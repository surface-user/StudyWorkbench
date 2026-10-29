"""Local build inventory and license texts; not a vulnerability certification."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import url2pathname


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    args = parser.parse_args()
    stage = args.stage.resolve()
    licenses = stage / "licenses"
    licenses.mkdir(exist_ok=True)
    packages = []
    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"]
        packages.append({"name": name, "version": dist.version,
                         "license": dist.metadata.get("License-Expression") or dist.metadata.get("License", "See license files")})
        for file in dist.files or []:
            if (not file.name.lower().startswith(("license", "licence", "copying", "notice", "copyright", "authors"))
                    and not any(part.upper() in {"LICENSES", "BUILD_LICENSES"} for part in file.parts)):
                continue
            if file.suffix.lower() in {".py", ".pyc"}:
                continue
            if ".." in file.parts:
                continue
            source = Path(dist.locate_file(file))
            if source.is_file():
                destination = licenses / name / file
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    python_license = Path(__import__("sys").base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        shutil.copy2(python_license, licenses / "Python-LICENSE.txt")
    repository = Path(__file__).resolve().parent.parent
    package_file = repository / "apps/desktop/.dart_tool/package_config.json"
    flutter = json.loads(package_file.read_text(encoding="utf-8"))
    for package in flutter["packages"]:
        uri = urljoin(package_file.as_uri(), package["rootUri"])
        package_root = Path(url2pathname(urlsplit(uri).path))
        for path in package_root.iterdir():
            if path.is_file() and path.name.lower().startswith(("license", "notice", "copying")):
                destination = licenses / "dart" / package["name"] / path.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
    sdk = Path(url2pathname(urlsplit(flutter["flutterRoot"]).path))
    shutil.copy2(sdk / "LICENSE", licenses / "Flutter-LICENSE")
    native = repository / "apps/desktop/build/windows/x64/packages"
    for package in native.iterdir():
        if not package.is_dir():
            continue
        for path in package.iterdir():
            if path.is_file() and path.name.lower().startswith(("license", "notice")):
                destination = licenses / "native" / package.name / path.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
    json_license = repository / ".local/release-tools/nlohmann-json-3.11.2-LICENSE.MIT"
    destination = licenses / "native/nlohmann.json/LICENSE.MIT"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(json_license, destination)
    files = {}
    for path in sorted(stage.rglob("*")):
        if path.is_file() and path.name != "build-inventory.json":
            with path.open("rb") as handle:
                files[path.relative_to(stage).as_posix()] = hashlib.file_digest(handle, "sha256").hexdigest()
    (stage / "build-inventory.json").write_text(json.dumps({
        "python": platform.python_version(), "flutter": flutter["flutterVersion"], "build_environment_packages": packages,
        "files": files, "note": "Build environment list is not the frozen module set. Native/Flutter license review and clean-machine acceptance remain separate.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Inventory: {len(files)} files, {len(packages)} build packages; no personal data included")


if __name__ == "__main__":
    main()
