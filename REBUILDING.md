# Rebuild Chicken and use a modified pynput

## Contents
The source archive contains the application source, storage module, icon,
sounds, installer script, package-version file, release-preparation scripts,
application license and build instructions. It excludes personal settings,
recorded macros, backups, and build outputs.
The unmodified pynput source archive is supplied separately in third_party/sources.
Keep the source archive and that third_party folder from the same release together.

## Build environment
Use Windows and Python 3.14.7, matching the release's reported build environment.
Install Inno Setup separately if you want to build the setup executable.
Extract the application source archive into a new folder. Copy the release's
third_party folder into that folder. Do not use your only development copy.

Open a terminal in the new source folder:

    py -3.14 -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements-build.txt

## Modify or replace pynput
Extract the supplied pynput-1.8.2 source archive into a separate directory.
Make your library changes there, preserving the relevant library notices.
Install the modified library in the build environment, replacing the published
copy. Substitute your extracted library directory for the example path:

    .venv\Scripts\python.exe -m pip uninstall -y pynput
    .venv\Scripts\python.exe -m pip install --no-deps "C:\path\to\modified-pynput"

The library must retain an interface compatible with Chicken's pynput calls.
The application source is editable too. You may reverse engineer for debugging
library modifications as described in LICENSE section 9. There is no
application-level signature check requiring the author's permission to rebuild
or execute this local build. Windows or organization security policies may
separately affect execution; do not disable system security to bypass them.

## Build the app with the selected library

    .venv\Scripts\python.exe -m PyInstaller --clean --noconfirm --onedir --windowed --name Chicken --icon chicken.ico --add-data "chicken.ico:." --add-data "sounds:sounds" chicken.py

The output is dist\Chicken\Chicken.exe. Keep its supporting files together.
Re-run the notice/source preparation scripts for modified distributions so that
source, library materials and package metadata match the actual distributed build.
Do not reuse the original library archive if you distribute a modified library.

## Build an optional installer
Open Chicken-Setup.iss in Inno Setup and compile it after rebuilding the app.
The installer's source paths are relative to this project directory.
Run the resulting setup normally for a per-user installation. A rebuilt app
may be launched from its bundle directory without installing it.

## Source snapshots
Re-run finish_notices.py after the final application changes and before
compiling the installer. It refreshes the matching application source archive.
The dependency lock records installed build versions; it does not guarantee
bit-for-bit reproducible binaries or availability of packages forever.
