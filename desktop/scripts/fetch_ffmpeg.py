"""Fetch FFmpeg/ffprobe for the build machine's OS at BUILD time (never on a user's PC),
verify the download, and check that every FFmpeg feature SceneForge uses is present.

  Windows: gyan.dev essentials 8.1.2 (pinned SHA-256)
  Linux:   BtbN FFmpeg-Builds n8.1 linux64 GPL (verified against the release's checksums.sha256)
  macOS:   ffmpeg-static (eugeneware) darwin builds for the runner's architecture

All are GPL builds; SceneForge is GPL-3.0-or-later. Sources and licenses: desktop/THIRD_PARTY.md.
"""
import gzip, hashlib, platform, shutil, stat, subprocess, sys, tarfile, tempfile, urllib.request, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "vendor/ffmpeg"
WIN_URL = "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-essentials_build.zip"
WIN_SHA256 = "db580001caa24ac104c8cb856cd113a87b0a443f7bdf47d8c12b1d740584a2ec"
BTBN = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
LINUX_FILE = "ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz"
MAC = "https://github.com/eugeneware/ffmpeg-static/releases/latest/download/"
# Filters the renderer relies on (captions/Arabic shaping, grading, effects, transitions, audio finishing).
REQUIRED_FILTERS = ["ass", "lut3d", "xfade", "zoompan", "colortemperature", "vibrance", "chromashift", "drawgrid",
                    "sidechaincompress", "loudnorm", "afftdn", "dynaudnorm", "colorkey", "alphamerge", "blend", "movie",
                    "boxblur", "gblur", "noise", "vignette", "curves", "rgbashift", "afade", "atrim", "amix"]
REQUIRED_ENCODERS = ["libx264", "aac", "qtrle", "ffv1"]


def download(url: str, dest: Path) -> str:
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=300) as r, dest.open("wb") as out:
        while chunk := r.read(1 << 20):
            out.write(chunk)
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract_zip(archive: Path, into: Path):
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if not (into / name).resolve().is_relative_to(into.resolve()):
                raise RuntimeError("Unsafe archive path")
        z.extractall(into)


def fetch_windows(tmp: Path):
    archive = tmp / "ffmpeg.zip"
    if download(WIN_URL, archive) != WIN_SHA256:
        raise RuntimeError("FFmpeg checksum mismatch; download rejected.")
    safe_extract_zip(archive, tmp)
    src = next(tmp.glob("ffmpeg-*/bin/ffmpeg.exe")).parents[1]
    shutil.copytree(src, TARGET)
    (TARGET / "bin/ffplay.exe").unlink(missing_ok=True)
    return f"URL: {WIN_URL}\nSHA256: {WIN_SHA256}\n"


def fetch_linux(tmp: Path):
    sums = tmp / "checksums.sha256"
    download(BTBN + "checksums.sha256", sums)
    expected = next(line.split()[0] for line in sums.read_text().splitlines() if line.endswith(" " + LINUX_FILE))
    archive = tmp / LINUX_FILE
    got = download(BTBN + LINUX_FILE, archive)
    if got != expected:
        raise RuntimeError("FFmpeg checksum mismatch; download rejected.")
    with tarfile.open(archive) as t:
        t.extractall(tmp, filter="data")
    src = next(tmp.glob("ffmpeg-*linux64-gpl*/bin/ffmpeg")).parents[1]
    (TARGET / "bin").mkdir(parents=True)
    for tool in ("ffmpeg", "ffprobe"):
        shutil.copy2(src / "bin" / tool, TARGET / "bin" / tool)
    for extra in ("LICENSE.txt",):
        if (src / extra).exists():
            shutil.copy2(src / extra, TARGET / extra)
    return f"URL: {BTBN}{LINUX_FILE}\nSHA256: {got} (matches the release checksums.sha256)\n"


def fetch_macos(tmp: Path):
    arch = "arm64" if platform.machine() in ("arm64", "aarch64") else "x64"
    (TARGET / "bin").mkdir(parents=True)
    lines = []
    for tool, gz in (("ffmpeg", True), ("ffprobe", False)):
        name = f"{tool}-darwin-{arch}" + (".gz" if gz else "")
        dl = tmp / name
        sha = download(MAC + name, dl)
        out = TARGET / "bin" / tool
        if gz:
            with gzip.open(dl) as src, out.open("wb") as dst:
                shutil.copyfileobj(src, dst)
        else:
            shutil.copy2(dl, out)
        out.chmod(out.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        lines.append(f"URL: {MAC}{name}\nSHA256: {sha}\n")
    return "".join(lines)


def verify():
    ext = ".exe" if sys.platform == "win32" else ""
    ff = TARGET / "bin" / ("ffmpeg" + ext)
    version = subprocess.run([str(ff), "-hide_banner", "-version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    filters = subprocess.run([str(ff), "-hide_banner", "-filters"], capture_output=True, text=True, check=True).stdout
    encoders = subprocess.run([str(ff), "-hide_banner", "-encoders"], capture_output=True, text=True, check=True).stdout
    have = {line.split()[1] for line in filters.splitlines() if len(line.split()) > 2 and line.startswith(" ")}
    missing = [f for f in REQUIRED_FILTERS if f not in have]
    missing += [e for e in REQUIRED_ENCODERS if f" {e} " not in encoders]
    subprocess.run([str(TARGET / "bin" / ("ffprobe" + ext)), "-hide_banner", "-version"], capture_output=True, check=True)
    if missing:
        raise RuntimeError(f"{version}: missing features SceneForge needs: {', '.join(missing)}")
    return version


def main():
    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        if sys.platform == "win32":
            info = fetch_windows(tmp)
        elif sys.platform == "darwin":
            info = fetch_macos(tmp)
        else:
            info = fetch_linux(tmp)
    (TARGET / "DOWNLOAD.txt").write_text(info, encoding="utf8")
    print("Verified:", verify())


if __name__ == "__main__":
    main()
