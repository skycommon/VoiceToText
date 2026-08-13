# VoiceToText (Windows)

[![GitHub release](https://img.shields.io/github/v/release/skycommon/VoiceToText)](https://github.com/skycommon/VoiceToText/releases)
[![GitHub downloads](https://img.shields.io/github/downloads/skycommon/VoiceToText/total)](https://github.com/skycommon/VoiceToText/releases)
[![Platform](https://img.shields.io/badge/platform-Windows-blue)](https://github.com/skycommon/VoiceToText)

> **Download**: Get `VoiceToText-1.0.1-windows.zip` from [Releases](https://github.com/skycommon/VoiceToText/releases), unzip it, then double-click `VoiceToText-Setup-1.0.1.exe` to install.

A lightweight local GUI for turning recordings / audio files into text via high-accuracy cloud recognition, with live display, copy, and `txt` / `srt` subtitle export.

Built for **lectures and meetings**: includes local noise reduction (spectral gating + 80 Hz high-pass to cut HVAC / fan rumble), optional **speaker diarization** (who is speaking), and **bilingual output** — the same audio is transcribed into two independent files (Simplified Chinese + English).

The app itself runs locally (UI, recording, denoise); recognition is performed by online services, so the installer is small (~24 MB) while Chinese accuracy stays high.

## 1. Install

- **Installer (recommended, in Releases)**: download `VoiceToText-1.0.1-windows.zip`, unzip to get `VoiceToText-Setup-1.0.1.exe`, run it (installs to the user program folder, no admin rights required). Creates Start Menu and desktop shortcuts.
- You can also build from source (see "6. Rebuild"). Build artifacts land in `dist\`.

> If the first launch complains about missing `vcruntime140.dll` / `api-ms-win-crt-*.dll`, install the
> [Visual C++ 2015–2022 runtime](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist).
> Most Windows 10/11 systems already have it.

## 2. Configure a recognition backend (required)

On first launch, open **Settings** and enter the credentials for one service, then save. **Use whichever service you have a key for**; all four can be switched anytime from the dropdown.

### 1. OpenAI Whisper API (simplest, strong multilingual)
- Needs: `api_key` (OpenAI Secret Key)
- Get it: https://platform.openai.com/api-keys
- Billing: pay-as-you-go, ~$0.006 / minute of audio

### 2. Baidu Speech (good Chinese, large free quota)
- Needs: `API Key` + `Secret Key`
- Get it: https://console.bce.baidu.com/ → Speech → create an application
- Free quota: a monthly amount of free calls

### 3. iFlytek Open Platform (most accurate Chinese, supports speaker diarization)
- Needs: `APPID` + `APIKey` + `APISecret`
- Get it: https://www.xfyun.cn/ → console → create an application
- **Two services**:
  - **Speech Dictation** (real-time short audio, no diarization): quick single-language transcription.
  - **File Transcription (LFASR)**: for long lecture/meeting audio, supports **speaker diarization**.
    **The "Separate speakers" feature requires this backend, and you must enable "录音文件转写 (LFASR)" for the app on the iFlytek console.**
- Free quota: daily / monthly free calls

Credentials are stored locally at `%APPDATA%\VoiceToText\config.json` (plaintext, local use only — do not share).

## 3. Usage

1. Pick a configured backend from the **Backend** dropdown. Default is "iFlytek Transcription" (supports diarization).
2. **UI language** (中文 / English): switch from the top dropdown; all text updates instantly and is remembered.
3. **Theme** (Light / Dark / Follow system): switch from the top dropdown. "Follow system" tracks Windows dark mode (set it in Settings → Personalization → Colors → Choose your default app mode); changes apply instantly and are remembered.
4. **Audio enhancement (denoise)**: when checked, a light local denoise (spectral gating + 80 Hz high-pass) runs before recognition to suppress classroom / meeting background noise. On by default; uncheck to send audio as-is.
5. **Separate speakers**: only available for the "iFlytek Transcription" backend (auto-disabled for others). When checked, results are split by speaker, e.g. `Speaker 1: …` `Speaker 2: …`. For meetings, the speaker count defaults to 2 and can be adjusted via the `speaker_number` field in `%APPDATA%\VoiceToText\config.json`.
6. **Language**: choose Chinese / English / Auto for single-language output; choose **Bilingual (zh+en)** to get **two independent results** (pure Chinese and pure English) from the same audio.
7. **Record**: click "Start Recording" → speak → "Stop Recording"; it uploads and transcribes automatically, result appears in the text box.
8. **File transcription**: click "Select audio file", supports `wav / mp3 / flac / m4a` etc.; auto-converted to the required format (16k mono) before sending.
9. **Results**:
   - "Copy" copies the text box (the Chinese transcript in bilingual mode);
   - "Export txt / Export srt" saves it.
     - Single language: one file;
     - **Bilingual: one save dialog auto-generates `base_zh.txt` / `base_zh.srt` and `base_en.txt` / `base_en.srt` as two independent files**.
10. "Clear" clears the current text.

## 4. Design notes

- **Accuracy vs size**: recognition is done by online services (iFlytek / Baidu / OpenAI are all high-accuracy models); the app ships no local speech model, so the installer is only ~24 MB — far smaller than local Whisper models (hundreds of MB to GB).
- **Local denoise**: "Audio enhancement" uses a pure-numpy spectral gate + 80 Hz high-pass, zero extra dependencies, no size increase, suppresses background noise before recognition.
- **Speaker diarization**: relies on iFlytek's "File Transcription (LFASR)" `speaker` field; other backends lack this capability.
- **Offline**: this tool needs internet to call recognition services; not suitable for fully offline use.
- **Privacy**: audio is sent only to the backend you choose; nothing is stored locally except exported files.

## 5. Project layout (for developers)

```
D:\VoiceToText\
├─ src\
│  ├─ main.py          # tkinter main UI
│  ├─ recorder.py      # recording / file import / format conversion
│  ├─ backends.py      # online recognition backends (OpenAI / Baidu / iFlytek dictation / iFlytek LFASR)
│  ├─ config.py        # credentials & config I/O
│  ├─ i18n.py          # UI localization (中文 / English)
│  └─ app_icon.ico     # app icon
├─ dist\
│  ├─ VoiceToText\                      # onedir (folder) build output
│  └─ VoiceToText-Setup-1.0.1.exe       # installer (generated by installer.iss)
├─ installer.iss       # Inno Setup script
├─ VoiceToText_onedir.spec   # onedir build spec
├─ VoiceToText_console.spec  # console diagnostic build spec
├─ gen_icon.py        # app icon generator
├─ make_shortcut.py   # desktop shortcut generator
├─ test_core.py / test_core2.py / e2e_smoke.py  # local automated tests
└─ pylibs\             # local Python deps (gitignored, does not pollute system)
```

> Note: `pylibs\`, `dist\`, `build\`, `tools\` (InnoSetup) are large and gitignored; the release zip is uploaded separately as a Release asset.

## 6. Rebuild (for developers)

```bat
:: 1) deps are in pylibs; build the onedir (folder) version (less likely to trigger AV false positives than one-file)
pyinstaller --noconfirm --clean VoiceToText_onedir.spec

:: 2) build the installer (requires Inno Setup; iscc on PATH or full path)
iscc installer.iss
```

To troubleshoot launch issues, also build the console diagnostic version (`console=True`, double-click shows a black window with the real error):

```bat
pyinstaller --noconfirm --clean VoiceToText_console.spec
```
