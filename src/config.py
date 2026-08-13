"""配置持久化：后端选择、语言、各家 API Key 存到 %APPDATA%\\VoiceToText\\config.json"""
import os
import json

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "VoiceToText")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

BACKENDS = ["讯飞转写", "讯飞听写", "百度语音", "OpenAI Whisper"]
LANGUAGES = [("自动", "auto"), ("中文", "zh"), ("英文", "en"), ("双语(中+英)", "bilingual")]

DEFAULT_CONFIG = {
    "backend": "讯飞转写",
    "language": "bilingual",
    "ui_lang": "zh",
    "theme": "system",
    "audio_enhance": True,
    "speaker_sep": True,
    "speaker_number": 2,
    "keys": {
        "xunfei": {"app_id": "", "api_key": "", "api_secret": ""},
        "baidu": {"api_key": "", "secret_key": ""},
        "openai": {"api_key": ""},
    },
}


def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = dict(DEFAULT_CONFIG)
        cfg.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
        for grp in DEFAULT_CONFIG["keys"]:
            cfg["keys"].setdefault(grp, {})
            cfg["keys"][grp].update(data.get("keys", {}).get(grp, {}))
        return cfg
    except Exception:
        return json.loads(json.dumps(DEFAULT_CONFIG))


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_key(group, field):
    return load_config()["keys"].get(group, {}).get(field, "")


def set_key(group, field, value):
    cfg = load_config()
    cfg["keys"].setdefault(group, {})[field] = value
    save_config(cfg)


def set_ui_lang(value):
    cfg = load_config()
    cfg["ui_lang"] = value
    save_config(cfg)


def set_theme(value):
    cfg = load_config()
    cfg["theme"] = value
    save_config(cfg)


def set_audio_enhance(value):
    cfg = load_config()
    cfg["audio_enhance"] = bool(value)
    save_config(cfg)


def set_speaker_sep(value):
    cfg = load_config()
    cfg["speaker_sep"] = bool(value)
    save_config(cfg)


def set_speaker_number(value):
    cfg = load_config()
    try:
        v = max(0, min(10, int(value)))
    except Exception:
        v = 2
    cfg["speaker_number"] = v
    save_config(cfg)
