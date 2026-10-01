"""Fetch and verify the small AI models shipped inside the installer (works offline after install).

U2-Net small (u2netp, Apache-2.0, 4.6 MB) for subject cutout. Larger models download on first use.
"""
import hashlib, pathlib, sys, urllib.request
root = pathlib.Path(__file__).resolve().parents[1]
MODELS = [("cutout", "u2netp.onnx", "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx",
           "8e83ca70e441ab06c318d82300c84806")]
for folder, name, url, md5 in MODELS:
    dest = root / "vendor" / "models" / folder / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or hashlib.md5(dest.read_bytes()).hexdigest() != md5:
        print(f"downloading {url}", flush=True)
        data = urllib.request.urlopen(url, timeout=120).read()
        if hashlib.md5(data).hexdigest() != md5:
            sys.exit(f"{name}: checksum mismatch")
        dest.write_bytes(data)
    print(f"ok {dest} ({dest.stat().st_size} bytes)")
