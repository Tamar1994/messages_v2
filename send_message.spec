# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec — Webex Connect Message Sender
# Para gerar o .exe execute:  build.bat
#

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Pasta raiz do projeto
ROOT = Path(SPECPATH)

# Inclui todos os arquivos de tema/asset do customtkinter
ctk_datas = collect_data_files("customtkinter")

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Temas e imagens do customtkinter
        *ctk_datas,
        # Ícone personalizado
        (str(ROOT / "assets" / "app.ico"), "assets"),
    ],
    hiddenimports=[
        *collect_submodules("customtkinter"),
        "PIL._tkinter_finder",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageTk",
        "requests",
        "dotenv",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="WebexConnectSender",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX pode causar falsos positivos em antivírus corporativos
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,      # sem janela de console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "app.ico"),
    version=None,
)
