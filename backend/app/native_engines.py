"""Run the bundled Chatterbox and Stable Diffusion services natively: no Docker (0.9.4-beta.3).

SceneForge downloads uv (Astral, MIT/Apache-2.0; pinned version, SHA-256 checked), lets uv
fetch a private Python 3.11, installs the service's packages into a private environment
under the engines folder, and starts the same FastAPI service the Docker image ran, on the
same loopback port. Nothing is installed system-wide and nothing needs administrator rights.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import zipfile
from pathlib import Path

import requests

from app.config import LOGS_DIR, RESOURCE_DIR

UV_VERSION = "0.13.0"
UV_ASSETS = {  # (system, machine) -> (asset, sha256)
    ("Windows", "AMD64"): ("uv-x86_64-pc-windows-msvc.zip", "088962f9e7b7bd9ea740c04c650b2a21c8928c345bd99ac24350dc924dba656c"),
    ("Linux", "x86_64"): ("uv-x86_64-unknown-linux-gnu.tar.gz", "1468ebd5a5541121837c5a2817b9972ba6090fa6caa3d142620850a47fb75154"),
    ("Darwin", "arm64"): ("uv-aarch64-apple-darwin.tar.gz", "a9c1b29002cf3c83f07fa9cd8a887a3be0107d90e23189721221e7257db8e3d6"),
    ("Darwin", "x86_64"): ("uv-x86_64-apple-darwin.tar.gz", "5f44dcbde809b632f47c36fadb241cb4d6f9af71d0c8f172b5d2026d3dde742c"),
}
PYTHON = "3.11"
SPECS = {
    "chatterbox": {"port": 8881, "service": "chatterbox", "torch": ["torch==2.6.0", "torchaudio==2.6.0"],
                   "gpu_index": "https://download.pytorch.org/whl/cu124", "label": "Chatterbox voices"},
    "stable_diffusion": {"port": 7860, "service": "stable-diffusion", "torch": ["torch==2.6.0"],
                         "gpu_index": "https://download.pytorch.org/whl/cu124", "label": "Stable Diffusion"},
}
CPU_INDEX = "https://download.pytorch.org/whl/cpu"
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_processes: dict[str, subprocess.Popen] = {}
_lock = threading.Lock()


class NativeEngineError(RuntimeError):
    pass


def root() -> Path:
    if os.environ.get("SCENEFORGE_NATIVE_ENGINES"):
        return Path(os.environ["SCENEFORGE_NATIVE_ENGINES"])
    from app.managed_ai import engine_root
    return engine_root() / "native"


def _exe(name: str) -> str:
    return name + (".exe" if os.name == "nt" else "")


def uv_path() -> Path:
    return root() / "uv" / _exe("uv")


def _env(gpu: bool = False) -> dict:
    base = root()
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV")}
    env.update(UV_PYTHON_INSTALL_DIR=str(base / "python"), UV_CACHE_DIR=str(base / "uv-cache"),
               UV_NO_CONFIG="1", UV_PYTHON_PREFERENCE="only-managed", HF_HOME=str(base / "models"),
               PYTHONUNBUFFERED="1")
    return env


def ensure_uv(report=print) -> Path:
    target = uv_path()
    if target.is_file():
        return target
    key = (platform.system(), platform.machine())
    if key not in UV_ASSETS:
        raise NativeEngineError(f"Automatic engine setup does not support {key[0]} on {key[1]} yet.")
    asset, digest = UV_ASSETS[key]
    report(f"Downloading the engine installer (uv {UV_VERSION}).")
    url = f"https://github.com/astral-sh/uv/releases/download/{UV_VERSION}/{asset}"
    try:
        data = requests.get(url, timeout=(15, 300)).content
    except requests.RequestException as e:
        raise NativeEngineError("Could not download the engine installer. Check the internet connection and retry.") from e
    if hashlib.sha256(data).hexdigest() != digest:
        raise NativeEngineError("The engine installer download did not match its checksum and was discarded. Retry.")
    target.parent.mkdir(parents=True, exist_ok=True)
    name = _exe("uv")
    if asset.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            member = next(m for m in z.namelist() if m.endswith("/" + name) or m == name)
            target.write_bytes(z.read(member))
    else:
        with tarfile.open(fileobj=io.BytesIO(data)) as t:
            member = next(m for m in t.getmembers() if m.name.endswith("/" + name) or m.name == name)
            target.write_bytes(t.extractfile(member).read())
    target.chmod(0o755)
    return target


def venv_python(component: str) -> Path:
    v = root() / component / "venv"
    return v / "Scripts" / "python.exe" if os.name == "nt" else v / "bin" / "python"


def installed(component: str) -> bool:
    return (root() / component / "installed.json").is_file() and venv_python(component).is_file()


def build(component: str) -> str | None:
    """Which PyTorch build an installed engine has: "gpu", "cpu" or None (not installed)."""
    if not installed(component):
        return None
    try:
        return "gpu" if json.loads((root() / component / "installed.json").read_text(encoding="utf-8")).get("gpu") else "cpu"
    except (OSError, ValueError):
        return "cpu"


def _requirements_sha(component: str) -> str:
    try:
        return hashlib.sha256((_service_source(component) / "requirements.txt").read_bytes()).hexdigest()[:16]
    except (OSError, NativeEngineError):
        return ""


def stale(component: str) -> bool:
    """The engine's packages were installed from an older requirements list (for example
    before setuptools was added for Chatterbox's watermark in 0.9.4-beta.5)."""
    current = _requirements_sha(component) if installed(component) else ""
    if not current:
        return False
    try:
        info = json.loads((root() / component / "installed.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    return info.get("requirements") != current


def refresh_packages(component: str, run=None, report=print) -> None:
    """Bring an installed engine's packages up to date (PyTorch is left as it is)."""
    if not stale(component):
        return
    uv = str(ensure_uv(report))
    run = run or (lambda args, env: subprocess.run(args, env=env, check=True, creationflags=FLAGS))
    report(f"{SPECS[component]['label']}: updating the engine packages.")
    run([uv, "pip", "install", "--python", str(venv_python(component)), "-r",
         str(_service_source(component) / "requirements.txt")], _env())
    path = root() / component / "installed.json"
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        info = {}
    info["requirements"] = _requirements_sha(component)
    path.write_text(json.dumps(info), encoding="utf-8")


def nvidia_present() -> bool:
    """An NVIDIA driver is installed (nvidia-smi ships with it)."""
    if shutil.which("nvidia-smi"):
        return True
    return os.name == "nt" and Path(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "nvidia-smi.exe").is_file()


def _service_source(component: str) -> Path:
    name = SPECS[component]["service"]
    for base in (Path(RESOURCE_DIR) / "services", Path(__file__).resolve().parents[2] / "services"):
        if (base / name / "server.py").is_file():
            return base / name
    raise NativeEngineError("The engine files are missing from this installation. Reinstall SceneForge.")


def install(component: str, gpu: bool = False, run=None, report=print, packages: list[str] | None = None) -> None:
    """Create the private environment and install the engine's packages. `run(args, env)`
    streams command output into the setup log. `packages` replaces the real package set
    (tests only)."""
    spec = SPECS[component]
    uv = str(ensure_uv(report))
    home = root() / component
    home.mkdir(parents=True, exist_ok=True)
    env = _env(gpu)
    run = run or (lambda args, env: subprocess.run(args, env=env, check=True, creationflags=FLAGS))
    report(f"{spec['label']}: preparing a private Python {PYTHON} (downloads once).")
    run([uv, "venv", "--python", PYTHON, "--allow-existing", str(home / "venv")], env)
    py = str(venv_python(component))
    source = _service_source(component)
    if packages is None:
        torch_args = [uv, "pip", "install", "--python", py, *spec["torch"]]
        if build(component) not in (None, "gpu" if gpu else "cpu"):
            # Switching between the CPU and NVIDIA builds: "torch==2.6.0" is already satisfied by the
            # other build, so ask uv to replace it.
            for package in spec["torch"]:
                torch_args += ["--reinstall-package", package.split("==")[0]]
        if platform.system() != "Darwin":
            torch_args += ["--index-url", spec["gpu_index"] if gpu else CPU_INDEX]
        report(f"{spec['label']}: installing PyTorch ({'NVIDIA GPU' if gpu else 'CPU'} build, about 1–3 GB).")
        run(torch_args, env)
        report(f"{spec['label']}: installing the engine packages.")
        run([uv, "pip", "install", "--python", py, "-r", str(source / "requirements.txt")], env)
    else:
        run([uv, "pip", "install", "--python", py, *packages], env)
    shutil.copy2(source / "server.py", home / "server.py")
    (home / "installed.json").write_text(json.dumps({"python": PYTHON, "gpu": bool(gpu), "uv": UV_VERSION,
                                                     "requirements": _requirements_sha(component),
                                                     "installed": time.strftime("%Y-%m-%d %H:%M:%S")}), encoding="utf-8")


def running(component: str) -> bool:
    p = _processes.get(component)
    return bool(p and p.poll() is None)


def start(component: str, gpu: bool = False) -> bool:
    """Start the engine in the background (no window). Returns False when not installed.
    The device follows the PyTorch build that is actually installed, not the current setting,
    so a CPU build is never asked to run on the graphics card."""
    if not installed(component):
        return False
    gpu = build(component) == "gpu"
    if running(component):
        return True
    try:
        refresh_packages(component)
    except (subprocess.CalledProcessError, OSError, NativeEngineError):
        pass   # start anyway; the engine reports its own error if a package is missing
    with _lock:
        if running(component):
            return True
        spec = SPECS[component]
        home = root() / component
        server = _service_source(component) / "server.py"
        try:   # keep the copy current after SceneForge updates
            shutil.copy2(server, home / "server.py")
        except OSError:
            pass
        env = _env(gpu)
        if component == "chatterbox":
            env["CHATTERBOX_DEVICE"] = "cuda" if gpu else "cpu"
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log = (LOGS_DIR / f"{component}-engine.log").open("a", encoding="utf-8")
        _processes[component] = subprocess.Popen(
            [str(venv_python(component)), "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", str(spec["port"])],
            cwd=str(home), env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, creationflags=FLAGS)
        return True


def stop(component: str) -> None:
    p = _processes.pop(component, None)
    if p and p.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill.exe", "/PID", str(p.pid), "/T", "/F"], capture_output=True, creationflags=FLAGS, timeout=15)
        else:
            p.terminate()
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()


def stop_all() -> None:
    for component, p in list(_processes.items()):
        if p.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill.exe", "/PID", str(p.pid), "/T", "/F"], capture_output=True, creationflags=FLAGS, timeout=15)
            else:
                p.terminate()
                try:
                    p.wait(10)
                except subprocess.TimeoutExpired:
                    p.kill()
        _processes.pop(component, None)


MODEL_REPOS = {"chatterbox": ("ResembleAI/chatterbox", 3200), "stable_diffusion": ("stable-diffusion-v1-5/stable-diffusion-v1-5", 5500)}


def model_cache_mb(component: str | None = None) -> float:
    """MB of model files downloaded, for one engine's model (or every model when None)."""
    base = root() / "models"
    if component in MODEL_REPOS:
        base = base / "hub" / ("models--" + MODEL_REPOS[component][0].replace("/", "--"))
    total = 0
    for path in base.rglob("*") if base.exists() else ():
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except OSError:
            pass
    return total / 1_000_000
