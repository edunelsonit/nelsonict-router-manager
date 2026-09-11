# Desktop packages

Open Actions → Build desktop packages → Run workflow on GitHub. After successful jobs, download and extract Nelsonict-Windows or Nelsonict-Debian from the run's Artifacts section. Workflow permission is required. Artifacts are not automatically published releases.

## Windows

On Windows with Python 3.11+, double-click build-windows.bat in the source folder. The script creates an isolated build environment and installs pinned PyInstaller; dependency installation requires Internet access. Output: dist/NelsonictRouterManager.exe. Users do not need Python installed. Keep the console open; Ctrl+C stops the backend. This is an unsigned portable EXE, not a setup wizard. Build it on Windows. Production distribution should add trusted code signing.

The build follows [PyInstaller one-file packaging](https://pyinstaller.org/en/stable/usage.html) and [bundled resource paths](https://pyinstaller.org/en/stable/runtime-information.html).

## Debian / Ubuntu

With Python 3.11+ and dpkg-dev installed, run:

```sh
sh build-deb.sh
sudo apt install ./dist/nelsonict-router-manager_0.4.0_all.deb
nelsonict-router-manager
```

The package uses system Python 3.11+ (available in Debian 12 and Ubuntu 24.04), includes a desktop launcher and does not install a background service. Run the app as your normal user, not root. Remove with sudo apt remove nelsonict-router-manager; owner data remains.

## Data and upgrades

- Windows EXE: %LOCALAPPDATA%/nelsonict-router-manager.
- DEB: ~/.local/share/nelsonict-router-manager, or $XDG_DATA_HOME/nelsonict-router-manager.
- Source: the existing data folder beside server.py.

NELSONICT_DATA_DIR overrides these locations. EXE data is outside its temporary extraction directory. Before migration, stop the backend and back up its complete data folder. Copy its contents into the new location, or set NELSONICT_DATA_DIR to its absolute path. Do not run two backends against the same directory. Application backup/restore excludes payment orders; a stopped full-folder copy retains those too.

Packages exclude owner data, environment files and payment credentials. Configure payment and AI environment variables on the host machine. The browser interface, router LAN/VPN reachability and connection restrictions remain unchanged.
