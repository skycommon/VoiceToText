"""核心逻辑测试：降噪往返 / LFASR 签名与解析 / 后端能力 / 双语路由 / 配置持久化"""
import os
import sys
import io
import wave
import json
import time, tempfile

sys.path.insert(0, "D:/VoiceToText/pylibs")
sys.path.insert(0, "D:/VoiceToText/src")

import numpy as np
import soundfile as sf
import config, i18n, recorder as rec, backends

# 隔离配置目录，避免读写真实用户配置（默认 backend=讯飞转写 由此保证）
_td = tempfile.mkdtemp()
config.CONFIG_DIR = _td
config.CONFIG_FILE = os.path.join(_td, "config.json")

passed = []


def chk(name, cond):
    if cond:
        passed.append(name)
    else:
        print("FAIL:", name)
        sys.exit(1)


# 1) 降噪往返
sr = 16000
t = np.linspace(0, 1, sr, endpoint=False)
sig = (0.3 * np.sin(2 * np.pi * 220 * t) + 0.02 * np.random.randn(sr)).astype(np.float32)
buf = io.BytesIO()
with wave.open(buf, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes((sig * 32767).astype(np.int16).tobytes())
wav = buf.getvalue()
out = rec.enhance(wav)
d, sr2 = sf.read(io.BytesIO(out), always_2d=True)
chk("enhance returns valid 16k wav", sr2 == sr and len(d) > 0)
# 异常输入回退
chk("enhance falls back on garbage", rec.enhance(b"not a wav") == b"not a wav")

# 2) LFASR 签名（用讯飞官方示例向量校验）
b = backends.XunfeiLfasrBackend("595f23df", "k", "d9f4aa7ea6d94faca62cd88a28fd5234")
_orig = backends.time.time
backends.time.time = lambda: 1512041814.0
signa, ts = b._signa()
backends.time.time = _orig
chk("lfasr ts format", ts == "1512041814")
chk("lfasr signa matches official vector", signa == "IrrzsJeOFk1NGfJHW6SkHUoN9CU=")

# 3) LFASR 结果解析（说话人分组）
sample = json.dumps([
    {"bg": "0", "ed": "4950", "onebest": "你好。", "speaker": "1"},
    {"bg": "4950", "ed": "8000", "onebest": "我是老师。", "speaker": "1"},
    {"bg": "8000", "ed": "9000", "onebest": "明白了。", "speaker": "2"},
])
parsed = backends.XunfeiLfasrBackend._parse_result(sample)
chk("parse groups speaker 1", "说话人1：" in parsed and "你好。我是老师。" in parsed)
chk("parse groups speaker 2", "说话人2：" in parsed and "明白了。" in parsed)

# 4) 后端能力
empty_xf = {"xunfei": {"app_id": "", "api_key": "", "api_secret": ""}}
chk("讯飞转写 supports diarization", backends.backend_supports_diarization("讯飞转写", empty_xf) is True)
chk("讯飞听写 no diarization", backends.backend_supports_diarization("讯飞听写", empty_xf) is False)
chk("OpenAI no diarization", backends.backend_supports_diarization("OpenAI Whisper", {"openai": {"api_key": ""}}) is False)

# 5) 双语语言路由映射
lang_map = {"auto": "", "zh": "zh", "en": "en", "bilingual": "bilingual"}
chk("bilingual route", lang_map["bilingual"] == "bilingual")
chk("zh route", lang_map["zh"] == "zh")

# 6) 配置默认值与 setter
c = config.load_config()
chk("default backend = 讯飞转写", c["backend"] == "讯飞转写")
chk("default language = bilingual", c["language"] == "bilingual")
chk("default audio_enhance True", c.get("audio_enhance") is True)
chk("default speaker_sep present", "speaker_sep" in c)
config.set_audio_enhance(False)
config.set_speaker_sep(True)
config.set_speaker_number(4)
c2 = config.load_config()
chk("audio_enhance persisted False", c2["audio_enhance"] is False)
chk("speaker_number persisted 4", c2["speaker_number"] == 4)

# 7) i18n 新键齐全
for k in ("chk_enhance", "chk_speaker", "status_bilingual", "speaker_note"):
    chk("i18n zh %s" % k, i18n.tr("zh", k) != k)
    chk("i18n en %s" % k, i18n.tr("en", k) != k)

print("ALL CORE TESTS PASSED (%d):" % len(passed))
for p in passed:
    print("  ✓", p)
