#!/usr/bin/env python3
"""Build distributable packages from an explicit source allowlist."""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ['server', 'core', 'expiry', 'templates', 'api_transport', 'portal_install',
           'pricing', 'voucher_history', 'locations', 'payments', 'backups',
           'gateways', 'sales', 'diagnostics', 'llm_review', 'app_paths', 'user_manager']
NAME = 'nelsonict-router-manager'
VERSION = '0.4.0'

def windows():
    if sys.platform != 'win32':
        raise SystemExit('Build the EXE on Windows, or use the GitHub Actions package workflow.')
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                    '--onefile', '--console', '--name', 'NelsonictRouterManager',
                    '--distpath', str(ROOT / 'dist'), '--workpath', str(ROOT / 'build' / 'windows'),
                    '--specpath', str(ROOT / 'build'), '--add-data', str(ROOT / 'web') + ':web',
                    '--add-data', str(ROOT / 'LICENSE') + ':.',
                    str(ROOT / 'server.py')], cwd=ROOT, check=True)

def deb():
    if not shutil.which('dpkg-deb'):
        raise SystemExit('Install dpkg-dev on Debian/Ubuntu before building a DEB.')
    with tempfile.TemporaryDirectory(prefix='nelsonict-deb-') as temporary:
        stage = Path(temporary)
        app = stage / 'usr' / 'lib' / NAME
        app.mkdir(parents=True)
        for module in MODULES:
            shutil.copy2(ROOT / (module + '.py'), app)
        shutil.copytree(ROOT / 'web', app / 'web')
        doc = stage / 'usr' / 'share' / 'doc' / NAME
        doc.mkdir(parents=True)
        shutil.copy2(ROOT / 'LICENSE', doc / 'copyright')
        for source in ROOT.glob('*.md'):
            shutil.copy2(source, doc)
        launcher = stage / 'usr' / 'bin' / NAME
        launcher.parent.mkdir(parents=True)
        launcher.write_text('#!/bin/sh\nset -eu\n'
            ': "${NELSONICT_DATA_DIR:=${XDG_DATA_HOME:-$HOME/.local/share}/nelsonict-router-manager}"\n'
            'export NELSONICT_DATA_DIR\n'
            'exec /usr/bin/python3 /usr/lib/nelsonict-router-manager/server.py "$@"\n')
        launcher.chmod(0o755)
        desktop = stage / 'usr' / 'share' / 'applications' / (NAME + '.desktop')
        desktop.parent.mkdir(parents=True)
        desktop.write_text('[Desktop Entry]\nType=Application\nName=Nelsonict Router Manager\n'
            'Comment=Manage MikroTik hotspots and vouchers\nExec=nelsonict-router-manager\n'
            'Icon=network-server\nTerminal=true\nCategories=Network;\n')
        control = stage / 'DEBIAN' / 'control'
        control.parent.mkdir()
        control.write_text(f'Package: {NAME}\nVersion: {VERSION}\nArchitecture: all\n'
            'Maintainer: Nelsonict Services Limited <info@nelsonict.com.ng>\n'
            'Depends: python3 (>= 3.11)\nRecommends: xdg-utils\nSection: net\nPriority: optional\n'
            'Homepage: https://github.com/edunelsonit/nelsonict-router-manager\n'
            'Description: Local MikroTik hotspot and voucher manager\n'
            ' Browser-based owner dashboard, setup walkthrough and sales reporting.\n')
        for entry in stage.rglob('*'):
            entry.chmod(0o755 if entry.is_dir() or entry == launcher else 0o644)
        output = ROOT / 'dist' / f'{NAME}_{VERSION}_all.deb'
        output.parent.mkdir(exist_ok=True)
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage), str(output)], check=True)
        print(output)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', choices=['exe', 'deb'])
    args = parser.parse_args()
    (windows if args.target == 'exe' else deb)()
