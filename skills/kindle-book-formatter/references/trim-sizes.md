# KDP Trim Size Margin Reference

All margins follow KDP's minimum requirements plus comfortable reading buffer.

## Supported Trim Sizes

| Code | Dimensions | Inner | Outer | Top | Bottom | Best For |
|------|-----------|-------|-------|-----|--------|---------|
| `5x8` | 5" × 8" | 0.875" | 0.625" | 0.75" | 0.875" | Novellas, poetry, short books |
| `5.5x8.5` | 5.5" × 8.5" | 0.875" | 0.625" | 0.75" | 0.875" | Novels, memoirs |
| `6x9` | 6" × 9" | 1.0" | 0.75" | 1.0" | 1.25" | **Most popular. Nonfiction, guides, self-help** |
| `8.5x11` | 8.5" × 11" | 1.25" | 1.0" | 1.0" | 1.25" | Workbooks, textbooks, illustrated |

## KDP Minimum Margins (for reference)

For books with 24–150 pages: 0.375" minimum  
For 151–300 pages: 0.5" minimum gutter (inner margin)  
For 301–500 pages: 0.625" minimum gutter  
For 500+ pages: 0.75" minimum gutter  

The `build_kindle.py` defaults exceed minimums with comfortable reading margins.

## To Use a Non-Standard Size

Modify the `TRIM_SIZES` dict in `build_kindle.py`, or pass a custom geometry string. For example, for a 7×10" workbook:

```bash
python3 build_kindle.py --input book.md --output ./out/ \
  --title "My Workbook" --author "Author" \
  --trim 6x9   # start with closest preset, then customize
```

Then manually edit the geometry in the script for the exact size.

## Black & White vs Color Interior

- **Black & White (standard)**: Cheaper per page. Best for text-only books.
- **Black & White with cream paper**: Warmer feel, popular for novels.
- **Color**: More expensive, required for color photos/illustrations.

The PDF from this skill works for all three — the distinction is set in KDP's paperback settings, not in the file itself.

## Page Count Estimation

| Trim | Words per page |
|------|---------------|
| 5×8 | ~200–220 |
| 6×9 | ~250–280 |
| 8.5×11 | ~400–450 |

For a 50,000 word novel at 6×9: roughly 180–200 pages.
