---
name: docx
description: Read, create, or edit Microsoft Word .docx files — extract text and tables, generate reports/letters/memos with headings, tables, images, TOC and page numbers, or apply tracked changes and comments. Use whenever the user has a .docx or wants a Word deliverable. Not for PDF, .xlsx, .pptx, or Google Docs.
triggers:
  - docx
  - word document
  - .docx
  - microsoft word
  - tracked changes
  - redlines
personas:
  - DEV
tech_stack:
  - python
---
[SKILL] docx
[OBJ] Produce correct, valid .docx deliverables — extract or author Word documents without corrupting the OOXML package.
[RULES]
1. [REQ] Know the format: a .docx is a ZIP of XML parts; body text lives in word/document.xml, styles in word/styles.xml, media under word/media/.
2. [REQ] Default toolchain: python-docx for create/read/simple edits. Reach for raw OOXML via zipfile only for what python-docx cannot express — tracked changes (w:ins/w:del), comments, or byte-fidelity edits that must preserve every untouched part.
3. [REQ] Extract correctly: paragraphs via doc.paragraphs, tables via doc.tables row.cells; do not regex the XML — namespaces and runs will defeat it.
4. [REQ] Author completely: headings via add_heading, tables via add_table, page numbers via section footer field codes (PAGE), TOC via a TOC field that Word updates on open — never fake a TOC with typed page numbers.
5. [REQ] Validate before delivering: reopen the output with python-docx and confirm paragraphs/tables read back; a corrupt ZIP or bad XML yields a file Word refuses to open.
6. [REQ] Images: embed via add_picture with explicit width/height in EMU (docx.shared.Inches); never reference external paths.
7. [REQ] Tracked changes need w:ins/w:del elements with author+date attributes and matching w:settings rsid plumbing — generate them through raw OOXML, not python-docx.
8. [CMD] Prefer create → save → reopen → validate in one operation; iterate on the same output file afterward.
9. [CMD] When editing an existing document, write a NEW output file unless the user explicitly authorized in-place replacement.
10. [PROHIBIT] Never deliver a .docx that fails to reopen, never type a TOC manually, never use python-docx APIs for tracked changes.
