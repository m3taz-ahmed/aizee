---
name: xlsx
description: Read, create, or edit Excel .xlsx workbooks — read sheets to dataframes, generate workbooks with formulas, styles, charts, and conditional formatting, or update existing files cell-by-cell while preserving formulas. Use whenever the user has a .xlsx or wants a spreadsheet deliverable. Not for CSV-only tasks, .docx, or Google Sheets.
triggers:
  - xlsx
  - excel
  - .xlsx
  - spreadsheet
  - workbook
personas:
  - DEV
tech_stack:
  - python
---
[SKILL] xlsx
[OBJ] Produce correct, valid .xlsx workbooks — accurate data, working formulas, and no silent type corruption.
[RULES]
1. [REQ] Know the format: .xlsx is a ZIP of OOXML; sheets under xl/worksheets/, shared strings in xl/sharedStrings.xml, formulas stored as text and recalculated by Excel on open.
2. [REQ] Toolchain by task: openpyxl for create/edit with full control (formulas, styles, merged cells, charts); pandas read_excel/to_excel for bulk data movement; NEVER use openpyxl + pandas interchangeably when formulas matter — pandas writes values, not formulas.
3. [REQ] Formulas: write formula strings ("=SUM(A1:A10)") — openpyxl stores them; it does NOT evaluate. For computed values needed in-file, write values or set wb.calculation properties so Excel recalcs on open.
4. [REQ] data_only trap: openpyxl data_only=True returns cached values — None for files never opened in Excel; detect None-vs-formula and report, don't silently emit blanks.
5. [REQ] Types: write real dates as datetime objects (number_format="yyyy-mm-dd"), real numbers as int/float — never stringify numbers to keep them sum-able.
6. [REQ] Styles: header row bold + fill via PatternFill, column widths via column_dimensions, freeze panes via ws.freeze_panes="A2", autofilter via ws.auto_filter.ref.
7. [REQ] Editing existing workbooks: load with keep_vba only for .xlsm, keep_links preserved; charts/images survive openpyxl round-trips but data validation may need re-check.
8. [CMD] Validate: reopen the output, assert sheet names, spot-check a formula cell (cell.value startswith "="), and confirm row counts match input data.
9. [CMD] For large data (>50k rows) use pandas/openpyxl write_only mode or consider .csv delivery instead — memory grows fast otherwise.
10. [PROHIBIT] Never write numbers as text, never destroy an existing workbook's formulas by rewriting cells with computed values, never overwrite the source file without explicit authorization.
