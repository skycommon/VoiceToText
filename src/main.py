"""语音转文字 — 主界面（tkinter）
功能：麦克风录音 / 选择音频文件 → 线上识别（讯飞/百度/OpenAI 可切换）→ 文字展示、复制、导出。
支持：界面语言（中文/English）切换、主题（亮色/暗色/随系统）切换。
"""
import os
import sys
import io
import threading
import datetime
import traceback
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

import config as cfg
import recorder as rec
from backends import make_backend, backend_supports_diarization
import i18n

APP_NAME = "语音转文字"
VERSION = "1.0.0"


def _crash_log(extype, value, tb):
    """把未捕获异常写到 exe 同目录 crash.log，方便用户反馈启动/运行错误。"""
    try:
        base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
            else os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base, "crash.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write("=== crash %s ===\n" % datetime.datetime.now().isoformat())
            traceback.print_exception(extype, value, tb, file=f)
    except Exception:
        pass


sys.excepthook = _crash_log


def resource_path(rel):
    """PyInstaller 打包后定位资源；开发期返回源码同目录。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


class SettingsWindow(tk.Toplevel):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.title(self.app.tr("settings_title"))
        self.geometry("420x260")
        self.resizable(False, False)
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        # 不再 grab_set：让窗口可自由移动，同时仍保持置顶
        self.keys = {
            g: dict(cfg.load_config()["keys"].get(g, {}))
            for g in ("xunfei", "baidu", "openai")
        }
        self.entries = {}
        self._build_ui()
        self._apply_theme_to_settings()
        self.after(10, self._center_on_parent)

    def _apply_theme_to_settings(self):
        """让设置窗口背景跟随当前亮/暗主题，避免默认灰底不协调。"""
        dark = getattr(self.app, "_is_dark", False)
        bg = "#2b2b2b" if dark else "#f5f5f5"
        self.configure(bg=bg)

    def _center_on_parent(self):
        """将设置窗口居中显示在主窗口上，避免卡在左上角。"""
        self.update_idletasks()
        parent = self.app
        if parent:
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            px = parent.winfo_x()
            py = parent.winfo_y()
        else:
            pw, ph, px, py = self.winfo_screenwidth(), self.winfo_screenheight(), 0, 0
        w = self.winfo_width()
        h = self.winfo_height()
        # 留 24px 上边距，避免贴到屏幕顶部/任务栏导致标题栏拖不动
        x = max(24, px + (pw - w) // 2)
        y = max(24, py + (ph - h) // 2)
        self.geometry("+%d+%d" % (x, y))
        self.deiconify()
        self.lift()
        self.focus_force()

    def _build_ui(self):
        # 选择要配置的后端
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(top, text=self.app.tr("label_config_backend")).pack(side="left")
        self.backend_var = tk.StringVar(value=self.app.backend_var.get())
        self.backend_cb = ttk.Combobox(
            top, textvariable=self.backend_var, values=cfg.BACKENDS, state="readonly", width=16
        )
        self.backend_cb.pack(side="left", padx=(6, 0))
        self.backend_cb.bind("<<ComboboxSelected>>", lambda e: self._render_fields())

        self.fields_frame = ttk.Frame(self)
        self.fields_frame.pack(fill="both", expand=True, padx=12, pady=8)

        self.save_btn = ttk.Button(self, text=self.app.tr("btn_save"), command=self.on_save)
        self.save_btn.pack(pady=(0, 6))

        self.note_label = ttk.Label(
            self, text=self.app.tr("settings_note"), foreground="#666", wraplength=380
        )
        self.note_label.pack(pady=(0, 10))

        self._render_fields()

    def _render_fields(self):
        """根据下拉选择的后端，只渲染对应一家的输入框。"""
        for w in self.fields_frame.winfo_children():
            w.destroy()
        self.entries.clear()

        backend = self.backend_var.get()
        if backend in ("讯飞听写", "讯飞转写"):
            group = "xunfei"
            title = self.app.tr("sec_xunfei")
            fields = [("app_id", "APPID"), ("api_key", "APIKey"), ("api_secret", "APISecret")]
        elif backend == "百度语音":
            group = "baidu"
            title = self.app.tr("sec_baidu")
            fields = [("api_key", "API Key"), ("secret_key", "Secret Key")]
        else:  # OpenAI Whisper
            group = "openai"
            title = self.app.tr("sec_openai")
            fields = [("api_key", "API Key")]

        ttk.Label(self.fields_frame, text=title, font=("微软雅黑", 10, "bold")).pack(
            anchor="w", pady=(4, 6)
        )
        for key, label in fields:
            row = ttk.Frame(self.fields_frame)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, width=12).pack(side="left")
            e = ttk.Entry(row, width=36, show="*")
            e.insert(0, self.keys.get(group, {}).get(key, ""))
            e.pack(side="left", padx=(6, 0), fill="x", expand=True)
            self.entries[(group, key)] = e

    def on_save(self):
        for (group, key), e in self.entries.items():
            cfg.set_key(group, key, e.get())
        messagebox.showinfo(self.app.tr("msg_saved"), self.app.tr("msg_saved_body"), parent=self)
        self.destroy()


class App:
    def __init__(self, root):
        self.root = root
        c = cfg.load_config()
        self.ui_lang_var = tk.StringVar(value=c.get("ui_lang", "zh"))
        self.theme_var = tk.StringVar(value=c.get("theme", "system"))
        self.backend_var = tk.StringVar(value=c["backend"])
        self.lang_var = tk.StringVar(value=c["language"])
        self.enhance_var = tk.BooleanVar(value=bool(c.get("audio_enhance", True)))
        self.speaker_var = tk.BooleanVar(value=bool(c.get("speaker_sep", False)))
        self.bilingual = None  # (zh_text, en_text) 双语结果
        self.recorder = None
        self.current_wav = None
        self.busy = False
        self._recording = False
        self._i18n = []            # (widget, key, kind)
        self._status_key = None
        self._status_args = ()

        # ui_lang / theme 下拉的显示名 -> 编码 映射
        self._ui_lang_map = {}
        self._theme_map = {}

        self.root.geometry("720x560")
        try:
            self.root.iconbitmap(resource_path("app_icon.ico"))
        except Exception:
            pass

        self._build_ui()
        self._populate_combos()
        self._update_speaker_state()
        self.apply_theme()
        self.refresh_texts()
        self._set_status("status_ready")

    # ----------------------------- i18n -----------------------------
    def tr(self, key, *args):
        return i18n.tr(self.ui_lang_var.get(), key, *args)

    def _reg(self, widget, key, kind="label"):
        self._i18n.append((widget, key, kind))
        widget.configure(text=self.tr(key))

    def refresh_texts(self):
        for w, key, kind in self._i18n:
            w.configure(text=self.tr(key))
        self._update_record_btn()
        self.root.title("%s v%s" % (self.tr("app_title"), VERSION))
        # 重渲染状态栏文案
        if self._status_key:
            self.status.set(self.tr(self._status_key, *self._status_args))

    # ----------------------------- 主题 -----------------------------
    def _system_is_dark(self):
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return val == 0
        except Exception:
            return False

    def apply_theme(self):
        theme = self.theme_var.get()
        dark = self._system_is_dark() if theme == "system" else (theme == "dark")
        self._is_dark = dark
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        if dark:
            bg, fg = "#2b2b2b", "#e6e6e6"
            field_bg, sel = "#3a3a3a", "#264f78"
        else:
            bg, fg = "#f5f5f5", "#222222"
            field_bg, sel = "#ffffff", "#cce4ff"
        style.configure(".", background=bg, foreground=fg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", background=field_bg, foreground=fg)
        style.configure("TCombobox", fieldbackground=field_bg, background=bg, foreground=fg)
        style.configure("TEntry", fieldbackground=field_bg, foreground=fg)
        style.map("TCombobox", fieldbackground=[("readonly", field_bg)])
        self.root.configure(bg=bg)
        self.text.configure(bg=field_bg, fg=fg, insertbackground=fg, selectbackground=sel)
        for chk in (self.chk_enhance, self.chk_speaker):
            chk.configure(
                bg=bg, fg=fg, selectcolor=field_bg,
                activebackground=bg, activeforeground=fg,
                disabledforeground="#888" if dark else "#888",
            )
        self._set_windows_dark_title(dark)

    def _set_windows_dark_title(self, dark):
        try:
            import ctypes
            hwnd = self.root.winfo_id()
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            value = ctypes.c_int(1 if dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value), ctypes.sizeof(value),
            )
        except Exception:
            pass

    # ----------------------------- 下拉选项 -----------------------------
    def _ui_lang_options(self):
        if self.ui_lang_var.get() == "en":
            return [("zh", "中文"), ("en", "English")]
        return [("zh", "中文"), ("en", "English")]

    def _theme_options(self):
        if self.ui_lang_var.get() == "en":
            return [("light", "Light"), ("dark", "Dark"), ("system", "System")]
        return [("light", "亮色"), ("dark", "暗色"), ("system", "随系统")]

    def _populate_combos(self):
        ui_opts = self._ui_lang_options()
        self._ui_lang_map = {d: c for c, d in ui_opts}
        self.ui_lang_cb["values"] = [d for _, d in ui_opts]
        cur = self.ui_lang_var.get()
        for c, d in ui_opts:
            if c == cur:
                self.ui_lang_cb.set(d)

        th_opts = self._theme_options()
        self._theme_map = {d: c for c, d in th_opts}
        self.theme_cb["values"] = [d for _, d in th_opts]
        cur_t = self.theme_var.get()
        for c, d in th_opts:
            if c == cur_t:
                self.theme_cb.set(d)

    def on_ui_lang(self, e):
        disp = self.ui_lang_cb.get()
        code = self._ui_lang_map.get(disp, "zh")
        if code == self.ui_lang_var.get():
            return
        self.ui_lang_var.set(code)
        cfg.set_ui_lang(code)
        self._populate_combos()
        self.refresh_texts()

    def on_theme(self, e):
        disp = self.theme_cb.get()
        code = self._theme_map.get(disp, "system")
        if code == self.theme_var.get():
            return
        self.theme_var.set(code)
        cfg.set_theme(code)
        self.apply_theme()

    # ----------------------------- UI -----------------------------
    def _build_ui(self):
        f = ttk.Frame(self.root, padding=10)
        f.pack(fill="x")

        # 第一行：识别引擎 / 识别语言 / 设置 Key
        self.lbl_engine = ttk.Label(f, text="")
        self._reg(self.lbl_engine, "label_engine")
        self.lbl_engine.grid(row=0, column=0, sticky="e", padx=4)
        cb = ttk.Combobox(
            f, textvariable=self.backend_var, values=cfg.BACKENDS, state="readonly", width=14
        )
        cb.grid(row=0, column=1, padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self._save_backend())

        self.lbl_asr = ttk.Label(f, text="")
        self._reg(self.lbl_asr, "label_asr_lang")
        self.lbl_asr.grid(row=0, column=2, sticky="e", padx=4)
        lang_cb = ttk.Combobox(
            f,
            textvariable=self.lang_var,
            values=[l[0] for l in cfg.LANGUAGES],
            state="readonly",
            width=10,
        )
        lang_cb.grid(row=0, column=3, padx=4)
        lang_cb.bind("<<ComboboxSelected>>", lambda e: self._save_lang())

        self.btn_settings = ttk.Button(f, text="", command=self._open_settings)
        self._reg(self.btn_settings, "btn_settings")
        self.btn_settings.grid(row=0, column=4, padx=8)

        # 第二行：界面语言 / 主题
        self.lbl_ui_lang = ttk.Label(f, text="")
        self._reg(self.lbl_ui_lang, "label_ui_lang")
        self.lbl_ui_lang.grid(row=1, column=0, sticky="e", padx=4)
        self.ui_lang_cb = ttk.Combobox(f, state="readonly", width=10)
        self.ui_lang_cb.grid(row=1, column=1, padx=4)
        self.ui_lang_cb.bind("<<ComboboxSelected>>", self.on_ui_lang)

        self.lbl_theme = ttk.Label(f, text="")
        self._reg(self.lbl_theme, "label_theme")
        self.lbl_theme.grid(row=1, column=2, sticky="e", padx=4)
        self.theme_cb = ttk.Combobox(f, state="readonly", width=10)
        self.theme_cb.grid(row=1, column=3, padx=4)
        self.theme_cb.bind("<<ComboboxSelected>>", self.on_theme)

        # 第三行：音频增强 / 区分说话人
        # 用 tk.Checkbutton 避免 ttk 在某些主题下把勾选显示成 ❌
        self.chk_enhance = tk.Checkbutton(
            f, text="", variable=self.enhance_var, command=self._on_enhance,
            font=("微软雅黑", 10), bg="#f5f5f5", fg="#222222",
            selectcolor="#ffffff", activebackground="#f5f5f5",
            activeforeground="#222222", highlightthickness=0,
        )
        self._reg(self.chk_enhance, "chk_enhance")
        self.chk_enhance.grid(row=2, column=0, columnspan=2, sticky="w", padx=4)
        self.chk_speaker = tk.Checkbutton(
            f, text="", variable=self.speaker_var, command=self._on_speaker,
            font=("微软雅黑", 10), bg="#f5f5f5", fg="#222222",
            selectcolor="#ffffff", activebackground="#f5f5f5",
            activeforeground="#222222", highlightthickness=0,
        )
        self._reg(self.chk_speaker, "chk_speaker")
        self.chk_speaker.grid(row=2, column=2, columnspan=2, sticky="w", padx=4)

        # 操作行
        f2 = ttk.Frame(self.root, padding=10)
        f2.pack(fill="x")
        self.btn_record = ttk.Button(f2, width=14, command=self.on_record)
        self.btn_record.pack(side="left", padx=4)
        self.btn_pick = ttk.Button(f2, text="", command=self.on_pick_file, width=16)
        self._reg(self.btn_pick, "btn_pick")
        self.btn_pick.pack(side="left", padx=4)
        self.btn_transcribe = ttk.Button(
            f2, text="", command=self.on_transcribe, width=12, state="disabled"
        )
        self.btn_transcribe.pack(side="left", padx=4)
        self._reg(self.btn_transcribe, "btn_transcribe")

        # 输出
        self.lbl_result = ttk.Label(self.root, text="")
        self._reg(self.lbl_result, "label_result")
        self.lbl_result.pack(anchor="w", padx=12, pady=(6, 0))
        self.text = scrolledtext.ScrolledText(
            self.root, wrap="word", font=("微软雅黑", 11), padx=8, pady=8
        )
        self.text.pack(fill="both", expand=True, padx=12, pady=6)

        # 底部按钮
        f3 = ttk.Frame(self.root, padding=10)
        f3.pack(fill="x")
        self.btn_copy = ttk.Button(f3, width=12, command=self.on_copy)
        self._reg(self.btn_copy, "btn_copy")
        self.btn_copy.pack(side="left", padx=4)
        self.btn_export_txt = ttk.Button(
            f3, width=12, command=lambda: self.on_export("txt")
        )
        self._reg(self.btn_export_txt, "btn_export_txt")
        self.btn_export_txt.pack(side="left", padx=4)
        self.btn_export_srt = ttk.Button(
            f3, width=12, command=lambda: self.on_export("srt")
        )
        self._reg(self.btn_export_srt, "btn_export_srt")
        self.btn_export_srt.pack(side="left", padx=4)
        self.btn_clear = ttk.Button(f3, width=12, command=self.on_clear)
        self._reg(self.btn_clear, "btn_clear")
        self.btn_clear.pack(side="left", padx=4)

        # 状态栏
        self.status = tk.StringVar()
        ttk.Label(self.root, textvariable=self.status, relief="sunken", anchor="w").pack(
            side="bottom", fill="x"
        )

    def _update_record_btn(self):
        key = "btn_stop" if self._recording else "btn_record"
        self.btn_record.configure(text=self.tr(key))

    # ----------------------------- 事件 -----------------------------
    def _save_backend(self):
        c = cfg.load_config()
        c["backend"] = self.backend_var.get()
        cfg.save_config(c)
        self._update_speaker_state()

    def _save_lang(self):
        c = cfg.load_config()
        c["language"] = self.lang_var.get()
        cfg.save_config(c)

    def _on_enhance(self):
        cfg.set_audio_enhance(self.enhance_var.get())

    def _on_speaker(self):
        cfg.set_speaker_sep(self.speaker_var.get())

    def _update_speaker_state(self):
        """说话人分离仅『讯飞转写』后端可用；其它后端禁用该勾选并提示。"""
        ok = backend_supports_diarization(self.backend_var.get(), cfg.load_config()["keys"])
        if ok:
            self.chk_speaker.configure(state="normal")
            self.chk_speaker.configure(text=self.tr("chk_speaker"))
        else:
            self.chk_speaker.configure(state="disabled")
            self.chk_speaker.configure(text=self.tr("chk_speaker_disabled"))
            self.speaker_var.set(False)
            cfg.set_speaker_sep(False)

    def _open_settings(self):
        SettingsWindow(self.root, app=self)

    def _set_status(self, key, *args):
        self._status_key = key
        self._status_args = args
        self.status.set(self.tr(key, *args))

    def on_record(self):
        if self.busy:
            return
        if self.recorder is None:
            self.recorder = rec.Recorder()
            try:
                self.recorder.start()
            except Exception as e:
                messagebox.showerror(self.tr("err_mic"), self.tr("err_mic") % e)
                self.recorder = None
                return
            self._recording = True
            self._update_record_btn()
            self._set_status("status_recording")
        else:
            self.on_stop_record()

    def on_stop_record(self):
        if self.recorder is None:
            return
        self._recording = False
        self._update_record_btn()
        self._set_status("status_stopping")

        def _stop():
            audio = self.recorder.stop()
            self.recorder = None
            if audio.shape[0] == 0:
                self.root.after(0, lambda: self._set_status("status_nosound"))
                return
            wav = rec.Recorder.to_wav_bytes(audio)
            self.current_wav = wav
            self.root.after(0, lambda: self._enable_transcribe())
            self.root.after(0, lambda: self._set_status("status_record_done"))

        threading.Thread(target=_stop, daemon=True).start()

    def on_pick_file(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(
            title=self.tr("btn_pick"),
            filetypes=[
                ("音频文件", "*.wav *.mp3 *.flac *.m4a *.ogg *.wma *.aac"),
                ("所有文件", "*.*"),
            ],
        )
        if not path:
            return
        self._set_status("status_decoding", os.path.basename(path))

        def _load():
            try:
                wav = rec.load_to_wav_bytes(path)
                self.current_wav = wav
                self.root.after(0, lambda: self._enable_transcribe())
                self.root.after(
                    0, lambda: self._set_status("status_loaded", os.path.basename(path))
                )
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(self.tr("err_decode"), str(e)))
                self.root.after(0, lambda: self._set_status("status_decode_fail"))

        threading.Thread(target=_load, daemon=True).start()

    def _enable_transcribe(self):
        self.btn_transcribe.configure(state="normal")

    def on_transcribe(self):
        if self.busy or not self.current_wav:
            return
        c = cfg.load_config()
        name = self.backend_var.get()
        lang = self.lang_var.get()  # auto/zh/en/bilingual
        lang_code = {"auto": "", "zh": "zh", "en": "en", "bilingual": "bilingual"}[lang]
        backend = make_backend(name, c["keys"])
        enhance = bool(c.get("audio_enhance", True))
        speaker_sep = bool(c.get("speaker_sep", False)) and backend_supports_diarization(
            name, c["keys"]
        )
        speaker_number = int(c.get("speaker_number", 2) or 2)
        # 本地降噪（可选）：在发送前对音频做一次轻量增强
        wav = rec.enhance(self.current_wav) if enhance else self.current_wav

        self.busy = True
        self.btn_transcribe.configure(state="disabled")
        self.btn_record.configure(state="disabled")
        self._set_status("status_transcribing", name)
        self.text.delete("1.0", "end")

        def _run():
            try:
                if lang_code == "bilingual":
                    zh = backend.transcribe(
                        wav, "zh", self._progress, speaker_sep=speaker_sep, speaker_number=speaker_number
                    )
                    en = backend.transcribe(
                        wav, "en", self._progress, speaker_sep=speaker_sep, speaker_number=speaker_number
                    )
                    self.bilingual = (zh, en)
                    self.root.after(0, lambda: self._show_result(zh, name))
                    self.root.after(0, lambda: self._set_status("status_bilingual"))
                else:
                    text = backend.transcribe(
                        wav, lang_code, self._progress, speaker_sep=speaker_sep, speaker_number=speaker_number
                    )
                    self.bilingual = None
                    self.root.after(0, lambda: self._show_result(text, name))
            except Exception as e:
                self.bilingual = None
                self.root.after(0, lambda: messagebox.showerror(self.tr("err_transcribe"), str(e)))
                self.root.after(0, lambda: self._set_status("status_transcribe_fail", e))
            finally:
                self.root.after(0, self._finish_busy)

        threading.Thread(target=_run, daemon=True).start()

    def _progress(self, msg):
        self.root.after(0, lambda: self.status.set(msg))

    def _show_result(self, text, name):
        self.text.insert("end", text)
        self._set_status("status_done", name)

    def _finish_busy(self):
        self.busy = False
        self.btn_transcribe.configure(state="normal")
        self.btn_record.configure(state="normal")

    def on_copy(self):
        txt = self.text.get("1.0", "end").strip()
        if txt:
            self.root.clipboard_clear()
            self.root.clipboard_append(txt)
            self._set_status("status_copied")

    def on_export(self, kind):
        # 双语模式：导出纯中文 + 纯英文 两份独立文件（txt 或 srt）
        if self.bilingual:
            zh, en = self.bilingual
            if not zh.strip() and not en.strip():
                messagebox.showinfo(self.tr("msg_hint"), self.tr("status_no_export"))
                return
            ext = ".srt" if kind == "srt" else ".txt"
            title = self.tr("title_export_txt") if kind == "txt" else self.tr("title_export_srt")
            path = filedialog.asksaveasfilename(
                defaultextension=ext,
                filetypes=[("文件", "*%s" % ext), ("所有文件", "*.*")],
                title=title,
            )
            if not path:
                return
            stem, _ = os.path.splitext(path)
            if kind == "txt":
                self._write_file(stem + "_zh.txt", zh)
                self._write_file(stem + "_en.txt", en)
            else:
                self._write_file(stem + "_zh.srt", self._to_srt(zh))
                self._write_file(stem + "_en.srt", self._to_srt(en))
            self._set_status("status_exported", "%s_zh/_en%s" % (stem, ext))
            return
        # 单语模式
        txt = self.text.get("1.0", "end").strip()
        if not txt:
            messagebox.showinfo(self.tr("msg_hint"), self.tr("status_no_export"))
            return
        if kind == "txt":
            path = filedialog.asksaveasfilename(
                defaultextension=".txt", filetypes=[("文本", "*.txt")], title=self.tr("title_export_txt")
            )
            if path:
                self._write_file(path, txt)
                self._set_status("status_exported", path)
        else:
            path = filedialog.asksaveasfilename(
                defaultextension=".srt", filetypes=[("字幕", "*.srt")], title=self.tr("title_export_srt")
            )
            if path:
                self._write_file(path, self._to_srt(txt))
                self._set_status("status_exported", path)

    @staticmethod
    def _write_file(path, content):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def _to_srt(text):
        # 线上 API 多数只返回纯文本，这里生成单条字幕（无时间戳）
        return "1\n00:00:00,000 --> 00:00:10,000\n%s\n" % text

    def on_clear(self):
        self.text.delete("1.0", "end")
        self.current_wav = None
        self.btn_transcribe.configure(state="disabled")
        self._set_status("status_cleared")


def main():
    root = tk.Tk()
    root.report_callback_exception = lambda et, ev, tb: _crash_log(et, ev, tb)
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
