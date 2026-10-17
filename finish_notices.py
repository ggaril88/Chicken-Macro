"""Run in the Chicken project: py finish_notices.py
Prepares release notices and source snapshot. Does not build or publish anything.
"""
import datetime
import importlib.metadata as metadata
from pathlib import Path
import shutil
import zipfile
EXCEPTION = '\n\n9. Third-party libraries and LGPL compatibility\nThe no-resale and other restrictions in this license apply only to the original\nChicken Macro application material, not to third-party components licensed\nseparately. Their own license permissions and conditions remain in effect.\n\nNotwithstanding other terms of this license, you may modify or replace the LGPL\nlibrary portions used by Chicken Macro, reverse engineer for debugging such\nmodifications, and use the supplied application source and build materials to\nrecombine or relink Chicken Macro with a modified, interface-compatible library\nand install and run that modified combined work. No term of this application\nlicense limits these permissions or any further rights required by the LGPL.\nThis exception takes precedence over conflicting application license terms.\n'
NOTICES = "# Third-party software\n\nChicken Macro uses pynput 1.8.2, licensed under the GNU Lesser General Public\nLicense version 3 (see its source for any later-version permission). The library\nand its use are covered by that license. The Python code is packaged by\nPyInstaller; a frozen bundle is not represented here as a replaceable shared\npynput installation.\n\n- Library license: third_party/licenses/packages/pynput/\n- LGPL and GPL texts: third_party/licenses/gnu/\n- Exact library source: third_party/sources/\n- Application source and build files: source-release/Chicken-Macro-source.zip\n- Rebuild and library-replacement instructions: REBUILDING.md\n\nAlso included are collected Python, six, Tcl/Tk 9.0.4 and build-tool notices.\nSome collected packages are build tools, not necessarily runtime dependencies.\nKeep each component's original copyright and license text unchanged. Chicken's\ncustom application license does not replace these licenses or restrict the\nrights they grant over those components. See LICENSE, section 9.\n\nThe exact Tcl/Tk license downloads and pynput source hash are recorded in\nthird_party/PROVENANCE.json. This package of materials is not a legal opinion\nor a guarantee that every distribution obligation has been satisfied.\n"
REBUILD = '# Rebuild Chicken and use a modified pynput\n\n## Contents\nThe source archive contains the application source, storage module, icon,\nsounds, installer script, package-version file, release-preparation scripts,\napplication license and build instructions. It excludes personal settings,\nrecorded macros, backups, and build outputs.\nThe unmodified pynput source archive is supplied separately in third_party/sources.\nKeep the source archive and that third_party folder from the same release together.\n\n## Build environment\nUse Windows and Python 3.14.7, matching the release\'s reported build environment.\nInstall Inno Setup separately if you want to build the setup executable.\nExtract the application source archive into a new folder. Copy the release\'s\nthird_party folder into that folder. Do not use your only development copy.\n\nOpen a terminal in the new source folder:\n\n    py -3.14 -m venv .venv\n    .venv\\Scripts\\python.exe -m pip install -r requirements-build.txt\n\n## Modify or replace pynput\nExtract the supplied pynput-1.8.2 source archive into a separate directory.\nMake your library changes there, preserving the relevant library notices.\nInstall the modified library in the build environment, replacing the published\ncopy. Substitute your extracted library directory for the example path:\n\n    .venv\\Scripts\\python.exe -m pip uninstall -y pynput\n    .venv\\Scripts\\python.exe -m pip install --no-deps "C:\\path\\to\\modified-pynput"\n\nThe library must retain an interface compatible with Chicken\'s pynput calls.\nThe application source is editable too. You may reverse engineer for debugging\nlibrary modifications as described in LICENSE section 9. There is no\napplication-level signature check requiring the author\'s permission to rebuild\nor execute this local build. Windows or organization security policies may\nseparately affect execution; do not disable system security to bypass them.\n\n## Build the app with the selected library\n\n    .venv\\Scripts\\python.exe -m PyInstaller --clean --noconfirm --onedir --windowed --name Chicken --icon chicken.ico --add-data "chicken.ico:." --add-data "sounds:sounds" chicken.py\n\nThe output is dist\\Chicken\\Chicken.exe. Keep its supporting files together.\nRe-run the notice/source preparation scripts for modified distributions so that\nsource, library materials and package metadata match the actual distributed build.\nDo not reuse the original library archive if you distribute a modified library.\n\n## Build an optional installer\nOpen Chicken-Setup.iss in Inno Setup and compile it after rebuilding the app.\nThe installer\'s source paths are relative to this project directory.\nRun the resulting setup normally for a per-user installation. A rebuilt app\nmay be launched from its bundle directory without installing it.\n\n## Source snapshots\nRe-run finish_notices.py after the final application changes and before\ncompiling the installer. It refreshes the matching application source archive.\nThe dependency lock records installed build versions; it does not guarantee\nbit-for-bit reproducible binaries or availability of packages forever.\n'

def main():
    base = Path(__file__).resolve().parent
    required = ['chicken.py', 'chicken_storage.py', 'chicken.ico', 'sounds', 'requirements.txt', 'Chicken-Setup.iss', 'LICENSE', 'third_party']
    missing = [n for n in required if not (base / n).exists()]
    if missing:
        raise ValueError('Missing: ' + ', '.join(missing))
    for n in ('third_party/licenses/gnu/GPL-3.0.txt', 'third_party/licenses/gnu/LGPL-3.0.txt'):
        if not (base / n).is_file():
            raise ValueError('Missing license text: ' + n)
    if not list((base / 'third_party' / 'sources').glob('pynput-1.8.2*')):
        raise ValueError('Expected pynput 1.8.2 source archive was not found.')
    lic = base / 'LICENSE'
    text = lic.read_text(encoding='utf-8-sig')
    if '9. Third-party libraries and LGPL compatibility' not in text:
        backup = base / ('LICENSE.before-third-party-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '.bak')
        shutil.copy2(lic, backup)
        lic.write_text(text.rstrip() + EXCEPTION, encoding='utf-8')
    (base / 'THIRD_PARTY_NOTICES.md').write_text(NOTICES, encoding='utf-8')
    (base / 'REBUILDING.md').write_text(REBUILD, encoding='utf-8')
    packages = ['pynput', 'six', 'pyinstaller', 'pyinstaller-hooks-contrib', 'altgraph', 'pefile', 'pywin32-ctypes', 'packaging', 'setuptools']
    pins = [name + '==' + metadata.version(name) for name in packages]
    (base / 'requirements-build.txt').write_text('\n'.join(pins) + '\n', encoding='utf-8')
    setup = base / 'Chicken-Setup.iss'
    installer = setup.read_text(encoding='utf-8-sig')
    marker = '; CHICKEN THIRD-PARTY RELEASE MATERIALS'
    if marker not in installer:
        if installer.count('[Files]') != 1:
            raise ValueError('Unrecognized installer Files section. No installer change made.')
        extra = '\n' + marker + '\nSource: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion\nSource: "THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion\nSource: "REBUILDING.md"; DestDir: "{app}"; Flags: ignoreversion\nSource: "third_party\\*"; DestDir: "{app}\\third_party"; Flags: ignoreversion recursesubdirs createallsubdirs\nSource: "source-release\\Chicken-Macro-source.zip"; DestDir: "{app}\\source-release"; Flags: ignoreversion\n'
        backup = base / ('Chicken-Setup.before-notices-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '.iss.bak')
        shutil.copy2(setup, backup)
        setup.write_text(installer.replace('[Files]', '[Files]' + extra), encoding='utf-8')
    output = base / 'source-release'
    output.mkdir(exist_ok=True)
    archive = output / 'Chicken-Macro-source.zip'
    files = [base / n for n in ['chicken.py', 'chicken_storage.py', 'chicken.ico', 'requirements.txt', 'requirements-build.txt', 'Chicken-Setup.iss', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'REBUILDING.md', 'chicken_updates.py']]
    files += [p for p in (base / 'sounds').rglob('*') if p.is_file()]
    for name in ('README.md', 'collect_notices.py', 'prepare_third_party.py', 'finish_notices.py'):
        if (base / name).is_file():
            files.append(base / name)
    temp = output / 'Chicken-Macro-source.tmp.zip'
    with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, 'Chicken-Macro/' + f.relative_to(base).as_posix())
    temp.replace(archive)
    print('DONE: notices, LGPL exception, dependency versions, and application source archive prepared.')
    print('LICENSE and Chicken-Setup.iss were backed up before any first-time changes.')
    print('Nothing was built, published, installed or deleted. No user macro data was collected.')
    print('Re-run this script after later source edits and before compiling the installer.')
if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit('STOPPED: ' + str(exc))
