"""录音与音频工具：麦克风录音(16k 单声道 WAV) + 任意音频文件解码为统一 WAV"""
import io
import math
import wave
import numpy as np
import sounddevice as sd
import soundfile as sf

SAMPLERATE = 16000
CHANNELS = 1
SAMPWIDTH = 2  # 16-bit


def list_microphones():
    try:
        devs = sd.query_devices()
        out = []
        for i, d in enumerate(devs):
            if d.get("max_input_channels", 0) > 0:
                out.append((i, d.get("name", f"设备{i}")))
        return out
    except Exception:
        return []


class Recorder:
    """简单的阻塞式录音器：start 开始，stop 返回 int16 音频数组。"""

    def __init__(self, samplerate=SAMPLERATE, channels=CHANNELS):
        self.samplerate = samplerate
        self.channels = channels
        self.frames = []
        self.stream = None
        self.recording = False

    def _callback(self, indata, frames, time_info, status):
        if self.recording:
            self.frames.append(indata.copy())

    def start(self, device=None):
        self.frames = []
        self.recording = True
        self.stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            dtype="int16",
            device=device,
            callback=self._callback,
        )
        self.stream.start()

    def stop(self):
        self.recording = False
        audio = np.zeros((0, self.channels), dtype="int16")
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        if self.frames:
            audio = np.concatenate(self.frames, axis=0)
        return audio

    @staticmethod
    def to_wav_bytes(audio, samplerate=SAMPLERATE, channels=CHANNELS):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(channels)
            w.setsampwidth(SAMPWIDTH)
            w.setframerate(samplerate)
            w.writeframes(audio.astype("int16").tobytes())
        return buf.getvalue()


def _resample_poly(x, up, down):
    """纯 numpy 抗混叠重采样（resample_poly 风格）：up=目标/down=源 采样率。
    不依赖 scipy/resampy，体积小，语音识别足够精确。"""
    x = np.asarray(x, dtype=np.float64).ravel()
    g = math.gcd(int(up), int(down))
    up, down = int(up) // g, int(down) // g
    # 抗混叠低通 FIR，截止 = 1/(2*max(up,down))（归一化到输出率）
    half_len = max(up, down) * 2
    n = np.arange(-half_len, half_len + 1, dtype=np.float64)
    h = np.sinc(2.0 * (0.5 / max(up, down)) * n)
    h *= 0.5 * (1.0 + np.cos(np.pi * n / (half_len + 1e-9)))  # Hann 窗
    h /= np.sum(h)
    # 上采样（插零）-> 卷积 -> 抽取
    x_up = np.zeros(len(x) * up, dtype=np.float64)
    x_up[::up] = x
    y = np.convolve(x_up, h, mode="full")
    delay = (len(h) - 1) // 2
    y = y[delay:]
    out = y[::down]
    target = int(round(len(x) * up / down))
    if len(out) > target:
        out = out[:target]
    return out


def load_to_wav_bytes(source):
    """把录音字节(bytes)或本地音频文件(路径)统一解码为 16k 单声道 WAV 字节。
    支持 wav/mp3/flac/m4a/ogg 等 soundfile 能读的格式（mp3 需系统有相关后端）。"""
    if isinstance(source, (bytes, bytearray)):
        data, sr = sf.read(io.BytesIO(bytes(source)), always_2d=True)
    else:
        data, sr = sf.read(str(source), always_2d=True)
    # 下混为单声道
    if data.shape[1] > 1:
        data = data.mean(axis=1)
    else:
        data = data[:, 0]
    # 重采样到 16k
    if sr != SAMPLERATE:
        data = _resample_poly(data, SAMPLERATE, sr)
    data = np.clip(data, -1.0, 1.0)
    data = (data * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(SAMPWIDTH)
        w.setframerate(SAMPLERATE)
        w.writeframes(data.tobytes())
    return buf.getvalue()


def wav_to_pcm(wav_bytes):
    """从 WAV 字节中提取裸 PCM（16-bit 小端），供百度/讯飞使用。"""
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        return w.readframes(w.getnframes())


# ----------------------------- 本地降噪增强 -----------------------------
def _spectral_gate(x, sr, n_fft=1024, hop=256, noise_quantile=0.1, gain_floor=0.02):
    """纯 numpy 频谱门控降噪：以分位数为噪声基底，抑制低于噪声门的频点；
    同时把 <80Hz 的隆隆声（教室/会议室空调、风扇）置零。返回与 x 等长数组。"""
    if len(x) < n_fft:
        return x
    x = np.asarray(x, dtype=np.float64).ravel()
    window = np.hanning(n_fft)
    n = len(x)
    n_frames = 1 + (n - n_fft) // hop
    if n_frames < 2:
        return x
    # 加半窗长的零填充，保证重叠相加无缝
    pad = n_fft // 2
    xp = np.concatenate([np.zeros(pad), x, np.zeros(pad)])
    frames = np.stack([xp[i * hop : i * hop + n_fft] * window for i in range(n_frames)])
    spec = np.fft.rfft(frames, n=n_fft, axis=1)
    mag = np.abs(spec)
    # 噪声基底：每个频点取时间维低分位（安静段能量低）
    noise = np.quantile(mag, noise_quantile, axis=0, keepdims=True)
    threshold = noise * 3.0  # 约 9.5dB 高于噪声门
    gain = np.clip(mag / (threshold + 1e-9), 0.0, 1.0)
    gain = np.power(gain, 1.5)  # 软门限，避免过度切割
    gain = np.maximum(gain, gain_floor)  # 不完全静音，保留少量混响
    spec_g = spec * gain
    # <80Hz 高通：去掉低频隆隆
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    spec_g[:, freqs < 80.0] = 0.0
    # 逆 STFT 重叠相加
    out = np.zeros(len(xp))
    norm = np.zeros(len(xp))
    for i in range(n_frames):
        frame = np.fft.irfft(spec_g[i], n=n_fft)
        out[i * hop : i * hop + n_fft] += frame * window
        norm[i * hop : i * hop + n_fft] += window * window
    norm = np.where(norm < 1e-9, 1.0, norm)
    y = out / norm
    return y[pad : pad + n]


def enhance(wav_bytes):
    """对 16k 单声道 WAV 字节做本地降噪增强，返回新的 WAV 字节。
    异常时回退为原始音频，保证识别流程不中断。"""
    try:
        data, sr = sf.read(io.BytesIO(bytes(wav_bytes)), always_2d=True)
        if data.shape[1] > 1:
            data = data.mean(axis=1)
        x = data.ravel().astype(np.float64)
        y = _spectral_gate(x, sr)
        y = np.clip(y, -1.0, 1.0)
        out = (y * 32767.0).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(SAMPWIDTH)
            w.setframerate(sr)
            w.writeframes(out.tobytes())
        return buf.getvalue()
    except Exception:
        return wav_bytes
