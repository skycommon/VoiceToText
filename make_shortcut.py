import os
import sys
import ctypes
from ctypes import wintypes

# GUIDs
CLSID_ShellLink = ctypes.c_ubyte*16  # placeholder; we use by-value below
# Actually use string CLSID via CoCreateInstance with clsid string is not allowed;
# we need the structure. Use pythoncom-free ctypes with CLSIDFromString.

ole32 = ctypes.windll.ole32
shell32 = ctypes.windll.shell32

# CLSID_ShellLink = {00021401-0000-0000-C000-000000000046}
# IID_IShellLinkW = {000214F9-0000-0000-C000-000000000046}
# IID_IPersistFile = {0000010B-0000-0000-C000-000000000046}

def CLSIDFromString(s):
    clsid = ctypes.create_string_buffer(16)
    ole32.CLSIDFromString(ctypes.c_wchar_p(s), clsid)
    return clsid

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]

CLSID_ShellLink = GUID(0x00021401, 0x0000, 0x0000,
                       (ctypes.c_ubyte*8)(0xC0,0x00,0x00,0x00,0x00,0x00,0x00,0x46))
IID_IShellLinkW = GUID(0x000214F9, 0x0000, 0x0000,
                       (ctypes.c_ubyte*8)(0xC0,0x00,0x00,0x00,0x00,0x00,0x00,0x46))
IID_IPersistFile = GUID(0x0000010B, 0x0000, 0x0000,
                        (ctypes.c_ubyte*8)(0xC0,0x00,0x00,0x00,0x00,0x00,0x00,0x46))

# IShellLinkW method indices (from IUnknown: 0=QueryInterface,1=AddRef,2=Release)
# IShellLink: 3=GetPath,4=GetIDList,5=SetIDList,6=GetDescription,7=SetDescription,
# 8=GetWorkingDirectory,9=SetWorkingDirectory,10=GetArguments,11=SetArguments,
# 12=GetHotkey,13=SetHotkey,14=GetShowCmd,15=SetShowCmd,16=GetIconLocation,
# 17=SetIconLocation,18=SetRelativePath,19=Resolve,20=SetPath
SL_SETPATH = 20
SL_SETWORKINGDIR = 9
SL_SETDESCRIPTION = 7
SL_SETICONLOCATION = 17

PF_SAVE = 6

# Load COM
ole32.CoInitialize(None)

pUnk = ctypes.c_void_p()
hr = ole32.CoCreateInstance(ctypes.byref(CLSID_ShellLink), None, 1, ctypes.byref(IID_IShellLinkW), ctypes.byref(pUnk))
if hr != 0:
    print("CoCreateInstance failed hr=%08x" % hr)
    sys.exit(1)

# Build VTABLE call helper
def vcall(iface, idx, *args):
    # iface is the interface pointer; first 8 bytes point to the vtable (array of fn ptrs)
    vt_pp = ctypes.cast(iface, ctypes.POINTER(ctypes.c_void_p))
    vtable = ctypes.cast(vt_pp.contents, ctypes.POINTER(ctypes.c_void_p * 64))
    func = ctypes.cast(vtable.contents[idx], ctypes.CFUNCTYPE(ctypes.c_long))
    return func(iface, *args)

target = "C:\\Users\\LBX\\AppData\\Local\\Programs\\VoiceToText\\VoiceToText.exe"
workdir = "C:\\Users\\LBX\\AppData\\Local\\Programs\\VoiceToText"
desc = "本地录音/音频转文字（讯飞/百度/OpenAI 可切换）"
icon = "C:\\Users\\LBX\\AppData\\Local\\Programs\\VoiceToText\\VoiceToText.exe,0"

p = pUnk
# SetPath
hr = vcall(p, SL_SETPATH, ctypes.c_wchar_p(target))
print("SetPath hr=%08x" % hr)
hr = vcall(p, SL_SETWORKINGDIR, ctypes.c_wchar_p(workdir))
print("SetWorkingDirectory hr=%08x" % hr)
hr = vcall(p, SL_SETDESCRIPTION, ctypes.c_wchar_p(desc))
print("SetDescription hr=%08x" % hr)
hr = vcall(p, SL_SETICONLOCATION, ctypes.c_wchar_p("C:\\Users\\LBX\\AppData\\Local\\Programs\\VoiceToText\\VoiceToText.exe"), 0)
print("SetIconLocation hr=%08x" % hr)

# QueryInterface for IPersistFile
ppf = ctypes.c_void_p()
hr = vcall(p, 0, ctypes.byref(IID_IPersistFile), ctypes.byref(ppf))
if hr != 0:
    print("QueryInterface(IPersistFile) failed hr=%08x" % hr)
    sys.exit(1)

desktop = os.path.join(os.path.expanduser("~"), "Desktop")
lnk = os.path.join(desktop, "语音转文字.lnk")
hr = vcall(ppf, PF_SAVE, ctypes.c_wchar_p(lnk), None, 2)  # STGM_WRITE|STGM_CREATE
print("Save hr=%08x -> %s" % (hr, lnk))
print("EXISTS:" , os.path.exists(lnk))
