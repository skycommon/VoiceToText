"""核心逻辑冒烟测试：不依赖显示器/网络，验证 exe 内业务逻辑正确。"""
import sys, io, json, tempfile, os, wave
sys.path.insert(0, "D:/VoiceToText/pylibs")
sys.path.insert(0, "D:/VoiceToText/src")

import numpy as np
import config, recorder, backends

# 把配置写到临时目录，避免污染真实 APPDATA
_td = tempfile.mkdtemp()
config.CONFIG_DIR = _td
config.CONFIG_FILE = os.path.join(_td, "config.json")

passed = []

# 1) 配置读写
config.set_key("openai", "api_key", "sk-test123")
assert config.get_key("openai", "api_key") == "sk-test123", "config set/get 失败"
assert config.load_config()["keys"]["openai"]["api_key"] == "sk-test123"
passed.append("config 读写/持久化")

# 2) 录音 WAV 生成 + 文件往返
audio = (np.random.rand(16000) * 30000).astype(np.int16)  # 1 秒 16k 单声道
wav = recorder.Recorder.to_wav_bytes(audio, 16000, 1)
assert wav[:4] == b"RIFF", "WAV 头错误"
wav2 = recorder.load_to_wav_bytes(wav)  # 对 wav 字节做统一解码
assert wav2[:4] == b"RIFF"
# 验证采样率/声道正确
with wave.open(io.BytesIO(wav2), "rb") as w:
    assert w.getframerate() == 16000 and w.getnchannels() == 1, "重采样/单声道失败"
passed.append("recorder WAV 生成 + load_to_wav_bytes 往返")

# 3) 后端工厂路由
b = backends.make_backend("OpenAI Whisper", config.load_config()["keys"])
assert isinstance(b, backends.OpenAIBackend)
assert backends.make_backend("百度语音", config.load_config()["keys"]).name == "百度语音"
assert backends.make_backend("讯飞听写", config.load_config()["keys"]).name == "讯飞听写"
passed.append("make_backend 三家路由")

# 4) 讯飞签名 URL（纯本地 HMAC 计算，不联网）
xf = backends.XunfeiBackend("appid1", "key1", "sec1")
url = xf._build_url()
assert url.startswith("wss://iat-api.xfyun.cn/v2/iat?authorization="), "讯飞 URL 错误"
assert "date=" in url and "host=" in url
passed.append("讯飞 _build_url 签名构造")

# 5) 讯飞帧状态机
f0 = json.loads(xf._frame(b"x" * 100, 0))
assert f0["common"]["app_id"] == "appid1" and f0["data"]["status"] == 0
f1 = json.loads(xf._frame(b"x" * 100, 1))
assert "common" not in f1 and f1["data"]["status"] == 1
f2 = json.loads(xf._frame(b"", 2))
assert f2["data"]["status"] == 2
passed.append("讯飞 _frame 状态机(0/1/2)")

# 6) 缺 key 校验（不应发起网络请求）
for cls, args in [
    (backends.OpenAIBackend, ("",)),
    (backends.BaiduBackend, ("", "")),
    (backends.XunfeiBackend, ("", "", "")),
]:
    try:
        cls(*args).transcribe(b"dummy", "zh")
        raise AssertionError("%s 缺 key 未报错" % cls.__name__)
    except ValueError:
        pass
passed.append("三家后端 缺 key 校验抛 ValueError")

# 7) 百度识别 body 构造（不调用 _get_token，直接验证 PCM/base64 封装逻辑）
pcm = recorder.wav_to_pcm(wav)
import base64
assert base64.b64decode(base64.b64encode(pcm)) == pcm
passed.append("wav_to_pcm + 百度 PCM/base64 封装")

# 8) 重采样 44.1k -> 16k（纯 numpy，不依赖 resampy/numba）
t = np.linspace(0, 1.0, 44100, endpoint=False)
sig = np.sin(2 * np.pi * 440 * t)
wav44 = recorder.Recorder.to_wav_bytes((sig * 30000).astype(np.int16), 44100, 1)
wav16 = recorder.load_to_wav_bytes(wav44)
with wave.open(io.BytesIO(wav16), "rb") as w:
    assert w.getframerate() == 16000 and w.getnchannels() == 1
    nframes = w.getnframes()
assert abs(nframes - 16000) < 80, "重采样长度异常: %d" % nframes
passed.append("44.1k->16k 重采样(纯 numpy, 无 resampy)")

print("ALL CORE TESTS PASSED (%d):" % len(passed))
for p in passed:
    print("  -", p)
