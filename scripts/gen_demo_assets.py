"""Generate README demo assets (demo.gif + social-preview.png) with Pillow.

Deterministic terminal-lookalike rendering — no screen recorder needed.
Run: py -3.10 scripts/gen_demo_assets.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "media"
OUT.mkdir(parents=True, exist_ok=True)

BG = (13, 17, 23)
PANEL = (22, 27, 34)
FG = (230, 237, 243)
DIM = (139, 148, 158)
GREEN = (63, 185, 80)
RED = (248, 81, 73)
CYAN = (96, 181, 255)
PURPLE = (188, 140, 255)
YELLOW = (210, 153, 34)

FONT = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 22)
FONT_SM = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 18)
FONT_BIG = ImageFont.truetype(r"C:\Windows\Fonts\consolab.ttf", 96)
FONT_MED = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 34)


def term_frame(w: int = 920, h: int = 560) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, 40], radius=10, fill=PANEL)
    d.rectangle([0, 20, w, 40], fill=PANEL)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([18 + i * 26, 14, 30 + i * 26, 26], fill=c)
    d.text((110, 10), "aizee — governed shell", font=FONT_SM, fill=DIM)
    return img, d


# Terminal script: (kind, text, color, frames_to_reveal)
LINES: list[tuple[str, str, tuple[int, int, int], int]] = [
    ("cmd", "$ aizee check 'Bash' --args '{\"command\":\"git add .env && git commit\"}'", CYAN, 26),
    ("out", "", FG, 4),
    ("out", "{", FG, 2),
    ("out", '  "ok": false,', FG, 2),
    ("out", '  "decision": "deny",', RED, 2),
    ("out", '  "reason": "guardian: commits secrets file .env",', YELLOW, 3),
    ("out", '  "gate": "probity -> guardian -> policy -> budget -> audit"', DIM, 3),
    ("out", "}", FG, 3),
    ("cmd", "$ aizee doctor --json | jq .verdict", CYAN, 16),
    ("out", '"ready"  # policy + secrets + graph + locks all green', GREEN, 3),
    ("cmd", "$ _", CYAN, 10),
]

PAD_L, PAD_T, LH = 26, 60, 34
CHAR_W = 11  # advance width at 22pt consola


def render_gif() -> None:
    frames: list[Image.Image] = []

    def frame_at(budget: int) -> Image.Image:
        img, d = term_frame()
        y = PAD_T
        for kind, text, color, _ in LINES:
            if budget <= 0:
                break
            if kind == "cmd":
                shown = text[:budget]
                d.text((PAD_L, y), shown, font=FONT, fill=color)
                if len(shown) < len(text):
                    cx = PAD_L + len(shown) * CHAR_W
                    d.rectangle([cx, y + 4, cx + 12, y + 26], fill=FG)
                    budget = 0
                else:
                    budget -= len(text) + 3
            else:
                d.text((PAD_L, y), text, font=FONT, fill=color)
                budget -= 4
            y += LH
        return img

    cmd_chars = sum(len(text) for kind, text, _c, _n in LINES if kind == "cmd")
    for b in range(0, cmd_chars + 60, 3):
        frames.append(frame_at(b))
    for _ in range(18):
        frames.append(frame_at(cmd_chars + 60))  # hold end

    frames[0].save(
        OUT / "demo.gif",
        save_all=True,
        append_images=frames[1:],
        duration=110,
        loop=0,
        optimize=True,
    )
    print(f"demo.gif: {len(frames)} frames, {(OUT / 'demo.gif').stat().st_size // 1024} KB")


def render_social() -> None:
    img = Image.new("RGB", (1280, 640), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 1280, 8], fill=PURPLE)
    d.text((80, 160), "aiZee", font=FONT_BIG, fill=FG)
    d.text((84, 290), "Your AI agent ships hallucinated APIs and secrets.", font=FONT_MED, fill=DIM)
    d.text((84, 340), "aiZee blocks them — enforced, not advised.", font=FONT_MED, fill=FG)
    chips = [
        ("Probity", CYAN), ("Guardian", GREEN), ("Policy", YELLOW),
        ("Budget", PURPLE), ("Audit", RED),
    ]
    x = 84
    for name, c in chips:
        w = int(d.textlength(name, font=FONT_MED)) + 36
        d.rounded_rectangle([x, 430, x + w, 482], radius=24, outline=c, width=3)
        d.text((x + 18, 438), name, font=FONT_MED, fill=c)
        x += w + 20
    d.text((84, 540), "github.com/m3taz-ahmed/aizee", font=FONT_SM, fill=DIM)
    img.save(OUT / "social-preview.png")
    print(f"social-preview.png: {(OUT / 'social-preview.png').stat().st_size // 1024} KB")


if __name__ == "__main__":
    render_gif()
    render_social()
