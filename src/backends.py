"""三个线上识别后端，统一接口 transcribe(wav_bytes, language, progress_cb) -> str"""
import io
import json
import base64
import uuid
import hmac
import hashlib
import time
import datetime
import urllib.request
import urllib.error
import urllib.parse

import websocket

from recorder import wav_to_pcm


# ----------------------------- 通用 HTTP 助手 -----------------------------
def _http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "VoiceToText/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def _http_post_json(url, body, timeout=60):
    data = body.encode("utf-8") if isinstance(body, str) else body
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "VoiceToText/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def _http_post_multipart(url, fields, files, headers, timeout=120):
    boundary = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += ("--%s\r\n" % boundary).encode()
        body += ('Content-Disposition: form-data; name="%s"\r\n\r\n' % k).encode()
        body += str(v).encode("utf-8") + b"\r\n"
    for name, (filename, data, ctype) in files.items():
        body += ("--%s\r\n" % boundary).encode()
        body += (
            'Content-Disposition: form-data; name="%s"; filename="%s"\r\n'
            % (name, filename)
        ).encode()
        body += ("Content-Type: %s\r\n\r\n" % ctype).encode()
        body += data + b"\r\n"
    body += ("--%s--\r\n" % boundary).encode()
    hdrs = dict(headers)
    hdrs["Content-Type"] = "multipart/form-data; boundary=%s" % boundary
    hdrs["Content-Length"] = str(len(body))
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


# ----------------------------- OpenAI Whisper -----------------------------
class OpenAIBackend:
    name = "OpenAI Whisper"

    def __init__(self, api_key):
        self.api_key = api_key or ""

    def transcribe(self, wav_bytes, language, progress_cb=None, **kwargs):
        if not self.api_key:
            raise ValueError("缺少 OpenAI API Key（设置 → OpenAI）")
        fields = {"model": "whisper-1"}
        if language:
            fields["language"] = language
        files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
        headers = {"Authorization": "Bearer %s" % self.api_key}
        if progress_cb:
            progress_cb("正在上传到 OpenAI ...")
        raw = _http_post_multipart(
            "https://api.openai.com/v1/audio/transcriptions",
            fields,
            files,
            headers,
            timeout=180,
        )
        data = json.loads(raw)
        return data.get("text", "")


# ----------------------------- 百度语音技术 -----------------------------
class BaiduBackend:
    name = "百度语音"

    def __init__(self, api_key, secret_key):
        self.api_key = api_key or ""
        self.secret_key = secret_key or ""

    def _get_token(self):
        url = (
            "https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials"
            "&client_id=%s&client_secret=%s" % (self.api_key, self.secret_key)
        )
        raw = _http_get(url, timeout=20)
        data = json.loads(raw)
        if "access_token" not in data:
            raise RuntimeError("百度获取 token 失败：%s" % data.get("error_description", raw))
        return data["access_token"]

    def transcribe(self, wav_bytes, language, progress_cb=None, **kwargs):
        if not self.api_key or not self.secret_key:
            raise ValueError("缺少百度 API Key / Secret Key（设置 → 百度）")
        if progress_cb:
            progress_cb("正在向百度获取 token ...")
        token = self._get_token()
        pcm = wav_to_pcm(wav_bytes)
        body = json.dumps(
            {
                "format": "pcm",
                "rate": 16000,
                "channel": 1,
                "speech": base64.b64encode(pcm).decode("ascii"),
                "len": len(pcm),
                "dev_pid": 1537,  # 普通话(混合) 带标点
            }
        )
        url = "https://vop.baidubce.com/server_api?dev_pid=1537&cuid=voicetotext&token=%s" % token
        if progress_cb:
            progress_cb("正在识别（百度，单次上限 60s）...")
        raw = _http_post_json(url, body, timeout=60)
        data = json.loads(raw)
        if data.get("err_no", -1) != 0:
            raise RuntimeError("百度错误 %s: %s" % (data.get("err_no"), data.get("err_msg")))
        return "".join(data.get("result", []))


# ----------------------------- 讯飞开放平台（语音听写 WebAPI） -----------------------------
class XunfeiBackend:
    name = "讯飞听写"

    def __init__(self, app_id, api_key, api_secret):
        self.app_id = app_id or ""
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""

    def _build_url(self):
        host = "iat-api.xfyun.cn"
        date = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        sign_origin = "host: %s\ndate: %s\nGET /v2/iat HTTP/1.1" % (host, date)
        signature = base64.b64encode(
            hmac.new(self.api_secret.encode(), sign_origin.encode(), hashlib.sha1).digest()
        ).decode()
        auth_origin = (
            'api_key="%s", algorithm="hmac-sha1", headers="host date request-line", signature="%s"'
            % (self.api_key, signature)
        )
        authorization = base64.b64encode(auth_origin.encode()).decode()
        return "wss://%s/v2/iat?authorization=%s&date=%s&host=%s" % (
            host,
            urllib.parse.quote(authorization),
            urllib.parse.quote(date),
            host,
        )

    def _frame(self, chunk, status):
        audio_b64 = base64.b64encode(chunk).decode("ascii") if chunk else ""
        lang = "en_us" if getattr(self, "_lang", "") == "en" else "zh_cn"
        if status == 0:
            body = {
                "common": {"app_id": self.app_id},
                "business": {
                    "language": lang,
                    "domain": "iat",
                    "accent": "mandarin",
                    "vad_eos": 10000,
                },
                "data": {
                    "status": 0,
                    "format": "audio/L16;rate=16000",
                    "encoding": "raw",
                    "audio": audio_b64,
                },
            }
        else:
            body = {
                "data": {
                    "status": status,
                    "format": "audio/L16;rate=16000",
                    "encoding": "raw",
                    "audio": audio_b64,
                }
            }
        return json.dumps(body)

    def transcribe(self, wav_bytes, language, progress_cb=None, **kwargs):
        if not all([self.app_id, self.api_key, self.api_secret]):
            raise ValueError("缺少讯飞 APPID / APIKey / APISecret（设置 → 讯飞）")
        self._lang = language or ""
        pcm = wav_to_pcm(wav_bytes)
        if progress_cb:
            progress_cb("正在连接讯飞 WebSocket ...")
        ws = websocket.create_connection(self._build_url(), timeout=30)
        chunk_size = 1280  # 40ms @ 16k*2bytes
        total = len(pcm)
        sent = 0
        # 第一帧（含首个音频块）
        first = pcm[:chunk_size] if total else b""
        ws.send(self._frame(first, status=0))
        sent = len(first)
        while sent < total:
            chunk = pcm[sent : sent + chunk_size]
            last = (sent + chunk_size) >= total
            ws.send(self._frame(chunk, status=2 if last else 1))
            sent += len(chunk)
        if progress_cb:
            progress_cb("正在识别（讯飞，单次上限 60s）...")
        result = []
        while True:
            try:
                msg = ws.recv()
            except websocket.WebSocketTimeoutException:
                break
            data = json.loads(msg)
            if data.get("code") != 0:
                ws.close()
                raise RuntimeError("讯飞错误 %s: %s" % (data.get("code"), data.get("message")))
            ws_arr = data.get("data", {}).get("ws")
            if ws_arr:
                for item in ws_arr:
                    for cw in item.get("cw", []):
                        result.append(cw.get("w", ""))
            if data.get("data", {}).get("status") == 2:
                break
        ws.close()
        return "".join(result)


# ----------------------------- 讯飞录音文件转写（LFASR，支持说话人分离） -----------------------------
class XunfeiLfasrBackend:
    name = "讯飞转写"
    supports_diarization = True  # 该后端可做说话人分离

    BASE = "https://raasr.xfyun.cn/api"
    SLICE_SIZE = 10 * 1024 * 1024  # 10MB/片

    def __init__(self, app_id, api_key, api_secret):
        self.app_id = app_id or ""
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""

    def _signa(self):
        ts = str(int(time.time()))
        base = (self.app_id + ts).encode("utf-8")
        md5s = hashlib.md5(base).hexdigest()
        signa = base64.b64encode(
            hmac.new(self.api_secret.encode("utf-8"), md5s.encode("utf-8"), hashlib.sha1).digest()
        ).decode("ascii")
        return signa, ts

    def _post_form(self, url, fields, timeout=30):
        body = urllib.parse.urlencode(fields).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _check(resp):
        if resp.get("ok", -1) != 0 or resp.get("err_no", -1) != 0:
            raise RuntimeError("讯飞转写错误 %s: %s" % (resp.get("err_no"), resp.get("failed")))

    def transcribe(
        self,
        wav_bytes,
        language,
        progress_cb=None,
        speaker_sep=False,
        speaker_number=2,
        timeout=1800,
    ):
        if not all([self.app_id, self.api_key, self.api_secret]):
            raise ValueError("缺少讯飞 APPID / APIKey / APISecret（设置 → 讯飞）")
        lf_lang = "en" if language == "en" else "cn"
        signa, ts = self._signa()
        auth = {"app_id": self.app_id, "signa": signa, "ts": ts}

        if progress_cb:
            progress_cb("讯飞转写：预处理任务…")
        prepare = self._post_form(
            self.BASE + "/prepare",
            {
                **auth,
                "file_len": str(len(wav_bytes)),
                "file_name": "audio.wav",
                "slice_num": str(max(1, (len(wav_bytes) + self.SLICE_SIZE - 1) // self.SLICE_SIZE)),
                "language": lf_lang,
                "has_seperate": "true" if speaker_sep else "false",
                "speaker_number": str(int(speaker_number)) if speaker_sep else "0",
                "role_type": "1" if speaker_sep else "0",
            },
        )
        self._check(prepare)
        task_id = prepare["data"]

        # 分片上传
        slices = [
            wav_bytes[i : i + self.SLICE_SIZE]
            for i in range(0, len(wav_bytes), self.SLICE_SIZE)
        ]
        gen = self._SliceIdGenerator()
        for idx, chunk in enumerate(slices):
            if progress_cb:
                progress_cb("讯飞转写：上传 %d/%d" % (idx + 1, len(slices)))
            self._check(
                json.loads(
                    _http_post_multipart(
                        self.BASE + "/upload",
                        {**auth, "task_id": task_id, "slice_id": gen.getNextSliceId()},
                        {"content": ("slice.bin", chunk, "application/octet-stream")},
                        {},
                        timeout=120,
                    )
                )
            )

        if progress_cb:
            progress_cb("讯飞转写：合并文件…")
        self._check(self._post_form(self.BASE + "/merge", {**auth, "task_id": task_id}))

        if progress_cb:
            progress_cb("讯飞转写：识别中…")
        deadline = time.time() + timeout
        while time.time() < deadline:
            prog = self._post_form(self.BASE + "/getProgress", {**auth, "task_id": task_id})
            self._check(prog)
            try:
                status = json.loads(prog["data"]).get("status", 0)
            except Exception:
                status = 0
            if status == 9:  # 结果已就绪
                break
            if status == 5:  # 转写完成
                break
            time.sleep(3)
        else:
            raise RuntimeError("讯飞转写超时（%d 秒）" % timeout)

        result = self._post_form(self.BASE + "/getResult", {**auth, "task_id": task_id})
        self._check(result)
        return self._parse_result(result["data"])

    @staticmethod
    def _parse_result(data_str):
        """LFASR 结果：JSON 数组 [{bg,ed,onebest,speaker,...}]。
        按 speaker 分组拼接，生成『说话人N：…』文本。"""
        try:
            arr = json.loads(data_str)
        except Exception:
            return data_str
        if isinstance(arr, dict):
            arr = arr.get("lattice", arr.get("data", []))
        if not isinstance(arr, list):
            return str(data_str)
        blocks = []
        cur_sp = None
        cur_buf = []
        for seg in arr:
            sp = seg.get("speaker", "0")
            txt = seg.get("onebest", "")
            if sp != cur_sp:
                if cur_buf:
                    blocks.append((cur_sp, "".join(cur_buf)))
                cur_sp = sp
                cur_buf = [txt]
            else:
                cur_buf.append(txt)
        if cur_buf:
            blocks.append((cur_sp, "".join(cur_buf)))
        lines = []
        for sp, txt in blocks:
            if sp in (None, "0", 0):
                lines.append(txt)
            else:
                lines.append("说话人%s：%s" % (sp, txt))
        return "\n".join(lines)

    class _SliceIdGenerator:
        def __init__(self):
            self._ch = "aaaaaaaaa`"

        def getNextSliceId(self):
            ch = self._ch
            j = len(ch) - 1
            while j >= 0:
                cj = ch[j]
                if cj != "z":
                    ch = ch[:j] + chr(ord(cj) + 1) + ch[j + 1 :]
                    break
                else:
                    ch = ch[:j] + "a" + ch[j + 1 :]
                    j -= 1
            self._ch = ch
            return self._ch


# ----------------------------- 工厂 -----------------------------
def make_backend(name, keys):
    if name == OpenAIBackend.name:
        return OpenAIBackend(keys["openai"]["api_key"])
    if name == BaiduBackend.name:
        return BaiduBackend(keys["baidu"]["api_key"], keys["baidu"]["secret_key"])
    if name == XunfeiBackend.name:
        return XunfeiBackend(
            keys["xunfei"]["app_id"],
            keys["xunfei"]["api_key"],
            keys["xunfei"]["api_secret"],
        )
    if name == XunfeiLfasrBackend.name:
        return XunfeiLfasrBackend(
            keys["xunfei"]["app_id"],
            keys["xunfei"]["api_key"],
            keys["xunfei"]["api_secret"],
        )
    raise ValueError("未知后端：%s" % name)


def backend_supports_diarization(name, keys):
    """该后端是否支持说话人分离（当前仅讯飞转写）。"""
    try:
        return bool(getattr(make_backend(name, keys), "supports_diarization", False))
    except Exception:
        return False

