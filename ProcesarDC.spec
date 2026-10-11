# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


tkdnd_datas = collect_data_files('tkinterdnd2')
tkdnd_bins = collect_dynamic_libs('tkinterdnd2')

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=tkdnd_bins,
    datas=tkdnd_datas,
    hiddenimports=['tkinterdnd2'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ProcesarDC',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon='assets/procesardc.ico',
    version='version_info.txt',
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
