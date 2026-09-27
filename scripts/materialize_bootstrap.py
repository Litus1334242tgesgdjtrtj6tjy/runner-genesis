from __future__ import annotations

import base64
import gzip
import io
import json
from pathlib import Path
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BOOT = ROOT / ".bootstrap"

def safe_target(name: str) -> Path:
    p = (ROOT / name).resolve()
    if ROOT not in p.parents and p != ROOT:
        raise RuntimeError(f"unsafe archive path: {name}")
    if name.startswith(".git/") or name == ".env":
        raise RuntimeError(f"refusing protected path: {name}")
    return p

def latest_payload() -> tuple[str, bytes]:
    bundles = sorted(BOOT.glob("*.bundle"))
    if bundles:
        p = bundles[-1]
        return p.stem, base64.b64decode(p.read_text().strip())
    groups: dict[str, list[Path]] = {}
    for p in BOOT.glob("*.part*"):
        prefix = p.name.split(".part", 1)[0]
        groups.setdefault(prefix, []).append(p)
    if not groups:
        raise RuntimeError("no bootstrap payload found")
    prefix = sorted(groups)[-1]
    parts = sorted(groups[prefix])
    text = "".join(p.read_text().strip() for p in parts)
    return prefix, base64.b64decode(text)

def extract_tar(raw: bytes) -> list[str]:
    paths=[]
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as tf:
        members=[]
        for m in tf.getmembers():
            if not m.isfile():
                continue
            safe_target(m.name)
            members.append(m)
            paths.append(m.name)
        tf.extractall(ROOT, members=members, filter="data")
    return paths

def extract_zip(raw: bytes) -> list[str]:
    paths=[]
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            target=safe_target(name)
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(zf.read(name))
            paths.append(name)
    return paths

def extract_json(raw: bytes) -> list[str]:
    obj=json.loads(raw.decode())
    files=obj.get("files",obj) if isinstance(obj,dict) else None
    if not isinstance(files,dict):
        raise RuntimeError("unsupported JSON bootstrap format")
    paths=[]
    for name,value in files.items():
        target=safe_target(name)
        target.parent.mkdir(parents=True,exist_ok=True)
        if isinstance(value,dict) and "base64" in value:
            data=base64.b64decode(value["base64"])
        elif isinstance(value,str):
            data=value.encode()
        else:
            raise RuntimeError(f"unsupported value for {name}")
        target.write_bytes(data)
        paths.append(name)
    return paths

def main() -> None:
    label,payload=latest_payload()
    try:
        raw=gzip.decompress(payload)
    except OSError:
        raw=payload
    try:
        paths=extract_tar(raw)
    except tarfile.TarError:
        if zipfile.is_zipfile(io.BytesIO(raw)):
            paths=extract_zip(raw)
        else:
            paths=extract_json(raw)
    print(f"materialized {len(paths)} files from {label}")
    for p in paths[:20]:
        print(p)

if __name__ == "__main__":
    main()
