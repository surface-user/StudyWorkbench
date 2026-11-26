"""Compare a pinned LibreOffice MSI cabinet with its administrative-image inventory on Windows."""
import ctypes
import hashlib
import os
import re
import subprocess
import tempfile
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

from prepare_java_runtime import no_links


def file_sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class MsiDatabase:
    def __init__(self):
        self.api = ctypes.WinDLL('msi')
        u = ctypes.c_uint
        p = ctypes.POINTER(u)
        w = ctypes.c_wchar_p
        for name, args in {'MsiOpenDatabaseW': [w, w, p], 'MsiDatabaseOpenViewW': [u, w, p],
                           'MsiViewExecute': [u, u], 'MsiViewFetch': [u, p], 'MsiCloseHandle': [u],
                           'MsiRecordGetStringW': [u, u, w, p], 'MsiRecordReadStream': [u, u, ctypes.c_void_p, p]}.items():
            getattr(self.api, name).argtypes = args
            getattr(self.api, name).restype = u
        self.handle = u()

    @contextmanager
    def rows(self, query):
        view = ctypes.c_uint()
        self.check(self.api.MsiDatabaseOpenViewW(self.handle, query, ctypes.byref(view)))
        def records():
            while True:
                row = ctypes.c_uint()
                status = self.api.MsiViewFetch(view, ctypes.byref(row))
                if status == 259:  # ERROR_NO_MORE_ITEMS
                    return
                self.check(status)
                try:
                    yield row
                finally:
                    self.api.MsiCloseHandle(row)
        cursor = records()
        try:
            self.check(self.api.MsiViewExecute(view, 0))
            yield cursor
        finally:
            cursor.close()
            self.api.MsiCloseHandle(view)

    @staticmethod
    def check(status):
        if status:
            raise OSError(status, 'Windows Installer database read failed')

    def table(self, table, fields):
        columns = ','.join('`' + field + '`' for field in fields)
        result = []
        with self.rows(f'SELECT {columns} FROM `{table}`') as rows:
            for row in rows:
                values = []
                for idx in range(1, len(fields) + 1):
                    buf = ctypes.create_unicode_buffer(2048)
                    length = ctypes.c_uint(len(buf))
                    self.check(self.api.MsiRecordGetStringW(row, idx, buf, ctypes.byref(length)))
                    values.append(buf.value)
                result.append(values)
        return result

    def cabinet(self, name, output):
        with self.rows("SELECT `Data` FROM `_Streams` WHERE `Name` = '" + name + "'") as rows:
            row = next(rows, None)
            if row is None:
                raise ValueError('Cabinet stream missing')
            buf = ctypes.create_string_buffer(1 << 20)
            with output.open('xb') as dest:
                while True:
                    count = ctypes.c_uint(len(buf))
                    self.check(self.api.MsiRecordReadStream(row, 1, buf, ctypes.byref(count)))
                    if not count.value:
                        break
                    dest.write(buf.raw[:count.value])
            if next(rows, None) is not None:
                raise ValueError('Duplicate cabinet stream')


def source_files(files, components, directories):
    records = {}
    for key, component, field, size in files:
        if (not re.fullmatch(r'[A-Za-z0-9_.-]+', key) or key.endswith('.') or
                re.fullmatch(r'CON|NUL|AUX|PRN|COM[1-9]|LPT[1-9]', key.split('.')[0], re.I) or key.casefold() in records):
            raise ValueError('Unsafe or duplicate cabinet identifier')
        parts = [field.rsplit('|', 1)[-1]]
        directory = components[component]
        seen = set()
        while directory not in ('TARGETDIR', 'INSTALLLOCATION'):
            if directory in seen or len(seen) > 32:
                raise ValueError('MSI directory cycle')
            seen.add(directory)
            directory, field = directories[directory]
            part = field.partition(':')[0].rsplit('|', 1)[-1]
            if part != '.':
                parts.append(part)
        if any(not p or p in ('.', '..') or any(c in p for c in '/\\:') for p in parts):
            raise ValueError('Unexpected MSI target path')
        records[key.casefold()] = ('/'.join(reversed(parts)), int(size))
    return records


def check_cabinet_files(folder, records, expected):
    results = defaultdict(set)
    found = set()
    for path in folder.iterdir():
        key = path.name.casefold()
        if key not in records or key in found or path.is_symlink() or not path.is_file():
            raise ValueError('Unexpected extracted cabinet member')
        name, size = records[key]
        if path.stat().st_size != size:
            raise ValueError('Cabinet size differs from MSI table')
        found.add(key)
        results[name].add(file_sha(path))
    if (found != records.keys() or results.keys() != expected.keys() or
            any(digest not in results[name] for name, digest in expected.items())):
        raise ValueError('MSI cabinet bytes differ from administrative-image file')
    return len(found)


def verify_msi(package, expected_sha, expected, scratch):
    no_links(package.absolute())
    if package.stat().st_size > 512 << 20 or file_sha(package) != expected_sha:
        raise ValueError('LibreOffice MSI digest differs')
    with tempfile.TemporaryDirectory(dir=scratch) as temp:
        folder = Path(temp)
        db = MsiDatabase()
        db.check(db.api.MsiOpenDatabaseW(str(package.resolve()), None, ctypes.byref(db.handle)))
        try:
            if db.table('Media', ['Cabinet']) != [['#libreoffice1.cab']]:
                raise ValueError('Expected the single pinned embedded cabinet')
            records = source_files(db.table('File', ['File', 'Component_', 'FileName', 'FileSize']),
                                   dict(db.table('Component', ['Component', 'Directory_'])),
                                   {k: (p, n) for k, p, n in db.table('Directory', ['Directory', 'Directory_Parent', 'DefaultDir'])})
            cabinet = folder / 'libreoffice1.cab'
            db.cabinet(cabinet.name, cabinet)
        finally:
            db.api.MsiCloseHandle(db.handle)
        extracted = folder / 'members'
        extracted.mkdir()
        subprocess.run([str(Path(os.environ['SystemRoot']) / 'System32/expand.exe'), '-F:*',
                        str(cabinet.resolve()), str(extracted.resolve())], stdout=subprocess.DEVNULL, check=True, timeout=300)
        return check_cabinet_files(extracted, records, expected)
