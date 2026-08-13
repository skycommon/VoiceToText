# -*- mode: python ; coding: utf-8 -*-
# 文件夹版（onedir）：把 exe 与依赖 DLL 平铺到一个文件夹，
# 不像单文件包那样运行时自解压，极大降低杀软误报/静默拦截的概率。
from PyInstaller.utils.hooks import collect_all

datas = [('D:/VoiceToText/src/app_icon.ico', '.')]
binaries = []
hiddenimports = ['tkinter', 'websocket', 'sounddevice', 'soundfile']
tmp_ret = collect_all('sounddevice')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('soundfile')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['D:/VoiceToText/src/main.py'],
    pathex=['D:/VoiceToText/pylibs', 'D:/VoiceToText/src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# 注意：onedir 模式下 EXE 只放脚本，真正依赖由 COLLECT 收集到同名文件夹
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VoiceToText',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['D:/VoiceToText/src/app_icon.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VoiceToText',
)
