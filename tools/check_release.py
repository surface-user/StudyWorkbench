"""Inspect the staged Windows dependency closure and artifact inventory."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import pefile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", type=Path)
    args = parser.parse_args()
    stage = args.stage.resolve()
    inventory = json.loads((stage / "build-inventory.json").read_text(encoding="utf-8"))
    assert inventory["python"] == "3.13.17"
    for relative, expected in inventory["files"].items():
        path = stage / relative
        with path.open("rb") as handle:
            assert hashlib.file_digest(handle, "sha256").hexdigest() == expected, relative
    assert not list(stage.rglob("*.db")), "Personal database must not be shipped"
    files = {path.name.lower() for path in stage.rglob("*") if path.is_file()}
    assert "python313.dll" in files and "python312.dll" not in files
    missing = set()
    for path in stage.rglob("*"):
        if path.suffix.lower() not in {".exe", ".dll", ".pyd"}:
            continue
        pe = pefile.PE(str(path), fast_load=True)
        try:
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
            for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
                name = entry.dll.decode("ascii").lower()
                if name.startswith(("api-ms-", "ext-ms-")):
                    continue
                system = Path(os.environ["SystemRoot"]) / "System32" / name
                if name not in files and not system.is_file():
                    missing.add((path.relative_to(stage).as_posix(), name))
                if name.startswith(("msvcp", "vcruntime")):
                    assert name in files, f"CRT must be app-local: {name}"
        finally:
            pe.close()
    assert not missing, missing
    print(f"PASS: {len(inventory['files'])} file hashes, CPython version, no database, PE imports available; not a clean-VM test")


if __name__ == "__main__":
    main()
