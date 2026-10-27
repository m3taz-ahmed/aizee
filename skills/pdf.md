---
name: pdf
description: Read, extract, merge, split, or generate PDF files — text and table extraction, form filling, watermarking, metadata, OCR hand-off, and producing new PDFs programmatically. Use whenever the user has a .pdf or wants a PDF deliverable.
triggers:
  - pdf
  - .pdf
  - extract pdf
  - merge pdf
  - split pdf
  - fill pdf form
personas:
  - DEV
tech_stack:
  - python
---
[SKILL] pdf
[OBJ] Extract and produce PDF documents faithfully — correct text order, preserved structure, valid output files.
[RULES]
1. [REQ] Know the format: PDF stores positioned text runs, not flowing paragraphs — extraction order is drawing order, not reading order; multi-column layouts need care.
2. [REQ] Toolchain by task: pypdf for merge/split/metadata/forms; pdfplumber for text+tables with layout; PyMuPDF (fitz) for speed, images, and rendering pages to PNG; reportlab for authoring new PDFs.
3. [REQ] Extraction sanity-check: a page yielding zero text is probably a scan — say so and hand off to OCR (pytesseract) instead of returning emptiness.
4. [REQ] Tables: use pdfplumber's extract_tables (line-detected or text-strategy); never parse tables by splitting lines on whitespace.
5. [REQ] Authoring with reportlab: build via platypus (SimpleDocTemplate + Paragraph/Table/Spacer flowables); set page size explicitly; embed only fonts you ship.
6. [REQ] Forms: fill AcroForm fields via pypdf's update_page_form_field_values and set_need_appearances_writer so viewers render the values; XFA forms are not AcroForm — detect and report instead of silently failing.
7. [REQ] Merging: preserve outlines/bookmarks via pypdf's outline import; encrypted inputs need a password attempt before merge.
8. [CMD] Validate output: reopen produced PDFs with pypdf, confirm page count and that text extracts from page 0; a zero-page or unopenable file is a failed deliverable.
9. [CMD] For visual verification render page 1 to PNG via PyMuPDF (page.get_pixmap) and inspect it.
10. [PROHIBIT] Never claim extraction succeeded on a scanned page without OCR, never modify the input file in place unless explicitly authorized.
