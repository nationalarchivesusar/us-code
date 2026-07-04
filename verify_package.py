#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    manifest_path = ROOT / 'PACKAGE-MANIFEST.json'
    if not manifest_path.exists():
        print('PACKAGE-MANIFEST.json is missing.', file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    errors: list[str] = []
    for item in manifest.get('files', []):
        path = ROOT / item['path']
        if not path.is_file():
            errors.append(f"missing: {item['path']}")
            continue
        actual_size = path.stat().st_size
        actual_hash = sha256(path)
        if actual_size != item['bytes']:
            errors.append(f"size mismatch: {item['path']} ({actual_size} != {item['bytes']})")
        if actual_hash != item['sha256']:
            errors.append(f"SHA-256 mismatch: {item['path']}")
    if errors:
        print('Package integrity check failed:', file=sys.stderr)
        for error in errors:
            print(f'- {error}', file=sys.stderr)
        return 1

    proc = subprocess.run(
        [sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'), '-p', 'test_*.py', '-v'],
        cwd=ROOT,
        text=True,
    )
    if proc.returncode:
        return proc.returncode
    print(f"Package verified: {len(manifest.get('files', []))} files and all tests passed.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
