# -*- coding: utf-8 -*-
"""KindlePub: validate an EPUB with epubcheck (the same check KDP runs).
Deps: pip install --break-system-packages epubcheck  (needs Java on PATH)
Usage: python3 validate_epub.py book.epub
"""
import sys
path = sys.argv[1] if len(sys.argv) > 1 else "book.epub"
from epubcheck import EpubCheck
r = EpubCheck(path)
print("EPUBCHECK VALID:", r.valid)
for m in (r.messages or []):
    print("  ", m)
sys.exit(0 if r.valid else 1)
