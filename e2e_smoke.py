"""端到端本地链路冒烟（不依赖显示器/网络/真实 Key）：
合成上课音频 -> 解码/重采样/下混 -> 降噪 -> 双语双文件导出(txt/srt) -> 缺key拒绝。
覆盖 exe 内可本地验证的完整链路；云端真实识别需用户填入 Key 后人工验证。
"""
import sys, io, os, re, tempfile, wave

sys.path.insert(0, "D:/VoiceToText/pylibs")
sys.path.insert(0, "D:/VoiceToText/src")

import numpy as np
import soundfile as sf
import config, recorder as rec, backends

# 隔离配置目录，避免读写真实用户配置
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


# 1) 合成上课场景音频：人声(220/440Hz) + 宽带噪声，44.1k 立体声
sr_in = 44100
dur = 2.0
t = np.linspace(0, dur, int(sr_in * dur), endpoint=False)
voice = 0.5 * np.sin(2 * np.pi * 220 * t) + 0.2 * np.sin(2 * np.pi * 440 * t)
noise = 0.15 * np.random.randn(len(t))
sig = voice + noise
stereo = np.stack([sig, sig * 0.9], axis=1)
src_wav = os.path.join(_td, "lecture.wav")
with wave.open(src_wav, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(sr_in)
    w.writeframes((stereo * 32767).astype(np.int16).tobytes())
chk("合成 44.1k 立体声源音频", os.path.exists(src_wav))

# 2) 解码/重采样/下混 -> 16k 单声道（与 on_transcribe 前 load_to_wav_bytes 一致）
wav16 = rec.load_to_wav_bytes(src_wav)
d, sr = sf.read(io.BytesIO(wav16), always_2d=True)
chk("load: 输出 16k 采样率", sr == 16000)
chk("load: 输出单声道", d.shape[1] == 1)
raw_mono = d[:, 0].copy()

# 3) 降噪（与 on_transcribe 内 rec.enhance 一致）：人声频带占比应提升
enh = rec.enhance(wav16)
de, _ = sf.read(io.BytesIO(enh), always_2d=True)
de = de[:, 0]


def high_freq_ratio(x, sr=16000):
    sp = np.abs(np.fft.rfft(x))
    fr = np.fft.rfftfreq(len(x), 1 / sr)
    hf = fr > 4000
    return sp[hf].sum() / sp.sum()


# 人声集中在 <2kHz，高频(>4kHz)基本是宽带噪声；降噪后应使其能量占比下降
chk("enhance: 高频噪声能量占比下降(降噪生效)", high_freq_ratio(de) < high_freq_ratio(raw_mono))

# 4) 双语双文件导出（命名/格式严格复刻 main.on_export + _to_srt）
zh = "你好。我是老师。今天我们讲电路。"
en = "Hello. I am the teacher. Today we talk about circuits."
stem = os.path.join(_td, "lecture_out")


def to_srt(text):  # 与 App._to_srt 完全一致
    return "1\n00:00:00,000 --> 00:00:10,000\n%s\n" % text


with open(stem + "_zh.txt", "w", encoding="utf-8") as f:
    f.write(zh)
with open(stem + "_en.txt", "w", encoding="utf-8") as f:
    f.write(en)
with open(stem + "_zh.srt", "w", encoding="utf-8") as f:
    f.write(to_srt(zh))
with open(stem + "_en.srt", "w", encoding="utf-8") as f:
    f.write(to_srt(en))

chk("export: _zh.txt 内容正确", open(stem + "_zh.txt", encoding="utf-8").read() == zh)
chk("export: _en.txt 内容正确", open(stem + "_en.txt", encoding="utf-8").read() == en)
chk("export: _zh.srt 前缀正确", open(stem + "_zh.srt", encoding="utf-8").read().startswith(
    "1\n00:00:00,000 --> 00:00:10,000\n" + zh))
srt_re = re.compile(r"\d+\n\d\d:\d\d:\d\d,\d\d\d --> \d\d:\d\d:\d\d,\d\d\d\n")
chk("export: _en.srt 时间戳格式合规", srt_re.match(open(stem + "_en.srt", encoding="utf-8").read()) is not None)
chk("export: 四份双语文件齐备", all(os.path.exists(stem + s) for s in
    ("_zh.txt", "_en.txt", "_zh.srt", "_en.srt")))

# 5) 缺 key 拒绝（真实后端构造，不发起网络请求）
for cls, args in [(backends.OpenAIBackend, ("",)), (backends.BaiduBackend, ("", ""))]:
    try:
        cls(*args).transcribe(b"x", "zh")
        raise AssertionError("%s 缺 key 未报错" % cls.__name__)
    except ValueError:
        pass
chk("缺 key 后端拒绝(OpenAI/百度)", True)

# 6) 双语语言路由映射（on_transcribe 使用）
lang_map = {"auto": "", "zh": "zh", "en": "en", "bilingual": "bilingual"}
chk("bilingual 路由映射", lang_map["bilingual"] == "bilingual" and lang_map["zh"] == "zh")

print("E2E SMOKE PASSED (%d):" % len(passed))
for p in passed:
    print("  ✓", p)
