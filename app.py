import os
import re
import math
import shutil
import asyncio
import tempfile
import subprocess
from functools import lru_cache

import numpy as np
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# ==============================================================================
# 1. PAGE SETUP
# ==============================================================================
st.set_page_config(page_title="Fintech Pulse Studio", page_icon="⚡", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    .main-title { color: #00F0FF; font-weight: 800; font-size: 2rem; margin-bottom: 0;
                  text-shadow: 0 0 12px rgba(0,240,255,.4); }
    .sub-title { color: #8b949e; font-size: .9rem; margin-bottom: 20px; }
    .stButton>button, .stDownloadButton>button {
        background: linear-gradient(90deg,#00F0FF 0%,#0088FF 100%);
        color: #000 !important; font-weight: bold; border: none; border-radius: 8px;
        padding: 12px 24px; width: 100%; box-shadow: 0 4px 14px rgba(0,240,255,.3); }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-title'>⚡ FINTECH PULSE</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Free animated short-video studio · no API keys</p>", unsafe_allow_html=True)

# ==============================================================================
# 2. THEMES
# ==============================================================================
THEMES = {
    "Neon Cyber":   dict(base=(8, 10, 22),  blobs=[(0, 240, 255), (120, 60, 255), (255, 0, 150)], accent=(0, 240, 255)),
    "Money Green":  dict(base=(5, 16, 12),  blobs=[(0, 255, 150), (0, 120, 90), (200, 255, 80)],  accent=(0, 255, 150)),
    "Sunset Gold":  dict(base=(20, 8, 16),  blobs=[(255, 120, 0), (255, 40, 100), (255, 200, 60)], accent=(255, 200, 60)),
    "Royal Violet": dict(base=(12, 8, 26),  blobs=[(150, 80, 255), (60, 100, 255), (255, 80, 200)], accent=(190, 140, 255)),
}

SAMPLES = {
    "Autopilot wealth": "Stop scrolling if you want to automate your wealth in 2026. These three fintech tools manage your money on autopilot so you don't have to lift a finger.",
    "Save first": "Most people save what is left after spending. Flip it. Move money into savings the moment you get paid, then spend what remains. Do that for one year and watch what happens.",
    "Index funds": "You do not need to pick stocks to build wealth. A simple low cost index fund, bought every month, beats most people who try to guess the market. Boring wins.",
}

# Sidebar
st.sidebar.header("⚙️ Channel Settings")
voice = st.sidebar.selectbox("Voice Actor", [
    "en-US-ChristopherNeural", "en-US-EricNeural", "en-US-GuyNeural",
    "en-US-JennyNeural", "en-US-AriaNeural", "en-GB-RyanNeural", "en-IN-NeerjaNeural"])
speed = st.sidebar.slider("Voice speed", -20, 30, 8, format="%d%%")
theme_name = st.sidebar.selectbox("Visual theme", list(THEMES))
bg_mode = st.sidebar.radio("Background", ["Trading-chart motion graphics", "My own clips / photos"])
quality = st.sidebar.selectbox("Quality", ["Fast (540x960)", "Standard (720x1280)", "Full HD (1080x1920)"], index=1)
channel = st.sidebar.text_input("Channel name (top badge)", "FINTECH PULSE")
cta_text = st.sidebar.text_input("Call to Action", "LINK IN BIO TO START")

# ==============================================================================
# 3. HELPERS
# ==============================================================================
def ffmpeg_path():
    p = shutil.which("ffmpeg")
    if p:
        return p
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def audio_duration(path):
    r = subprocess.run([ffmpeg_path(), "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", r.stderr)
    if not m:
        raise RuntimeError("Could not read audio duration")
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])


async def _edge_tts(text, voice, rate, out):
    import edge_tts
    try:
        comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    except TypeError:
        comm = edge_tts.Communicate(text, voice, rate=rate)
    words = []
    with open(out, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                s = ch["offset"] / 1e7
                words.append((ch["text"], s, s + ch["duration"] / 1e7))
    if os.path.getsize(out) == 0:
        raise RuntimeError("Edge-TTS returned empty audio")
    return words


def estimate_words(text, dur):
    toks = text.split()
    weights = [len(t) + 2 for t in toks]
    total = sum(weights)
    t, out = 0.0, []
    for tok, w in zip(toks, weights):
        d = dur * w / total
        out.append((tok, t, t + d))
        t += d
    return out


def synthesize(text, voice, speed_pct, out):
    """Free TTS: Edge-TTS first, gTTS as fallback. Returns (word_timings, engine)."""
    rate = f"{speed_pct:+d}%"
    last_err = None
    for _ in range(3):
        try:
            words = asyncio.run(_edge_tts(text, voice, rate, out))
            if not words:
                words = estimate_words(text, audio_duration(out))
            return words, "Edge-TTS"
        except Exception as e:  # network blocks, 403s, etc.
            last_err = e
    try:
        from gtts import gTTS
        gTTS(text, lang="en").save(out)
        return estimate_words(text, audio_duration(out)), "gTTS (fallback)"
    except Exception as e:
        raise RuntimeError(f"Both voice engines failed. Edge-TTS: {last_err} | gTTS: {e}")


# ---------------------------- drawing ----------------------------------------
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


@lru_cache(maxsize=64)
def get_font(size):
    size = int(size)
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def ease_out_back(x):
    x = min(max(x, 0.0), 1.0)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def make_groups(words, per=3):
    groups, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= per or re.search(r"[.!?,;:]$", w[0]):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


class Scene:
    def __init__(self, W, H, theme, words, total, channel, cta, bg_reader=None, seed=7):
        self.W, self.H, self.theme, self.total = W, H, theme, total
        self.channel, self.cta = channel.upper(), cta.upper()
        self.accent = theme["accent"]
        self.bg_reader = bg_reader
        self.groups = make_groups(words)
        rng = np.random.default_rng(seed)

        sw, sh = max(W // 6, 90), max(H // 6, 160)
        yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
        self.X, self.Y = xx / sh, yy / sh            # keep aspect ratio
        self.aspect = sw / sh
        vx, vy = (xx / sw - .5), (yy / sh - .5)
        self.vignette = np.clip(1.15 - 1.4 * (vx ** 2 + vy ** 2), .25, 1)[..., None]
        self.base = np.array(theme["base"], np.float32)
        self.blob_cols = [np.array(c, np.float32) for c in theme["blobs"]]
        self.blob_ph = rng.uniform(0, 6.28, (3, 2))
        self.blob_sp = rng.uniform(.25, .6, (3, 2))

        n = 46
        self.p = dict(x=rng.uniform(0, W, n), y=rng.uniform(0, H, n),
                      s=rng.uniform(20, 90, n) * H / 1920, r=rng.uniform(2, 7, n) * H / 1920,
                      ph=rng.uniform(0, 6.28, n), a=rng.integers(40, 120, n))

        steps = rng.normal(0.35, 1.0, 90)          # upward-drifting random walk (decoration only)
        series = np.cumsum(steps)
        series = (series - series.min()) / (series.max() - series.min())
        self.series = series

        # 3 candlestick sets (decoration only) -> a new "scene" every SEG seconds
        self.SEG = 5.0
        self.candle_sets = []
        for _ in range(3):
            o, cs = 0.0, []
            for _ in range(28):
                c = o + rng.normal(0.18, 1.0)
                h = max(o, c) + abs(rng.normal(0, .5))
                l = min(o, c) - abs(rng.normal(0, .5))
                cs.append((o, h, l, c)); o = c
            arr = np.array(cs)
            lo, hi = arr.min(), arr.max()
            self.candle_sets.append((arr - lo) / (hi - lo))
        self.vol = rng.uniform(.15, 1, (3, 28))

    # ---- background ----
    def background(self, t):
        if self.bg_reader is not None:
            img = self.bg_reader()
            if img is not None:
                arr = (np.asarray(img, np.float32) * .5 + np.array(self.theme["base"], np.float32) * .3)
                return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        gx = self.aspect
        img = np.tile(self.base, (*self.X.shape, 1))
        for i, col in enumerate(self.blob_cols):
            cx = (.5 + .45 * math.sin(t * self.blob_sp[i, 0] + self.blob_ph[i, 0])) * gx
            cy = .5 + .55 * math.sin(t * self.blob_sp[i, 1] + self.blob_ph[i, 1])
            d2 = (self.X - cx) ** 2 + (self.Y - cy) ** 2
            img += np.exp(-d2 / (2 * .16 ** 2))[..., None] * col * .55
        img = np.clip(img * self.vignette, 0, 255).astype(np.uint8)
        return Image.fromarray(img).resize((self.W, self.H), Image.BICUBIC)

    def decorations(self, d, t):
        W, H, a = self.W, self.H, self.accent
        if self.bg_reader is None:
            self._grid(d, t)
        self._particles(d, t)

    def _grid(self, d, t):
        W, H, a = self.W, self.H, self.accent
        off = (t * 40) % (H / 16)
        for k in range(18):
            y = H * .62 + k * H / 16 + off
            if y < H:
                d.line([(0, y), (W, y)], fill=(*a, 16), width=max(1, W // 540))
        for k in range(0, 13):
            x = k * W / 12
            d.line([(x, H * .62), (W / 2 + (x - W / 2) * 2.2, H)], fill=(*a, 12), width=max(1, W // 540))

    def _particles(self, d, t):
        W, H, a = self.W, self.H, self.accent
        P = self.p
        for i in range(len(P["x"])):
            y = (P["y"][i] - P["s"][i] * t * 3) % H
            x = P["x"][i] + math.sin(t * .8 + P["ph"][i]) * 22 * W / 1080
            r = P["r"][i]
            d.ellipse([x - r * 2.2, y - r * 2.2, x + r * 2.2, y + r * 2.2], fill=(*a, int(P["a"][i] * .25)))
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, int(P["a"][i])))

    def candles(self, d, t):
        W, H, a = self.W, self.H, self.accent
        x0, x1, y0, y1 = W * .07, W * .93, H * .13, H * .42
        d.rounded_rectangle([x0 - W * .02, y0 - H * .02, x1 + W * .02, y1 + H * .05], radius=W * .03,
                            fill=(0, 0, 0, 95), outline=(*a, 60), width=max(1, W // 540))
        seg = int(t // self.SEG) % 3
        lt = (t % self.SEG) / self.SEG
        cs = self.candle_sets[seg]
        n = len(cs)
        k = min(n, lt * 1.15 * n)
        slot = (x1 - x0) / n
        bw = slot * .62
        ch = y1 - y0
        for g in range(5):
            y = y0 + ch * g / 4
            d.line([(x0, y), (x1, y)], fill=(255, 255, 255, 16), width=max(1, W // 540))
        closes = []
        for i in range(int(math.ceil(k))):
            o, h, l, c = cs[i]
            grow = 1.0 if i < int(k) else (k - int(k))
            c = o + (c - o) * grow
            h = max(h, o, c) if grow >= 1 else max(o, c)
            l = min(l, o, c) if grow >= 1 else min(o, c)
            cx = x0 + slot * (i + .5)
            yo, yc, yh, yl = [y1 - ch * v for v in (o, c, h, l)]
            col = (0, 230, 130, 255) if c >= o else (255, 70, 90, 255)
            d.line([(cx, yh), (cx, yl)], fill=col, width=max(2, W // 300))
            d.rounded_rectangle([cx - bw / 2, min(yo, yc), cx + bw / 2, max(yo, yc) + 2], radius=2, fill=col)
            vh = self.vol[seg][i] * H * .035
            d.rectangle([cx - bw / 2, y1 + H * .04 - vh, cx + bw / 2, y1 + H * .04], fill=(*col[:3], 90))
            closes.append((cx, yc))
        if len(closes) > 5:
            ma = [(closes[i][0], sum(p[1] for p in closes[i - 4:i + 1]) / 5) for i in range(4, len(closes))]
            d.line(ma, fill=(*a, 70), width=max(6, W // 80), joint="curve")
            d.line(ma, fill=(*a, 240), width=max(3, W // 220), joint="curve")
        if closes:
            ex, ey = closes[-1]
            r = W / 80 * (1 + .35 * math.sin(t * 7))
            d.ellipse([ex - r * 2.4, ey - r * 2.4, ex + r * 2.4, ey + r * 2.4], fill=(*a, 60))
            d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=(255, 255, 255, 255))

    def ticker(self, d, t):
        W, H = self.W, self.H
        f = get_font(W * .034)
        msg = "SAVE   •   INVEST   •   AUTOMATE   •   COMPOUND   •   "
        mw = d.textlength(msg, font=f)
        y = H * .935
        d.rectangle([0, y - f.size * .9, W, y + f.size * .9], fill=(0, 0, 0, 130))
        x = -((t * W * .18) % mw)
        while x < W:
            d.text((x, y), msg, font=f, fill=(*self.accent, 230), anchor="lm")
            x += mw

    def chart(self, d, t):
        if self.bg_reader is None:
            return self.candles(d, t)
        return None

    def line_chart_unused(self, d, t):
        W, H, a = self.W, self.H, self.accent
        x0, x1, y0, y1 = W * .08, W * .92, H * .15, H * .40
        n = len(self.series)
        prog = min(1.0, (t / self.total) * 1.15 + .08)
        upto = max(2, int(n * prog))
        # frame lines
        for k in range(5):
            y = y0 + (y1 - y0) * k / 4
            d.line([(x0, y), (x1, y)], fill=(255, 255, 255, 18), width=max(1, W // 540))
        pts = [(x0 + (x1 - x0) * i / (n - 1), y1 - (y1 - y0) * self.series[i]) for i in range(upto)]
        d.line(pts, fill=(*a, 55), width=max(6, W // 70), joint="curve")
        d.line(pts, fill=(*a, 235), width=max(3, W // 200), joint="curve")
        ex, ey = pts[-1]
        pulse = 1 + .35 * math.sin(t * 6)
        r = W / 70 * pulse
        d.ellipse([ex - r * 2.4, ey - r * 2.4, ex + r * 2.4, ey + r * 2.4], fill=(*a, 60))
        d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=(255, 255, 255, 255))

    def badge(self, d):
        W, H = self.W, self.H
        f = get_font(W * .036)
        tw = d.textlength(self.channel, font=f)
        pad = W * .035
        cy = H * .075
        d.rounded_rectangle([W / 2 - tw / 2 - pad, cy - f.size * .9, W / 2 + tw / 2 + pad, cy + f.size * .9],
                            radius=f.size, fill=(0, 0, 0, 120), outline=(*self.accent, 200), width=max(2, W // 360))
        d.text((W / 2, cy), self.channel, font=f, fill=(*self.accent, 255), anchor="mm")

    def captions(self, d, t):
        W, H = self.W, self.H
        gi = 0
        for i, g in enumerate(self.groups):
            if g[0][1] <= t:
                gi = i
        g = self.groups[gi]
        if t < g[0][1] - .05:
            return
        gstart = g[0][1]
        pop = 1 + .18 * (1 - ease_out_back((t - gstart) / .22)) if t - gstart < .22 else 1.0
        fs = W * .105 * pop
        f = get_font(fs)
        sp = d.textlength(" ", font=f)
        maxw = W * .88
        lines, cur, curw = [], [], 0
        for wd in g:
            ww = d.textlength(wd[0].upper(), font=f)
            if cur and curw + sp + ww > maxw:
                lines.append((cur, curw))
                cur, curw = [], 0
            cur.append((wd, ww))
            curw += ww + (sp if len(cur) > 1 else 0)
        lines.append((cur, curw))
        lh = fs * 1.25
        block_h = lh * len(lines)
        cy = H * .60
        top = cy - block_h / 2
        bw = max(l[1] for l in lines) + W * .07
        d.rounded_rectangle([W / 2 - bw / 2, top - fs * .25, W / 2 + bw / 2, top + block_h + fs * .1],
                            radius=fs * .35, fill=(0, 0, 0, 110))
        active = max(j for j, wd in enumerate(g) if wd[1] <= t + .02) if g[0][1] <= t + .02 else 0
        idx = 0
        for li, (ws, lw) in enumerate(lines):
            x = W / 2 - lw / 2
            y = top + li * lh + lh / 2
            for (wd, ww) in ws:
                col = (*self.accent, 255) if idx == active else (255, 255, 255, 255)
                d.text((x, y), wd[0].upper(), font=f, fill=col, anchor="lm",
                       stroke_width=max(3, int(fs * .06)), stroke_fill=(0, 0, 0, 255))
                x += ww + sp
                idx += 1

    def footer(self, d, t):
        W, H = self.W, self.H
        pulse = 1 + .035 * math.sin(t * 5)
        f = get_font(W * .04 * pulse)
        tw = d.textlength(self.cta, font=f)
        cy = H * .86
        pw, ph = tw + W * .09, f.size * 1.9
        d.rounded_rectangle([W / 2 - pw / 2, cy - ph / 2, W / 2 + pw / 2, cy + ph / 2],
                            radius=ph / 2, fill=(*self.accent, 255))
        d.text((W / 2, cy), self.cta, font=f, fill=(0, 0, 0, 255), anchor="mm")
        # progress bar
        bh = max(6, H // 200)
        d.rectangle([0, H - bh, W, H], fill=(255, 255, 255, 40))
        d.rectangle([0, H - bh, W * min(1, t / self.total), H], fill=(*self.accent, 255))

    def frame(self, t):
        img = self.background(t)
        d = ImageDraw.Draw(img, "RGBA")
        self.chart(d, t)
        self.decorations(d, t)
        self.badge(d)
        self.captions(d, t)
        self.footer(d, t)
        self.ticker(d, t)
        return img


IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")


def build_background(files, workdir, W, H, fps):
    """Normalise uploaded clips/photos to W x H, trim, and join into one looping mp4."""
    ff = ffmpeg_path()
    segs = []
    for i, p in enumerate(files):
        out = os.path.join(workdir, f"seg{i}.mp4")
        if p.lower().endswith(IMG_EXT):   # photo -> slow pan (Ken Burns style)
            vf = (f"scale={int(W*1.3)}:{int(H*1.3)}:force_original_aspect_ratio=increase,"
                  f"crop={W}:{H}:x='(iw-{W})*t/4':y='(ih-{H})/2',setsar=1,format=yuv420p")
            cmd = [ff, "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(fps), "-t", "4", "-i", p,
                   "-vf", vf, "-r", str(fps), "-c:v", "libx264", "-preset", "ultrafast", "-an", out]
        else:                             # video clip -> crop to 9:16, max 6 s
            vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                  f"fps={fps},setsar=1,format=yuv420p")
            cmd = [ff, "-y", "-loglevel", "error", "-t", "6", "-i", p, "-vf", vf,
                   "-c:v", "libx264", "-preset", "ultrafast", "-an", out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(out):
            segs.append(out)
    if not segs:
        raise RuntimeError("None of the uploaded files could be read. Use MP4/MOV/WEBM or JPG/PNG.")
    lst = os.path.join(workdir, "list.txt")
    with open(lst, "w") as fh:
        fh.write("".join(f"file '{p}'\n" for p in segs))
    bg = os.path.join(workdir, "bg.mp4")
    r = subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                        "-c", "copy", bg], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("Could not join clips: " + r.stderr[-300:])
    return bg


def open_bg_reader(bg_path, W, H, fps, total):
    """Returns (reader_fn, process). reader_fn() -> next PIL frame (looping background)."""
    cmd = [ffmpeg_path(), "-loglevel", "error", "-stream_loop", "-1", "-i", bg_path,
           "-t", f"{total:.2f}", "-r", str(fps), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size = W * H * 3
    last = {"img": None}

    def read():
        buf = proc.stdout.read(size)
        if buf and len(buf) == size:
            last["img"] = Image.frombytes("RGB", (W, H), buf)
        return last["img"]
    return read, proc


def render_video(words, audio_path, out_path, theme, W, H, fps, channel, cta, progress_cb=None, bg_path=None):
    dur = audio_duration(audio_path)
    total = dur + .5
    # close gaps so captions never flicker
    words = [(w, s, (words[i + 1][1] if i + 1 < len(words) else e)) for i, (w, s, e) in enumerate(words)]
    reader, bgproc = (None, None)
    if bg_path:
        reader, bgproc = open_bg_reader(bg_path, W, H, fps, total + 1)
    scene = Scene(W, H, theme, words, total, channel, cta, bg_reader=reader)
    n = int(total * fps)
    log = tempfile.NamedTemporaryFile(delete=False, suffix=".log")
    cmd = [ffmpeg_path(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-i", audio_path,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=log)
    try:
        for i in range(n):
            proc.stdin.write(scene.frame(i / fps).tobytes())
            if progress_cb and i % 6 == 0:
                progress_cb(i / n)
        proc.stdin.close()
        proc.wait()
    except BrokenPipeError:
        pass
    finally:
        if bgproc:
            bgproc.kill()
    log.close()
    if proc.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) < 1000:
        with open(log.name) as fh:
            raise RuntimeError("ffmpeg failed: " + fh.read()[-600:])
    return dur


# ==============================================================================
# 4. MAIN UI
# ==============================================================================
sample = st.selectbox("Start from a sample (optional)", ["—"] + list(SAMPLES))
default_text = SAMPLES.get(sample, SAMPLES["Autopilot wealth"])
script_input = st.text_area("💡 Viral hook script:", default_text, height=140,
                            key=f"script_{sample}")
st.caption("Tip: 60–110 words ≈ 25–45 seconds. Short sentences caption best.")

uploads = []
if bg_mode.startswith("My own"):
    st.markdown("**Background footage** — upload clips/photos (they play in order and loop). "
                "Free commercial-use sources: Pexels, Pixabay, Mixkit, Coverr.")
    uploads = st.file_uploader("Upload MP4/MOV/WEBM videos or JPG/PNG photos",
                               type=["mp4", "mov", "webm", "jpg", "jpeg", "png", "webp"],
                               accept_multiple_files=True)

if st.button("🚀 Render Short"):
    if not script_input.strip():
        st.error("Please enter a script.")
    elif bg_mode.startswith("My own") and not uploads:
        st.error("Upload at least one clip or photo, or switch to Trading-chart motion graphics.")
    else:
        W, H = {"Fast": (540, 960), "Standard": (720, 1280), "Full HD": (1080, 1920)}[quality.split(" (")[0]]
        fps = 24
        status = st.status("Building your short...", expanded=True)
        bar = st.progress(0.0)
        try:
            status.write("🎙️ Generating voiceover...")
            tmpdir = tempfile.mkdtemp()
            audio_path = os.path.join(tmpdir, "voice.mp3")
            video_path = os.path.join(tmpdir, "short.mp4")
            words, engine = synthesize(script_input.strip(), voice, speed, audio_path)
            status.write(f"✅ Voice ready via {engine}")

            bg_path = None
            if uploads:
                status.write("🎞️ Preparing your footage...")
                paths = []
                for k, up in enumerate(uploads):
                    p = os.path.join(tmpdir, f"up{k}_{os.path.basename(up.name)}")
                    with open(p, "wb") as fh:
                        fh.write(up.getbuffer())
                    paths.append(p)
                bg_path = build_background(paths, tmpdir, W, H, fps)

            status.write("🎬 Rendering frames...")
            render_video(words, audio_path, video_path, THEMES[theme_name], W, H, fps,
                         channel, cta_text, lambda p: bar.progress(min(p, 1.0)), bg_path=bg_path)
            bar.progress(1.0)
            with open(video_path, "rb") as fh:
                st.session_state["video_bytes"] = fh.read()
            status.update(label="✅ Short ready!", state="complete")
        except Exception as e:
            status.update(label="❌ Error generating video", state="error")
            st.error(f"Error details: {e}")

if st.session_state.get("video_bytes"):
    st.subheader("📺 Preview")
    st.video(st.session_state["video_bytes"])
    st.download_button("📥 Download Short (.mp4)", st.session_state["video_bytes"],
                       file_name="fintech_pulse_short.mp4", mime="video/mp4")
