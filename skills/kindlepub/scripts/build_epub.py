# -*- coding: utf-8 -*-
"""KindlePub: build a reflowable, epubcheck-clean Kindle EPUB from a .docx manuscript.
Edit CONFIG, then run: python3 build_epub.py
Deps: pip install --break-system-packages mammoth ebooklib beautifulsoup4 lxml
"""
import re, uuid, html, os
import mammoth
from bs4 import BeautifulSoup
from ebooklib import epub

# ============================ CONFIG ============================
INPUT_DOCX  = "manuscript.docx"        # exported .docx (Google Doc -> export?format=docx)
TITLE       = "Book Title"
SUBTITLE    = "Your Subtitle Here"
AUTHOR      = "Author Name"
CONTRIBUTORS= []                        # e.g. ["Claude (Anthropic)"] - title page only, NOT KDP authors
PUBLISHER   = "Your Imprint"
PUB_CITY    = "Your City, ST"
COVER_JPG   = "cover.jpg"               # 1600x2560 portrait
OUT_EPUB    = "book.epub"
DESCRIPTION = "One-paragraph description for EPUB metadata."
CHAPTER_RE  = r"^CHAPTER\s+\d+$"        # exact text (any case) that starts a chapter
NAMED_SECTIONS = {"READER":"A Reader's Guide","HOW THIS BOOK WAS MADE":"How This Book Was Made",
                  "ABOUT THE AUTHOR":"About the Author","APPENDIX":"Appendix"}
INTERLUDE_WORD = "INTERLUDE"
INCLUDE_988 = True                       # keep the crisis disclaimer for health/safety books
# ===============================================================

with open(INPUT_DOCX, "rb") as f:
    res = mammoth.convert_to_html(f)
soup = BeautifulSoup(res.value, "lxml")
# pull embedded images out of the .docx zip for in-text figures
import zipfile
media = {}
with zipfile.ZipFile(INPUT_DOCX) as z:
    for n in z.namelist():
        if n.startswith("word/media/"):
            media[os.path.basename(n)] = z.read(n)
img_files = list(media.items())

blocks = soup.body.find_all(["h1","h2","p"])
def norm(s): return " ".join(s.split()).strip()
DIV = set("*-_  ")
def is_div(t):
    t=t.strip(); return 0<len(t)<=7 and all(c in "*-_ " for c in t) and "*" in t

def boundary(b):
    t=norm(b.get_text()); U=t.upper()
    if not t: return None
    if re.match(CHAPTER_RE, U): return ("chapter", t)
    if b.name in ("h1","h2"):
        for key,disp in NAMED_SECTIONS.items():
            if key in U: return ("named", disp)
    if b.name=="p" and U==INTERLUDE_WORD: return ("interlude", t)
    return None

bounds=[(i,)+boundary(b) for i,b in enumerate(blocks) if boundary(b)]
sections=[]
for n,(idx,kind,txt) in enumerate(bounds):
    end=bounds[n+1][0] if n+1<len(bounds) else len(blocks)
    if kind=="chapter":
        num=re.search(r"\d+",txt).group(); title=norm(blocks[idx+1].get_text()) if idx+1<end else ""
        sections.append(dict(kind="chapter",eyebrow=f"Chapter {num}",heading=title,body=blocks[idx+2:end]))
    elif kind=="interlude":
        sub=norm(blocks[idx+1].get_text()) if idx+1<end else ""
        sections.append(dict(kind="front",eyebrow="Interlude",heading=sub,body=blocks[idx+2:end]))
    else:
        sections.append(dict(kind="matter",eyebrow="",heading=txt,body=blocks[idx+1:end]))

img_idx=[0]
def render(b):
    if b.find("img") is not None and img_idx[0] < len(img_files):
        return '<figure class="fig"><img src="images/%s" alt="figure"/></figure>' % img_files[min(img_idx[0],len(img_files)-1)][0]
    t=norm(b.get_text())
    if not t: return ""
    if is_div(t): return '<p class="div">* * *</p>'
    inner=re.sub(r"</?(h1|h2|h3)[^>]*>","",b.decode_contents()).strip()
    return f"<p>{inner}</p>" if inner else ""

PAGE='<html xmlns="http://www.w3.org/1999/xhtml"><body>{0}</body></html>'
def sec_xhtml(s):
    parts=[]
    if s["eyebrow"]: parts.append(f'<p class="eyebrow">{html.escape(s["eyebrow"])}</p>')
    parts.append(f'<h1 class="ct">{html.escape(s["heading"])}</h1>')
    for b in s["body"]:
        r=render(b)
        if r: parts.append(r)
    return PAGE.format("\n".join(parts))

book=epub.EpubBook(); book.set_identifier("urn:uuid:"+str(uuid.uuid4()))
book.set_title(TITLE); book.set_language("en"); book.add_author(AUTHOR)
for c in CONTRIBUTORS: book.add_metadata("DC","contributor",c)
book.add_metadata("DC","publisher",PUBLISHER); book.add_metadata("DC","date","2026")
book.add_metadata("DC","description",DESCRIPTION)
book.set_cover("cover.jpg", open(COVER_JPG,"rb").read(), create_page=True)
cov=book.get_item_with_id("cover")
if cov is not None: cov.is_linear=True
# in-text figure image(s)
for i,(name,data) in enumerate(img_files):
    book.add_item(epub.EpubImage(uid="img_%d"%i, file_name="images/"+name, media_type="image/png", content=data))

CSS=("body{font-family:Georgia,serif;line-height:1.5;margin:0 6%}"
     "h1.ct{font-family:Arial,sans-serif;font-weight:700;font-size:1.7em;margin:1.2em 0 .2em}"
     "p.eyebrow{font-family:Arial,sans-serif;letter-spacing:.18em;text-transform:uppercase;font-size:.78em;color:#2b7c86;margin:2.2em 0 0}"
     "p{margin:0 0 1em;text-align:justify}p.div{text-align:center;color:#2b7c86;letter-spacing:.3em;margin:1.4em 0}"
     "figure.fig{margin:1.4em 0;text-align:center}figure.fig img{max-width:100%}.legal{font-size:.92em}"
     "h1.tt{font-family:Arial,sans-serif;font-size:2.1em;margin:.2em 0}.sub{font-style:italic;font-size:1.15em}")
css=epub.EpubItem(uid="style",file_name="style/style.css",media_type="text/css",content=CSS); book.add_item(css)

def mk(uid,fn,title,body):
    c=epub.EpubHtml(uid=uid,file_name=fn,title=title,lang="en")
    c.content=PAGE.format(body); c.add_link(href="style/style.css",rel="stylesheet",type="text/css")
    book.add_item(c); return c

contrib = ("<p class=\"legal\">with " + " and ".join(CONTRIBUTORS) + "</p>") if CONTRIBUTORS else ""
title_pg=mk("title","title.xhtml",TITLE,
    f'<h1 class="tt">{html.escape(TITLE)}</h1><p class="sub">{html.escape(SUBTITLE)}</p>'
    f'<p class="legal"><b>{html.escape(AUTHOR)}</b></p>{contrib}')
copy_pg=mk("copyright","copyright.xhtml","Copyright",
    f'<h1 class="ct">Copyright</h1><p class="legal"><em>{html.escape(TITLE)}: {html.escape(SUBTITLE)}</em></p>'
    f'<p class="legal">Copyright &#169; 2026 {html.escape(AUTHOR)}. All rights reserved.</p>'
    '<p class="legal">No part of this book may be reproduced without prior written permission from the author, '
    'except for brief quotations used in reviews.</p>'
    f'<p class="legal">Published by {html.escape(PUBLISHER)}, {html.escape(PUB_CITY)}.</p>'
    '<p class="legal">First edition, 2026.</p>')
spine=["cover",title_pg,copy_pg]; toc=[title_pg,copy_pg]
if INCLUDE_988:
    dis=mk("disclaimer","disclaimer.xhtml","Disclaimer",
      '<h1 class="ct">Disclaimer</h1><p class="legal">This book is for general informational and educational '
      'purposes only. It is not medical, psychological, or professional advice and is not a substitute for '
      'diagnosis or treatment by a qualified professional.</p><p class="legal"><strong>If you or someone you know '
      'may be in crisis, do not rely on a book or a chatbot. In the United States, call or text 988 (the Suicide '
      'and Crisis Lifeline) or call 911. Outside the United States, contact your local emergency or crisis '
      'service.</strong></p>')
    spine.append(dis); toc.append(dis)
spine.append("nav")
content=[]
for s in sections:
    uid="sec_%d"%len(content); c=epub.EpubHtml(uid=uid,file_name=uid+".xhtml",title=s["heading"] or s["eyebrow"],lang="en")
    c.content=sec_xhtml(s); c.add_link(href="style/style.css",rel="stylesheet",type="text/css"); book.add_item(c)
    content.append(c); spine.append(c); toc.append(c)
book.toc=toc; book.add_item(epub.EpubNcx()); book.add_item(epub.EpubNav()); book.spine=spine
epub.write_epub(OUT_EPUB, book, {"epub3_pages": False})
print("WROTE", OUT_EPUB, "| sections:", len(content), "| figures:", len(img_files))
