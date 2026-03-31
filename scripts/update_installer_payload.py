#!/usr/bin/env python3
import base64
import gzip
import pathlib
import re
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE_PATH = REPO_ROOT / "src" / "ec2m.py"
INSTALLER_PATH = REPO_ROOT / "install-ec2m.sh"


def build_payload(source_path: pathlib.Path) -> str:
    source_bytes = source_path.read_bytes()
    encoded = base64.b64encode(gzip.compress(source_bytes)).decode("ascii")
    return "\n".join(encoded[i : i + 76] for i in range(0, len(encoded), 76))


def update_installer(installer_path: pathlib.Path, payload: str) -> None:
    text = installer_path.read_text()
    updated, count = re.subn(
        r'payload = """\n.*?\n"""',
        'payload = """\n' + payload + '\n"""',
        text,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError("Could not find embedded payload block in install-ec2m.sh")
    installer_path.write_text(updated)


def main() -> int:
    if not SOURCE_PATH.exists():
        print(f"Missing source file: {SOURCE_PATH}", file=sys.stderr)
        return 1
    if not INSTALLER_PATH.exists():
        print(f"Missing installer file: {INSTALLER_PATH}", file=sys.stderr)
        return 1

    payload = build_payload(SOURCE_PATH)
    update_installer(INSTALLER_PATH, payload)
    print(f"Updated embedded payload in {INSTALLER_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
