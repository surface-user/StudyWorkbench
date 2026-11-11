"""Native no-short-name directory probe; removes aliases only in a fresh owned test root."""
import argparse
import ctypes
import hashlib
import json
import os
import stat
import sys
from ctypes import wintypes
from pathlib import Path

from check_office_previews import check_complex_pdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from study_workbench.office_runtime import OfficeRuntime, native_directory  # noqa: E402


def remove_owned_alias(directory, root):
    directory = directory.absolute()
    assert directory == root or directory.is_relative_to(root)
    for parent in [directory, *directory.parents]:
        assert not parent.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT, parent
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.SetFileShortNameW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR]
    kernel.SetFileShortNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(directory), 0x10000, 7, None, 3, 0x02000000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not kernel.SetFileShortNameW(handle, ''):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)
    native = native_directory(directory)
    assert native.name == directory.name and os.path.samefile(directory, native)
    return native


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test-root', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--docx', type=Path, required=True)
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[1]
    root = args.test_root.absolute()
    assert root.is_relative_to(workspace / '.local'), 'Use this checkout .local only'
    assert root.resolve() == root and not root.exists(), 'Never reuse a prior directory or an alias'
    root.mkdir()
    remove_owned_alias(root, root)
    directory = root / '本任务无短名目录中文回退验证'
    directory.mkdir()
    native = remove_owned_alias(directory, root)
    source = directory / 'source.docx'
    raw = args.docx.resolve(strict=True).read_bytes()
    source.write_bytes(raw)
    runtime = OfficeRuntime(args.runtime.resolve(strict=True))
    output = runtime.convert(source, directory, lambda: None)
    layout = check_complex_pdf(output, '.docx')
    runtime.verify(lambda: None)
    assert source.read_bytes() == raw
    value = dict(native_length=len(str(native)), physical_length=len(str(directory)),
                 directory_alias_removed=True, same_directory=True, pages=layout,
                 source_sha256=hashlib.sha256(raw).hexdigest(), runtime_fingerprint=runtime.fingerprint,
                 component_unchanged=True, no_short_name_volume_tested=False)
    (root / 'result.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(value, ensure_ascii=False))


if __name__ == '__main__':
    main()
