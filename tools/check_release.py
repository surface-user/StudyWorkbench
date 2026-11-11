"""Inspect the staged Windows dependency closure and artifact inventory."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from native_dependencies import inspect_dependencies
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
    report = inspect_dependencies(payload, Path(os.environ['SystemRoot']) / 'System32')
    print(json.dumps({key: value for key, value in report.items() if key != 'domains'}, ensure_ascii=False))
    if report['unproven_runtime_candidates']:
        raise ValueError('Native runtime coverage incomplete: unclassified PE images block release; '
                         'establish auditable execution domains or non-runtime classification first')
    print(f"PASS: {len(inventory['files'])} file hashes, CPython version, no database, main-process x64 headers, "
          "declared static native loading domains; not a clean-VM or full loader test")


if __name__ == "__main__":
    main()
