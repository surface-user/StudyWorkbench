"""Inspect the staged Windows dependency closure and artifact inventory."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import pefile
from release_inventory import stage_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", type=Path)
    args = parser.parse_args()
    stage = args.stage.resolve()
    payload = stage_files(stage)
    inventory = json.loads((stage / "build-inventory.json").read_text(encoding="utf-8"))
    assert inventory["python"] == "3.13.17"
    expected = set(inventory["files"])
    if set(payload) != expected:
        raise ValueError(f"Release inventory mismatch: {len(expected - payload.keys())} missing, "
                         f"{len(payload.keys() - expected)} unlisted")
    assert not any(path.suffix.lower() == '.db' for path in payload.values()), "Personal database must not be shipped"
    for relative, expected in inventory["files"].items():
        path = payload[relative]
        with path.open("rb") as handle:
            assert hashlib.file_digest(handle, "sha256").hexdigest() == expected, relative
    files = {path.name.lower() for path in payload.values()}
    assert "python313.dll" in files and "python312.dll" not in files
    missing = set()
    for path in payload.values():
        if path.suffix.lower() not in {".exe", ".dll", ".pyd"}:
            continue
        pe = pefile.PE(str(path), fast_load=True)
        try:
            relative = path.relative_to(stage)
            if (len(relative.parts) == 1
                    or relative.as_posix().lower() == 'backend/study_backend.exe'
                    or (relative.parts[0].lower() == 'backend' and path.suffix.lower() in {'.dll', '.pyd'})):
                if (pe.FILE_HEADER.Machine != pefile.MACHINE_TYPE['IMAGE_FILE_MACHINE_AMD64']
                        or pe.OPTIONAL_HEADER.Magic != pefile.OPTIONAL_HEADER_MAGIC_PE_PLUS):
                    raise ValueError(f'Expected x64 PE32+ image: {relative.as_posix()}')
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
    print(f"PASS: {len(inventory['files'])} file hashes, CPython version, no database, main-process x64 headers, PE imports available; not a clean-VM test")


if __name__ == "__main__":
    main()
