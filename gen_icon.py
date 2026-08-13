"""生成应用图标 app_icon.ico —— 语音转文字主题
设计：蓝紫渐变圆角方底 + 白色麦克风(语音输入) + 两侧声波弧(聆听) + 底部字幕条(转写文字)
"""
import numpy as np
from PIL import Image, ImageDraw

TOP = (99, 102, 241)    # indigo-500
BOT = (37, 99, 235)     # blue-600
WHITE = (255, 255, 255, 255)
MESH = (255, 255, 255, 80)   # 网纹（半透明）


def make_icon(size):
    s = float(size)
    # 垂直渐变背景
    grad = np.zeros((size, size, 3), dtype=np.float64)
    top = np.array(TOP, np.float64)
    bot = np.array(BOT, np.float64)
    for y in range(size):
        t = y / (size - 1)
        grad[y] = top * (1 - t) + bot * t
    base = Image.fromarray(grad.astype(np.uint8), "RGB").convert("RGBA")

    # 圆角遮罩：把渐变裁成圆角方块，四角透明
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [int(s * 0.06), int(s * 0.06), int(s * 0.94), int(s * 0.94)],
        radius=int(s * 0.22), fill=255,
    )
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.paste(base, (0, 0), mask)

    d = ImageDraw.Draw(img)
    cx = s * 0.5
    hw = s * 0.15                       # 网头半宽
    top_y = s * 0.30
    bot_y = s * 0.56
    sw = s * 0.05                       # 支架/杆线宽

    # 麦克风网头（胶囊）
    d.rounded_rectangle([cx - hw, top_y, cx + hw, bot_y], radius=hw, fill=WHITE)
    # 支架 U 形
    d.arc([cx - hw, bot_y - s * 0.02, cx + hw, bot_y + s * 0.22],
          start=180, end=360, fill=WHITE, width=max(2, int(sw)))
    # 竖杆
    d.rectangle([cx - sw / 2, bot_y + s * 0.10, cx + sw / 2, s * 0.70], fill=WHITE)
    # 底座
    d.rounded_rectangle([cx - s * 0.17, s * 0.70, cx + s * 0.17, s * 0.70 + sw],
                        radius=sw / 2, fill=WHITE)

    # 两侧声波弧（聆听中）—— 同心括号线，分别朝左右开口
    cyw = s * 0.43
    for scale in (0.08, 0.12, 0.16):
        hw = s * scale
        hh = s * scale * 1.1
        lw = max(2, int(s * 0.035))
        # 右侧：右半椭圆 (300°~60° 经过正东)
        d.arc([cx + s * 0.18 - hw, cyw - hh, cx + s * 0.18 + hw, cyw + hh],
              start=300, end=60, fill=WHITE, width=lw)
        # 左侧：左半椭圆 (120°~240° 经过正西)
        d.arc([cx - s * 0.18 - hw, cyw - hh, cx - s * 0.18 + hw, cyw + hh],
              start=120, end=240, fill=WHITE, width=lw)

    # 底部字幕条（转写出的文字）
    d.rounded_rectangle([cx - s * 0.18, s * 0.80, cx + s * 0.18, s * 0.80 + s * 0.05],
                        radius=s * 0.025, fill=WHITE)
    return img


sizes = [16, 32, 48, 64, 128, 256]
imgs = [make_icon(s) for s in sizes]
out = "D:/VoiceToText/src/app_icon.ico"
# 用最高清的 256 图作为源，降采样出各档，保证清晰度
imgs[-1].save(out, sizes=[(sz, sz) for sz in sizes])
imgs[-1].save("D:/VoiceToText/icon_preview.png")
print("saved", out)
