"""Chicken-owned macro library. Standard library only; Windows Documents discovery."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import uuid
FORMAT = 'chicken-macro-library-v1'

def documents_folder():
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [('Data1', wintypes.DWORD), ('Data2', wintypes.WORD), ('Data3', wintypes.WORD), ('Data4', ctypes.c_ubyte * 8)]
    guid = GUID.from_buffer_copy(uuid.UUID('FDD39AD0-238F-46AF-ADB4-6C85480369C7').bytes_le)
    shell = ctypes.windll.shell32
    ole = ctypes.windll.ole32
    get_path = shell.SHGetKnownFolderPath
    get_path.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
    get_path.restype = ctypes.c_long
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ptr = ctypes.c_void_p()
    hr = get_path(ctypes.byref(guid), 0, None, ctypes.byref(ptr))
    if hr != 0 or not ptr.value:
        raise OSError('Windows could not locate Documents. No macro data was moved.')
    try:
        return Path(ctypes.wstring_at(ptr.value))
    finally:
        ole.CoTaskMemFree(ptr)

def write_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('x', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()

def read_json(path):
    with Path(path).open(encoding='utf-8') as f:
        return json.load(f)

def safe_filename(name):
    return isinstance(name, str) and re.fullmatch('[A-Za-z0-9_-]+\\.json', name) is not None

class Library:

    def __init__(self, folder):
        self.folder = Path(folder).absolute()
        self.index = self.folder / 'library.json'
        self.index_data = None
        self.exists = self.index.is_file()

    def _read_index(self):
        data = read_json(self.index)
        if not isinstance(data, dict) or data.get('format') != FORMAT:
            raise ValueError('This folder is not a Chicken macro library.')
        files = data.get('files')
        if not isinstance(files, list) or not all((safe_filename(x) for x in files)) or len(files) != len(set(files)):
            raise ValueError('Invalid Chicken library index.')
        return data

    def load(self):
        if not self.index.exists():
            self.exists = False
            return None
        data = self._read_index()
        macros = []
        for filename in data['files']:
            path = self.folder / filename
            if path.is_symlink():
                raise ValueError('Linked macro files are not supported.')
            value = read_json(path)
            if not isinstance(value, dict) or value.get('format') != FORMAT or (not isinstance(value.get('macro'), dict)):
                raise ValueError('Invalid macro file: ' + filename)
            macros.append(value['macro'])
        self.index_data = data
        self.exists = True
        return macros

    def save(self, macros):
        if self.folder.is_symlink() or self.folder.parent.is_symlink():
            raise ValueError('Use a normal folder, not a directory link.')
        self.folder.mkdir(parents=True, exist_ok=True)
        old = self._read_index() if self.index.exists() else {'files': []}
        written = []
        try:
            for macro in macros:
                slug = re.sub('[^A-Za-z0-9_-]+', '-', str(macro.get('name', 'Macro'))).strip('-')[:35] or 'Macro'
                token = uuid.uuid4().hex
                filename = slug + '-' + token + '.json'
                write_json(self.folder / filename, {'format': FORMAT, 'macro': macro})
                written.append(filename)
            data = {'format': FORMAT, 'files': written}
            write_json(self.index, data)
        except Exception:
            for filename in written:
                try:
                    (self.folder / filename).unlink()
                except OSError:
                    pass
            raise
        self.index_data = data
        self.exists = True
        for filename in old['files']:
            path = self.folder / filename
            try:
                if not path.is_symlink() and read_json(path).get('format') == FORMAT:
                    path.unlink()
            except (OSError, ValueError, AttributeError):
                pass

    def deletion_targets(self):
        if self.folder.is_symlink() or self.folder.parent.is_symlink() or self.index.is_symlink():
            raise ValueError('Linked library folders cannot be safely removed.')
        if not self.index.exists():
            return []
        data = self._read_index()
        targets = []
        for name in data['files']:
            p = self.folder / name
            if p.is_symlink() or p.resolve().parent != self.folder.resolve():
                raise ValueError('Refusing to remove linked files.')
            if p.exists() and read_json(p).get('format') != FORMAT:
                raise ValueError('A file is not recognized as Chicken data: ' + str(p))
            targets.append(p)
        return targets + [self.index]

    def delete_owned(self):
        for p in self.deletion_targets():
            if p.exists():
                p.unlink()
        for directory in (self.folder, self.folder.parent):
            try:
                directory.rmdir()
            except OSError:
                pass
