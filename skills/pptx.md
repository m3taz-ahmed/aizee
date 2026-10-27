---
name: pptx
description: Read, create, or edit PowerPoint .pptx presentations — extract slide text and speaker notes, generate decks with layouts, titles, bullets, images, and tables, or apply template-driven edits. Use whenever the user has a .pptx or wants a presentation deliverable. Not for .docx, .xlsx, or Google Slides.
triggers:
  - pptx
  - powerpoint
  - .pptx
  - presentation
  - slides deck
personas:
  - DEV
tech_stack:
  - python
---
[SKILL] pptx
[OBJ] Produce valid, well-structured .pptx decks — correct slide layouts, readable content, and files PowerPoint actually opens.
[RULES]
1. [REQ] Know the format: .pptx is a ZIP of OOXML; slides under ppt/slides/slideN.xml, layouts under ppt/slideLayouts/, theme in ppt/theme/.
2. [REQ] Default toolchain: python-pptx for everything it covers — layouts, shapes, text frames, tables, images, notes. Raw XML only for what it cannot reach (animations, transitions, slide masters edits).
3. [REQ] Use real layouts: pick from prs.slide_layouts (title, title+content, blank) instead of drawing everything on a blank slide — PowerPoint's own placeholders keep the deck editable.
4. [REQ] Text discipline: title via slide.shapes.title, body via the content placeholder's text_frame with add_paragraph for bullets and .level for indentation; set font size/bold explicitly.
5. [REQ] Extract faithfully: iterate prs.slides, read each shape's text_frame when shape.has_text_frame, tables via shape.has_table, speaker notes via slide.notes_slide.notes_text_frame.
6. [REQ] Images: add via slide.shapes.add_picture with explicit left/top/width/height in EMU; keep aspect ratio by setting only width OR height.
7. [REQ] Tables: add_table(rows, cols, left, top, width, height) then fill cell.text_frame text — merged cells via cell.merge.
8. [CMD] Validate before delivering: reopen with python-pptx, confirm slide count and that every slide's title placeholder reads back; render check via LibreOffice headless (soffice --convert-to pdf) when fidelity matters.
9. [CMD] Keep text concise — slides are not documents; if a bullet exceeds ~2 lines, split it.
10. [PROHIBIT] Never paste raw XML into text frames, never deliver a deck that fails to reopen, never write over the source file without explicit authorization.
