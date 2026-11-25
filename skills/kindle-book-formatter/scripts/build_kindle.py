#!/usr/bin/env python3
"""
build_kindle.py — Convert markdown/txt manuscript to KDP-ready EPUB3 + print PDF.

Usage:
    python3 build_kindle.py --input manuscript.md --output ./output/ \
        --title "My Book" --author "Author Name"
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


# ─── Trim size → margin specs (inner/outer/top/bottom in inches) ──────────────
TRIM_SIZES = {
    "5x8":   {"w": "5in",    "h": "8in",    "inner": "0.875in", "outer": "0.625in", "top": "0.75in",  "bottom": "0.875in"},
    "5.5x8.5": {"w": "5.5in", "h": "8.5in", "inner": "0.875in", "outer": "0.625in", "top": "0.75in",  "bottom": "0.875in"},
    "6x9":   {"w": "6in",    "h": "9in",    "inner": "1.0in",   "outer": "0.75in",  "top": "1.0in",   "bottom": "1.25in"},
    "8.5x11":{"w": "8.5in",  "h": "11in",   "inner": "1.25in",  "outer": "1.0in",   "top": "1.0in",   "bottom": "1.25in"},
}

# Max code line width per trim size (characters that fit in monospace at \scriptsize)
CODE_MAX_WIDTH = {
    "5x8": 48,
    "5.5x8.5": 50,
    "6x9": 52,
    "8.5x11": 68,
}


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text[:60]


def parse_frontmatter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    meta = {}
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            fm = content[3:end].strip()
            for line in fm.splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    meta[key.strip()] = val.strip().strip('"').strip("'")
    return meta


def strip_frontmatter(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            return content[end + 4:].lstrip()
    return content


def strip_title_block_for_pdf(content: str) -> str:
    """Strip the first H1 section for PDF — the LaTeX template handles title/copyright."""
    lines = content.split("\n")
    first_h1 = None
    second_h1 = None
    for i, line in enumerate(lines):
        if line.startswith("# "):
            if first_h1 is None:
                first_h1 = i
            elif second_h1 is None:
                second_h1 = i
                break
    if first_h1 is not None and second_h1 is not None:
        return "\n".join(lines[:first_h1] + lines[second_h1:]).strip()
    return content


def wrap_code_blocks(content: str, max_width: int = 52) -> str:
    """Wrap long lines inside fenced code blocks to fit print margins.

    Prevents KDP 'text outside margins' errors for code blocks containing
    long URLs, file paths, JSON-LD snippets, or prompt templates.
    """
    lines = content.split("\n")
    result = []
    in_code = False
    for line in lines:
        if line.startswith("```"):
            in_code = not in_code
            result.append(line)
            continue
        if in_code and len(line) > max_width:
            indent = len(line) - len(line.lstrip())
            prefix = line[:indent]
            text = line[indent:]
            while len(prefix + text) > max_width and text:
                cut = max_width - len(prefix)
                if cut <= 0:
                    cut = max_width
                space_pos = text.rfind(" ", 0, cut)
                if space_pos > 0:
                    cut = space_pos + 1
                result.append(prefix + text[:cut].rstrip())
                text = text[cut:].lstrip() if space_pos > 0 else text[cut:]
            if text:
                result.append(prefix + text)
        else:
            result.append(line)
    return "\n".join(result)


def write_temp_md(content: str, tmp_dir: str) -> Path:
    p = Path(tmp_dir) / "manuscript.md"
    p.write_text(content, encoding="utf-8")
    return p


def create_lua_filter(tmp_dir: str) -> Path:
    """Create a pandoc lua filter that assigns equal column widths to tables."""
    lua_code = '''function Table(tbl)
  if tbl.widths then
    local ncols = #tbl.widths
    if ncols == 0 then return tbl end
    local all_zero = true
    for i, w in ipairs(tbl.widths) do
      if w > 0 then all_zero = false; break end
    end
    if all_zero then
      local width = 1.0 / ncols
      for i = 1, ncols do tbl.widths[i] = width end
    end
  end
  return tbl
end
'''
    p = Path(tmp_dir) / "table-width-filter.lua"
    p.write_text(lua_code, encoding="utf-8")
    return p


def build_epub(src: Path, out_path: Path, meta: dict, cover: str | None = None) -> bool:
    cmd = [
        "pandoc", str(src),
        "--from", "markdown+smart",
        "--to", "epub3",
        "--output", str(out_path),
        "--toc", "--toc-depth=2", "--split-level=1",
        "--metadata", f"title={meta['title']}",
        "--metadata", f"author={meta['author']}",
        "--metadata", f"lang={meta.get('language', 'en-US')}",
    ]
    if meta.get("publisher"):
        cmd += ["--metadata", f"publisher={meta['publisher']}"]
    if meta.get("rights"):
        cmd += ["--metadata", f"rights={meta['rights']}"]
    if meta.get("description"):
        cmd += ["--metadata", f"description={meta['description']}"]

    css_path = Path(__file__).parent.parent / "assets" / "epub-styles.css"
    if css_path.exists():
        cmd += ["--css", str(css_path)]
    if cover and Path(cover).exists():
        cmd += ["--epub-cover-image", cover]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[EPUB ERROR] {result.stderr}", file=sys.stderr)
        return False
    return True


def build_pdf(src: Path, out_path: Path, meta: dict, trim: str, font_size: int,
              lua_filter: Path | None = None) -> bool:
    t = TRIM_SIZES.get(trim, TRIM_SIZES["6x9"])
    geometry = (
        f"paperwidth={t['w']},paperheight={t['h']},"
        f"inner={t['inner']},outer={t['outer']},"
        f"top={t['top']},bottom={t['bottom']}"
    )

    template_path = Path(__file__).parent.parent / "assets" / "print-template.tex"
    if not template_path.exists():
        print("[PDF ERROR] print-template.tex not found", file=sys.stderr)
        return False

    cmd = [
        "pandoc", str(src),
        "--from", "markdown+smart",
        "--to", "pdf",
        "--pdf-engine=xelatex",
        f"--template={template_path}",
        "--output", str(out_path),
        "--toc", "--toc-depth=2",
        "--columns=50",
    ]

    if lua_filter and lua_filter.exists():
        cmd += [f"--lua-filter={lua_filter}"]

    cmd += [
        "-V", f"geometry={geometry}",
        "-V", f"fontsize={font_size}pt",
        "-V", "linestretch=1.5",
        "-V", "documentclass=book",
        "-V", "classoption=openany",
        "-V", f"title={meta['title']}",
        "-V", f"author={meta['author']}",
    ]

    if meta.get("publisher"):
        cmd += ["-V", f"publisher={meta['publisher']}"]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[PDF ERROR] {result.stderr}", file=sys.stderr)
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Build KDP-ready EPUB and PDF from markdown")
    parser.add_argument("--input", required=True, help="Path to input .md or .txt file")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--title", help="Book title (overrides frontmatter)")
    parser.add_argument("--author", help="Author name (overrides frontmatter)")
    parser.add_argument("--language", default=None)
    parser.add_argument("--publisher", default=None)
    parser.add_argument("--rights", default=None)
    parser.add_argument("--description", default=None)
    parser.add_argument("--cover", default=None, help="Path to cover image (EPUB)")
    parser.add_argument("--trim", default="6x9", choices=list(TRIM_SIZES.keys()))
    parser.add_argument("--font-size", type=int, default=12)
    parser.add_argument("--epub-only", action="store_true")
    parser.add_argument("--pdf-only", action="store_true")
    args = parser.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"[ERROR] Input file not found: {src}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    fm = parse_frontmatter(src)
    meta = {
        "title":       args.title or fm.get("title") or src.stem,
        "author":      args.author or fm.get("author") or "Unknown",
        "language":    args.language or fm.get("language") or fm.get("lang") or "en-US",
        "publisher":   args.publisher or fm.get("publisher"),
        "rights":      args.rights or fm.get("rights"),
        "description": args.description or fm.get("description"),
    }

    slug = slugify(meta["title"])
    print(f"\n📚 Building: {meta['title']} by {meta['author']}")
    print(f"   Trim: {args.trim} | Font: {args.font_size}pt")

    content = strip_frontmatter(src)

    with tempfile.TemporaryDirectory() as tmp:
        src_dir = src.parent
        for ext in ("*.jpg", "*.png", "*.jpeg"):
            for img in src_dir.glob(ext):
                shutil.copy(img, tmp)

        tmp_src = write_temp_md(content, tmp)
        lua_filter = create_lua_filter(tmp)

        results = {}

        if not args.pdf_only:
            epub_out = out_dir / f"{slug}_digital.epub"
            print(f"\n⚡ Building EPUB → {epub_out.name}")
            ok = build_epub(tmp_src, epub_out, meta, cover=args.cover)
            results["epub"] = epub_out if ok else None
            if ok:
                size_kb = epub_out.stat().st_size // 1024
                print(f"   ✅ EPUB done ({size_kb} KB)")
            else:
                print("   ❌ EPUB failed — check errors above")

        if not args.epub_only:
            pdf_content = strip_title_block_for_pdf(content)
            code_width = CODE_MAX_WIDTH.get(args.trim, 52)
            pdf_content = wrap_code_blocks(pdf_content, max_width=code_width)
            tmp_pdf_src = Path(tmp) / "manuscript_pdf.md"
            tmp_pdf_src.write_text(pdf_content, encoding="utf-8")

            pdf_out = out_dir / f"{slug}_print.pdf"
            print(f"\n⚡ Building Print PDF → {pdf_out.name}")
            ok = build_pdf(tmp_pdf_src, pdf_out, meta, trim=args.trim,
                           font_size=args.font_size, lua_filter=lua_filter)
            results["pdf"] = pdf_out if ok else None
            if ok:
                size_kb = pdf_out.stat().st_size // 1024
                print(f"   ✅ PDF done ({size_kb} KB)")
            else:
                print("   ❌ PDF failed — check errors above")

    print("\n─────────────────────────────────────────")
    print("📦 Output files:")
    if results.get("epub"):
        print(f"   Digital (EPUB):  {results['epub']}")
        print(f"   → Upload to KDP › Kindle eBooks › Manuscript")
    if results.get("pdf"):
        print(f"   Print (PDF):     {results['pdf']}")
        print(f"   → Upload to KDP › Paperback › Manuscript interior")
    print("\n⚠️  Don't forget: KDP needs a SEPARATE cover file.")
    print("   Use KDP Cover Calculator for the exact cover PDF dimensions.")
    print("─────────────────────────────────────────\n")

    if not any(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
