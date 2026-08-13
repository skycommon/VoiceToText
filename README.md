# 语音转文字 VoiceToText（Windows）

[![GitHub release](https://img.shields.io/github/v/release/skycommon/VoiceToText)](https://github.com/skycommon/VoiceToText/releases)
[![GitHub downloads](https://img.shields.io/github/downloads/skycommon/VoiceToText/total)](https://github.com/skycommon/VoiceToText/releases)
[![Platform](https://img.shields.io/badge/platform-Windows-blue)](https://github.com/skycommon/VoiceToText)

> **下载**：前往 [Releases](https://github.com/skycommon/VoiceToText/releases) 下载 `VoiceToText-1.0.0-windows.zip`，解压后双击 `VoiceToText-Setup-1.0.0.exe` 安装即可。

**English documentation**: [README_EN.md](README_EN.md)

本地轻量 GUI，录音 / 选音频文件 → 线上高精度识别 → 文字实时显示、可复制、可导出 `txt` / `srt` 字幕。
面向**上课录音、开会录音**场景：内置本地降噪增强（频谱门控 + 高通去环境隆隆声），支持**说话人分离**（区分谁在说话），并可将同一段音频同时转写成**简体中文 + 英文两份独立文件**。
本地只跑界面、录音与降噪，识别走线上服务，所以安装包体积小（约 27 MB），中文识别精度高。

## 一、安装

- **安装包（推荐，Release 中提供）**：下载 Release 里的 `VoiceToText-1.0.0-windows.zip`，解压得到 `VoiceToText-Setup-1.0.0.exe`，双击按向导安装（默认装到用户程序目录，无需管理员权限）。会创建开始菜单与桌面快捷方式。
- 也可自行从源码构建（见「六、重新打包」），构建产物位于 `dist\`。

> 若首次启动报错“缺少 vcruntime140.dll / api-ms-win-crt-*.dll”，请安装
> [Visual C++ 2015–2022 运行库](https://learn.microsoft.com/zh-CN/cpp/windows/latest-supported-vc-redist)。
> Windows 10/11 多数已自带。

## 二、配置识别后端（必做）

首次打开后，点「设置」填入对应服务的密钥并保存。**哪家有 Key 用哪家**，三者可随时在界面下拉切换。

### 1. OpenAI Whisper API（最简单，多语种强）
- 需要：`api_key`（OpenAI 账号的 Secret Key）
- 申请：https://platform.openai.com/api-keys
- 计费：按量，约 $0.006 / 分钟音频

### 2. 百度语音技术（中文好，免费额度大）
- 需要：`API Key` + `Secret Key`
- 申请：https://console.bce.baidu.com/ → 语音技术 → 创建应用
- 免费额度：每月一定量免费调用

### 3. 讯飞开放平台（中文识别最准，且支持说话人分离）
- 需要：`APPID` + `APIKey` + `APISecret`
- 申请：https://www.xfyun.cn/ → 控制台 → 创建应用
- **两种服务**：
  - **语音听写**（实时短音频，不支持说话人分离）：用于快速单语转写。
  - **录音文件转写（LFASR）**：用于上课/开会长音频，支持**说话人分离**（区分 A/B/C 说话人）。
    **「区分说话人」功能必须用这个后端，且需在讯飞控制台为应用开通「录音文件转写」服务。**
- 免费额度：每日/每月免费调用次数

密钥保存在本机 `%APPDATA%\VoiceToText\config.json`（明文，仅本机使用，请勿分享）。

## 三、使用

1. 顶部「识别后端」下拉选择已配置的服务。默认「讯飞转写」（支持说话人分离）。
2. **界面语言**（中文 / English）：顶部「界面语言」下拉切换，整个界面文案即时切换，下次启动自动记忆。
3. **主题**（亮色 / 暗色 / 随系统）：顶部「主题」下拉切换。选「随系统」时跟随 Windows 深色模式设置（亮度需在系统「设置 → 个性化 → 颜色 → 选择默认应用模式」中调整）；切换即时生效并记忆。
4. **音频增强（降噪）**：勾选后，发送识别前本地做一次轻量降噪（频谱门控 + 80Hz 高通，去除教室/会议室空调、风扇等背景噪音）。默认可用，关掉则原样发送。
5. **区分说话人**：仅「讯飞转写」后端可用（其它后端自动置灰）。勾选后，转写结果按说话人分段，形如 `说话人1：……` `说话人2：……`。开会时建议同时设置「设置 → 说话人数量」。
6. **语言**：选「中文 / 英文 / 自动」做单语转写；选**「双语(中+英)」**则同一段音频分别生成**纯中文**与**纯英文**两份结果。
7. **录音**：点「开始录音」→ 说话 → 点「停止录音」，自动上传识别，结果出现在下方文本框。
8. **文件转写**：点「选择音频文件」，支持 `wav / mp3 / flac / m4a` 等常见格式，自动转成识别所需格式（16k 单声道）后发送。
9. **结果处理**：
   - 点「复制」复制文本框内容（双语时复制的是中文稿）；
   - 点「导出 txt / 导出 srt」保存。
     - 单语：保存为一份文件；
     - **双语：弹出一次保存框，自动生成 `基名_zh.txt` / `基名_zh.srt` 与 `基名_en.txt` / `基名_en.srt` 两份独立文件**。
10. 点「清空」清空当前文本。

## 四、设计说明

- **精度 vs 体积**：识别由线上服务完成（讯飞 / 百度 / OpenAI 均为高精度大模型），本地不含语音模型，因此安装包仅约 27 MB，远小于本地 Whisper 模型（数百 MB～GB 级）。
- **本地降噪**：「音频增强」用纯 numpy 实现的频谱门控 + 80Hz 高通，零额外依赖、体积不变，可在识别前抑制教室/会议室背景噪音。
- **说话人分离**：依赖讯飞「录音文件转写（LFASR）」服务的 `speaker` 字段；其它后端无此能力。
- **离线能力**：本工具需联网调用识别服务；纯离线场景不适用。
- **隐私**：音频仅发送至你选择的后端服务，本地不留存识别内容（导出文件除外）。

## 五、目录结构（开发用）

```
D:\VoiceToText\
├─ src\
│  ├─ main.py          # tkinter 主界面
│  ├─ recorder.py      # 录音 / 文件导入 / 格式转换
│  ├─ backends.py      # 线上识别后端（OpenAI / 百度 / 讯飞听写 / 讯飞转写-LFASR）
│  ├─ config.py        # 密钥与配置读写
│  ├─ i18n.py          # 界面多语言（中文 / English）
│  └─ app_icon.ico     # 应用图标
├─ dist\
│  ├─ VoiceToText\                      # 文件夹版（onedir）构建产物
│  └─ VoiceToText-Setup-1.0.0.exe       # 安装包（由 installer.iss 生成）
├─ installer.iss       # Inno Setup 安装脚本
├─ VoiceToText_onedir.spec   # 文件夹版打包配置
├─ VoiceToText_console.spec  # 控制台诊断版打包配置
├─ gen_icon.py        # 应用图标生成脚本
├─ make_shortcut.py   # 桌面快捷方式生成脚本
├─ test_core.py / test_core2.py / e2e_smoke.py  # 本地自动化测试
└─ pylibs\             # 本地 Python 依赖（不污染系统，已 gitignore）
```

> 注：`pylibs\`、`dist\`、`build\`、`tools\`（InnoSetup 安装器）体积较大，已加入 `.gitignore`，不随源码入库；发布用的 zip 单独作为 Release 资源。

## 六、重新打包（开发）

```bat
:: 1) 依赖已装到 pylibs；用 onedir spec 打包（文件夹版，比单文件更不易被杀软误报）
pyinstaller --noconfirm --clean VoiceToText_onedir.spec

:: 2) 生成安装包（需 Inno Setup，iscc 在 PATH 或指定完整路径）
iscc installer.iss
```

若需要排查启动问题，可额外构建控制台诊断版（`console=True`，双击弹黑窗打印真实报错）：

```bat
pyinstaller --noconfirm --clean VoiceToText_console.spec
```
