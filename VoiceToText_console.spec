# -*- mode: python ; coding: utf-8 -*-
# 控制台诊断版：保留黑窗口，双击运行即可看到真实报错文字，
# 用于排查“双击完全没反应”这类被静默拦截/缺运行库的问题。
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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='VoiceToText_diag',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,            # 关键：显示控制台，把报错打印出来
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['D:/VoiceToText/src/app_icon.ico'],
)
