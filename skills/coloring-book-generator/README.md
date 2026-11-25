# 🖍️ coloring-book

AI coloring page generator for kids. An [OpenClaw](https://github.com/openclaw/openclaw) skill.

## What it does

Tell your AI assistant what your kid wants to color. It generates age-appropriate line art and gives you a printable PDF. Optionally prints it directly.

```
"Make a coloring page of a dinosaur at the beach for my 3-year-old"
```

30 seconds later: a printable PDF with thick-lined, toddler-friendly dino art.

## Install

```bash
openclaw skill add riverventures/coloring-book
```

## Features

- **Age-calibrated complexity** — Under 2 gets extra-thick bold lines. 3-5 gets medium detail. 6+ gets intricate scenes. Tell it the age once.
- **Themed generators** — Animals, family portraits, learning pages (letters/numbers), story sequences, holiday/cultural themes (Ramadan, Eid, Diwali, Christmas)
- **Booklet mode** — "Make a 10-page coloring book about ocean animals" → compiled multi-page PDF, print and staple
- **Personalization** — Adds your child's name in colorable bubble letters at the top
- **Direct print** — Detects network printers (CUPS/AirPrint) and sends directly. Voice → printer → kid colors.

## Examples

| Request | Output |
|---|---|
| "Giraffe and bird friend for my 19-month-old" | Extra thick lines, simple scene, 3-4 elements |
| "10-page ocean book for Liam, age 4" | Multi-page PDF with name header on each page |
| "Ramadan iftar scene for a 6-year-old" | Detailed scene with lanterns, family, mosque |
| "Letter B with animals for my 2-year-old" | Learning page, bold lines, butterfly + banana |

## Requirements

- Google API key with Generative Language API (Gemini image generation)
- Python 3.9+ with Pillow
- Optional: network printer for direct printing

## How it works

1. You describe what you want
2. Skill builds an age-calibrated prompt for Gemini's image model
3. Generates black & white line art (no shading, no fills)
4. Converts to A4/Letter PDF at print resolution
5. Delivers the file (or sends to your printer)

## Why this exists

I have a 19-month-old. She loves coloring. I was tired of searching Pinterest for mediocre printables. Now I just ask for what she wants and it comes out of the printer.

## License

MIT
