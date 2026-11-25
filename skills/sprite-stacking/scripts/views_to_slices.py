#!/usr/bin/env python3
"""Turn four orthographic pixel-art views (top, side, front, back) into a sprite-stacking slice sheet.

Works on transparent PNGs and on opaque flat-background sheets (generated or hand-drawn),
in either a 2x2 grid or a 1x4 horizontal row.

Examples:
  python views_to_slices.py sheet.png slices.png --shade 0.25 --preview check.png
  python views_to_slices.py sheet.png slices.png --slices 36 --shade 0.2 --preview check.png --html viewer.html
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def remove_background(rgba: np.ndarray, tol: int = 28) -> np.ndarray:
    """Return RGBA array with transparent background.

    Keeps existing alpha when the sheet is already transparent; otherwise flood-fills
    from the outer border against the median corner color so interior highlights stay intact.
    """
    h, w = rgba.shape[:2]
    if (rgba[..., 3] < 128).mean() > 0.05:
        out = rgba.copy()
        out[..., 3] = np.where(out[..., 3] >= 128, 255, 0)
        return out

    rgb = rgba[..., :3].astype(np.int16)
    corners = np.array([rgb[0, 0], rgb[0, w - 1], rgb[h - 1, 0], rgb[h - 1, w - 1]])
    bg = np.median(corners, axis=0)
    close = np.abs(rgb - bg).max(axis=-1) <= tol

    bg_mask = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        if close[0, x] and not bg_mask[0, x]:
            bg_mask[0, x] = True
            q.append((0, x))
        if close[h - 1, x] and not bg_mask[h - 1, x]:
            bg_mask[h - 1, x] = True
            q.append((h - 1, x))
    for y in range(1, h - 1):
        if close[y, 0] and not bg_mask[y, 0]:
            bg_mask[y, 0] = True
            q.append((y, 0))
        if close[y, w - 1] and not bg_mask[y, w - 1]:
            bg_mask[y, w - 1] = True
            q.append((y, w - 1))

    while q:
        y, x = q.popleft()
        if y > 0 and close[y - 1, x] and not bg_mask[y - 1, x]:
            bg_mask[y - 1, x] = True
            q.append((y - 1, x))
        if y + 1 < h and close[y + 1, x] and not bg_mask[y + 1, x]:
            bg_mask[y + 1, x] = True
            q.append((y + 1, x))
        if x > 0 and close[y, x - 1] and not bg_mask[y, x - 1]:
            bg_mask[y, x - 1] = True
            q.append((y, x - 1))
        if x + 1 < w and close[y, x + 1] and not bg_mask[y, x + 1]:
            bg_mask[y, x + 1] = True
            q.append((y, x + 1))

    out = rgba.copy()
    out[bg_mask, 3] = 0
    out[~bg_mask, 3] = 255
    return out


def find_views(sheet: np.ndarray, order: str = "auto") -> list[np.ndarray]:
    """Locate the four views [top, side, front, back], dropping tiny specks and text labels."""
    solid = sheet[..., 3] >= 128
    h, w = solid.shape
    dilate_steps = max(2, min(6, round(min(h, w) / 260)))
    grown = solid.copy()
    for _ in range(dilate_steps):
        g = grown.copy()
        g[1:] |= grown[:-1]
        g[:-1] |= grown[1:]
        g[:, 1:] |= grown[:, :-1]
        g[:, :-1] |= grown[:, 1:]
        grown = g

    seen = np.zeros_like(solid)
    boxes: list[tuple[int, int, int, int, int]] = []
    for y0, x0 in zip(*np.nonzero(grown)):
        if seen[y0, x0]:
            continue
        stack = [(int(y0), int(x0))]
        seen[y0, x0] = True
        min_x = max_x = int(x0)
        min_y = max_y = int(y0)
        count = 0
        while stack:
            y, x = stack.pop()
            count += 1
            if x < min_x:
                min_x = x
            if x > max_x:
                max_x = x
            if y < min_y:
                min_y = y
            if y > max_y:
                max_y = y
            if y + 1 < h and grown[y + 1, x] and not seen[y + 1, x]:
                seen[y + 1, x] = True
                stack.append((y + 1, x))
            if y > 0 and grown[y - 1, x] and not seen[y - 1, x]:
                seen[y - 1, x] = True
                stack.append((y - 1, x))
            if x + 1 < w and grown[y, x + 1] and not seen[y, x + 1]:
                seen[y, x + 1] = True
                stack.append((y, x + 1))
            if x > 0 and grown[y, x - 1] and not seen[y, x - 1]:
                seen[y, x - 1] = True
                stack.append((y, x - 1))
        if count > 40:
            boxes.append((min_x, min_y, max_x + 1, max_y + 1, count))

    if not boxes:
        raise ValueError("No foreground drawings found. Check --bg-tol or image alpha.")

    big = max((b[2] - b[0]) * (b[3] - b[1]) for b in boxes)
    boxes = [b for b in boxes if (b[2] - b[0]) * (b[3] - b[1]) >= 0.14 * big]
    # Reading order: cluster into rows by vertical midpoint, then left to right
    row_band = max(1.0, h / 2.2)
    boxes.sort(key=lambda b: (round((b[1] + b[3]) / 2 / row_band), b[0]))

    if len(boxes) != 4:
        summary = [(b[0], b[1], b[2] - b[0], b[3] - b[1]) for b in boxes]
        raise ValueError(
            f"Found {len(boxes)} drawings {summary}, expected 4 (top, side, front, back). "
            "Check spacing between views or adjust --bg-tol."
        )

    views: list[np.ndarray] = []
    for x0, y0, x1, y1, _ in boxes:
        v = sheet[y0:y1, x0:x1].copy()
        ys, xs = np.nonzero(v[..., 3] >= 128)
        v = v[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
        v[..., 3] = np.where(v[..., 3] >= 128, 255, 0)
        views.append(v)

    if order == "reading":
        return views

    # Pick the (top, side) pair whose sizes agree: top length = side length, top width = front
    # width, side height = front height. Aspect alone misreads tall props (trees, towers).
    def err(t: int, s: int) -> float:
        tv, sv = views[t], views[s]
        rest = [views[i] for i in range(4) if i not in (t, s)]
        e = abs(math.log(tv.shape[0] / sv.shape[1]))
        e += sum(abs(math.log(tv.shape[1] / f.shape[1])) + abs(math.log(sv.shape[0] / f.shape[0])) for f in rest) / 2
        return e

    pairs = [(t, s) for t in range(4) for s in range(4) if t != s]
    best = min(err(t, s) for t, s in pairs)
    # ponytail: 0.1 log-tolerance ~ 10% size slack; reading order wins any near-tie
    t, s = next(p for p in pairs if err(*p) <= best + 0.1)
    rest = [views[i] for i in range(4) if i not in (t, s)]
    return [views[t], views[s], rest[0], rest[1]]


def strip_outline(v: np.ndarray, dark: int = 70) -> np.ndarray:
    """Replace 1px dark outer contour pixels with their interior neighbor's color."""
    if dark <= 0:
        return v
    m = v[..., 3] > 0
    pad = np.pad(m, 1)
    # 8-neighbour: an outline pixel in a concave corner (stem under a cap) touches empty space only diagonally
    edge = m & ~(
        pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:]
        & pad[:-2, :-2] & pad[:-2, 2:] & pad[2:, :-2] & pad[2:, 2:]
    )
    line = edge & (v[..., :3].astype(int).sum(-1) / 3 < dark)
    out = v.copy()
    for y, x in zip(*np.nonzero(line)):
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            yy, xx = y + dy, x + dx
            if 0 <= yy < m.shape[0] and 0 <= xx < m.shape[1] and m[yy, xx] and not line[yy, xx]:
                out[y, x] = v[yy, xx]
                break
    return out


def one_palette(views: list[np.ndarray], n: int) -> list[np.ndarray]:
    """Quantize all four views onto one shared palette of n colors without dithering."""
    if n <= 0:
        return views
    px = np.concatenate([v[v[..., 3] > 0][:, :3] for v in views])
    px = np.unique(px // 6 * 6 + 3, axis=0).astype(np.uint8)
    pal_img = Image.fromarray(px.reshape(1, -1, 3)).quantize(
        min(n, len(px)), method=Image.MEDIANCUT, dither=Image.NONE
    )
    k = min(n, len(px))
    pal = np.array(pal_img.getpalette()[: k * 3]).reshape(-1, 3)
    out: list[np.ndarray] = []
    for v in views:
        q = v.copy()
        rgb = v[..., :3].astype(np.int32)
        dist = ((rgb[..., None, :] - pal[None, None, :, :]) ** 2).sum(-1)
        q[..., :3] = pal[dist.argmin(-1)]
        out.append(q)
    return out


def fit(v: np.ndarray, w: int, h: int) -> np.ndarray:
    return np.array(Image.fromarray(v).resize((max(1, w), max(1, h)), Image.NEAREST))


def edge_colour(view: np.ndarray, row: int, i: int):
    xs = np.nonzero(view[row, :, 3])[0]
    return None if len(xs) == 0 else view[row, min(max(i, int(xs[0])), int(xs[-1])), :3]


def match_top(top: np.ndarray, side: np.ndarray) -> str:
    """Return 'down' or 'up' so dark cabin/window pixels sit over the tallest span of the side view."""
    tall = (side[..., 3] > 0).sum(0)
    tall = np.interp(np.linspace(0, len(tall) - 1, top.shape[0]), np.arange(len(tall)), tall)
    tall_mask = tall >= 0.8 * tall.max()
    dark = ((top[..., :3].astype(int).sum(-1) < 240) & (top[..., 3] > 0)).mean(1)
    return "down" if (dark * tall_mask).sum() >= (dark[::-1] * tall_mask).sum() else "up"


def _edge_row(view: np.ndarray, row: int, length: int) -> np.ndarray | None:
    xs = np.nonzero(view[row, :, 3])[0]
    if len(xs) == 0:
        return None
    idx = np.clip(np.arange(length), int(xs[0]), int(xs[-1]))
    return view[row, idx, :3]


def carve(
    top: np.ndarray,
    side: np.ndarray,
    front: np.ndarray,
    back: np.ndarray,
    shade: float = 0.0,
    round_: bool = False,
) -> np.ndarray:
    """Visual-hull carve into slices [z, y, x, rgba], z=0 on the ground."""
    L, W = top.shape[:2]
    H = side.shape[0]
    top_mask = top[..., 3] > 0
    occ = np.zeros((H, L, W), dtype=bool)
    yy_grid = xx_grid = None
    for z in range(H):
        r = H - 1 - z
        along = side[r, :, 3] > 0
        across = (front[r, :, 3] > 0) | (back[r, :, 3] > 0)
        occ[z] = top_mask & along[:, None] & across[None, :]
        if round_ and along.any() and across.any():
            # Lathe: clip the row to the ellipse its side and front spans describe. The hull alone
            # gives (widest top disk) & (square), so a tower narrower than its base carves square.
            ys, xs = np.nonzero(along)[0], np.nonzero(across)[0]
            if not (along[ys[0] : ys[-1] + 1].all() and across[xs[0] : xs[-1] + 1].all()):
                continue  # a gap in the row means separate posts, ropes or legs: keep them square
            if yy_grid is None:
                yy_grid, xx_grid = np.mgrid[0:L, 0:W]
            ry, rx = (ys[-1] - ys[0]) / 2 + 0.5, (xs[-1] - xs[0]) / 2 + 0.5
            occ[z] &= ((yy_grid - (ys[0] + ys[-1]) / 2) / ry) ** 2 + ((xx_grid - (xs[0] + xs[-1]) / 2) / rx) ** 2 < 1

    vol = np.zeros((H, L, W, 4), dtype=np.uint8)
    covered = np.zeros((L, W), dtype=bool)
    ix = np.arange(W)[None, :].repeat(L, 0)
    iy = np.arange(L)[:, None].repeat(W, 1)
    top_rgb = top[..., :3]

    for z in range(H - 1, -1, -1):
        r = H - 1 - z
        above = covered.copy()
        o = occ[z]
        covered |= o
        if not o.any():
            continue
        d = np.stack(
            [
                ix - np.maximum.accumulate(np.where(~o, ix, -1), axis=1),
                np.minimum.accumulate(np.where(~o, ix, W)[:, ::-1], axis=1)[:, ::-1] - ix,
                iy - np.maximum.accumulate(np.where(~o, iy, -1), axis=0),
                np.minimum.accumulate(np.where(~o, iy, L)[::-1], axis=0)[::-1] - iy,
            ]
        )
        face, depth = d.argmin(0), d.min(0)
        # Higher slices within 2px, corners included: views disagree by 1-2px at colour boundaries.
        pad_a = np.pad(above, 2)
        near_above = np.zeros_like(above)
        for dy in range(5):
            for dx in range(5):
                near_above |= pad_a[dy : dy + L, dx : dx + W]

        # Vectorized per-voxel colouring (matches scalar carve logic exactly)
        is_steep_step = (~above) & (depth <= 2) & near_above
        use_top = (~above) & (~is_steep_step)
        if z + 1 < H:
            use_above = above & (depth > 2) & (vol[z + 1, :, :, 3] > 0)
        else:
            use_above = np.zeros((L, W), dtype=bool)

        side_row = _edge_row(side, r, L)
        back_row = _edge_row(back, r, W)
        front_row = _edge_row(front, r, W)

        edge_rgb = top_rgb.copy()
        if side_row is not None:
            m = face < 2
            edge_rgb[m] = np.broadcast_to(side_row[:, None, :], (L, W, 3))[m]
        if back_row is not None:
            m = face == 2
            edge_rgb[m] = np.broadcast_to(back_row[None, :, :], (L, W, 3))[m]
        if front_row is not None:
            m = face > 2
            edge_rgb[m] = np.broadcast_to(front_row[None, :, :], (L, W, 3))[m]

        slice_rgb = np.where(use_top[..., None], top_rgb, edge_rgb)
        if z + 1 < H:
            slice_rgb = np.where(use_above[..., None], vol[z + 1, :, :, :3], slice_rgb)

        if shade:
            shade_mask = (above | is_steep_step) & (depth <= 2) & o
            if shade_mask.any():
                factor = 1.0 - shade * (1.0 - z / max(H - 1, 1)) - shade * 0.4
                shaded = np.clip(slice_rgb[shade_mask].astype(float) * factor, 0, 255).astype(np.uint8)
                slice_rgb = slice_rgb.copy()
                slice_rgb[shade_mask] = shaded

        vol[z, o, :3] = slice_rgb[o]
        vol[z, o, 3] = 255
    return vol


def views_to_slices(
    sheet: np.ndarray,
    *,
    slices: int | None = None,
    top_nose: str = "auto",
    side_nose: str = "left",
    order: str = "auto",
    colours: int = 24,
    shade: float = 0.2,
    dark_thresh: int = 70,
    bg_tol: int = 28,
    round_: bool = False,
) -> tuple[np.ndarray, list[np.ndarray]]:
    clean = remove_background(sheet, tol=bg_tol)
    raw_views = find_views(clean, order=order)
    top, side, front, back = raw_views

    if side_nose == "left":
        side_aligned = side[:, ::-1]
    else:
        side_aligned = side

    # Determine target pixel grid (L, W, H)
    raw_h = side.shape[0]
    if slices is None:
        # Auto-downscale high-res AI sheets while leaving native pixel art untouched
        target_h = 36 if raw_h > 64 else raw_h
    elif slices == 0:
        target_h = raw_h
    else:
        target_h = slices

    if target_h != raw_h:
        L = max(4, round(target_h * side.shape[1] / side.shape[0]))
        W = max(4, round(L * top.shape[1] / top.shape[0]))
        H = target_h
        top = fit(top, W, L)
        side_aligned = fit(side_aligned, L, H)
        front = fit(front, W, H)
        back = fit(back, W, H)
    else:
        L, W = top.shape[:2]
        H = max(2, round(side.shape[0] * L / side.shape[1]))
        side_aligned = fit(side_aligned, L, H)
        front = fit(front, W, H)
        back = fit(back, W, H)

    # Back view is seen from behind (+y -> -y), mirror x to match top view's x axis
    back_aligned = back[:, ::-1]

    cleaned = [strip_outline(v, dark=dark_thresh) for v in (top, side_aligned, front, back_aligned)]
    top, side_aligned, front, back_aligned = one_palette(cleaned, colours)

    if top_nose == "auto":
        top_nose = match_top(top, side_aligned)
    if top_nose == "up":
        top = top[::-1]

    vol = carve(top, side_aligned, front, back_aligned, shade=shade, round_=round_)
    display_views = [
        top,
        side_aligned[:, ::-1] if side_nose == "left" else side_aligned,
        front,
        back_aligned[:, ::-1],
    ]
    return vol, display_views


def render_stack_image(
    vol: np.ndarray,
    angle_deg: float,
    squash: float = 0.75,
    spacing: float = 1.0,
    shadow: bool = True,
    outline: bool = True,
) -> Image.Image:
    """Render one crisp 1x art-pixel frame of the stacked volume for visual verification."""
    n, h, w = vol.shape[:3]
    diag = int(math.ceil(math.hypot(w, h))) + 8
    lift_max = int(math.ceil((n - 1) * spacing))
    cw = diag + 12
    ch = int(math.ceil(diag * squash)) + lift_max + 16
    cx = cw // 2
    base_y = ch - int(math.ceil(diag * squash / 2)) - 6

    rad = math.radians(angle_deg)
    ca, sa = math.cos(rad), math.sin(rad)

    canvas = np.zeros((ch, cw, 4), dtype=np.uint8)
    yy, xx = np.mgrid[0:ch, 0:cw]
    dx = xx - cx

    if shadow:
        # Union footprint of all slices projected flat on the ground, offset down-right
        footprint = (vol[..., 3] > 0).any(axis=0)
        foot_img = np.zeros((h, w, 4), dtype=np.uint8)
        foot_img[footprint] = (0, 0, 0, 255)
        dy_s = (yy - (base_y + 3)) / squash
        dx_s = (xx - (cx + 2))
        sx = np.floor(dx_s * ca + dy_s * sa + w / 2.0).astype(np.int32)
        sy = np.floor(-dx_s * sa + dy_s * ca + h / 2.0).astype(np.int32)
        valid = (sx >= 0) & (sx < w) & (sy >= 0) & (sy < h)
        vy, vx = np.nonzero(valid)
        hit = foot_img[sy[vy, vx], sx[vy, vx], 3] > 0
        canvas[vy[hit], vx[hit]] = (186, 198, 212, 255)

    body = np.zeros((ch, cw, 4), dtype=np.uint8)
    for z in range(n):
        lift_y = round(z * spacing)
        dy = (yy - (base_y - lift_y)) / squash
        sx = np.floor(dx * ca + dy * sa + w / 2.0).astype(np.int32)
        sy = np.floor(-dx * sa + dy * ca + h / 2.0).astype(np.int32)
        valid = (sx >= 0) & (sx < w) & (sy >= 0) & (sy < h)
        vy, vx = np.nonzero(valid)
        px = vol[z, sy[vy, vx], sx[vy, vx]]
        opaque = px[:, 3] > 0
        body[vy[opaque], vx[opaque]] = px[opaque]

    if outline:
        alpha = body[..., 3] > 0
        pad = np.pad(alpha, 1)
        ring = ~alpha & (pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:])
        canvas[ring] = (24, 28, 36, 255)

    solid = body[..., 3] > 0
    canvas[solid] = body[solid]
    return Image.fromarray(canvas)


def thin_runs(vol: np.ndarray, min_run: int = 3) -> list[tuple[int, int]]:
    """Slice ranges holding a part with no 2x2 block (a 1px post, rope, antenna or rail) for at
    least min_run slices in a row. Renderers sample each rotated slice per screen pixel, so such a
    part drops between pixels at some angles and blinks in and out as the stack turns."""
    thin = []
    for s in vol[..., 3] > 0:
        b = s[:-1, :-1] & s[1:, :-1] & s[:-1, 1:] & s[1:, 1:]
        block = np.zeros_like(s)
        for dy in (0, 1):
            for dx in (0, 1):
                block[dy : dy + b.shape[0], dx : dx + b.shape[1]] |= b
        seen, found = np.zeros_like(s), False
        for y0, x0 in zip(*np.nonzero(s)):
            if seen[y0, x0] or found:
                continue
            stack, seen[y0, x0], solid = [(y0, x0)], True, False
            while stack:
                y, x = stack.pop()
                solid |= bool(block[y, x])
                for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                    if 0 <= yy < s.shape[0] and 0 <= xx < s.shape[1] and s[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True
                        stack.append((yy, xx))
            found = not solid
        thin.append(found)
    runs, start = [], None
    for z, t in enumerate(thin + [False]):
        if t and start is None:
            start = z
        elif not t and start is not None:
            if z - start >= min_run:
                runs.append((start, z - 1))
            start = None
    return runs


def build_preview(vol: np.ndarray, views: list[np.ndarray], out_path: Path) -> None:
    """Save a crisp visual check sheet: 4 views + 4 turntable angles + exploded stack."""
    renders = [
        ("35 deg", render_stack_image(vol, 35, squash=0.75, spacing=1.0)),
        ("135 deg", render_stack_image(vol, 135, squash=0.75, spacing=1.0)),
        ("225 deg", render_stack_image(vol, 225, squash=0.75, spacing=1.0)),
        ("315 deg", render_stack_image(vol, 315, squash=0.75, spacing=1.0)),
        ("exploded", render_stack_image(vol, 35, squash=0.75, spacing=2.4)),
    ]
    scale = max(2, min(6, round(180 / max(renders[0][1].width, 1))))
    pad = 16
    cell_w = max(im.width * scale for _, im in renders) + pad
    cell_h = max(im.height * scale for _, im in renders) + pad + 20

    top_row_h = max(v.shape[0] for v in views) * scale + 36
    total_w = max(cell_w * len(renders) + pad, sum(v.shape[1] * scale + pad * 2 for v in views))
    total_h = top_row_h + cell_h + pad * 2

    bg = Image.new("RGBA", (total_w, total_h), (242, 245, 249, 255))
    draw = ImageDraw.Draw(bg)

    # Row 1: extracted views
    x = pad
    for label, v in zip(("TOP", "SIDE", "FRONT", "BACK"), views):
        im = Image.fromarray(v).resize((v.shape[1] * scale, v.shape[0] * scale), Image.NEAREST)
        bg.paste(im, (x, pad + 18), im)
        draw.text((x, pad), f"{label} ({v.shape[1]}x{v.shape[0]})", fill=(70, 80, 95, 255))
        x += im.width + pad * 2

    # Row 2: rendered stack angles + exploded
    y0 = top_row_h + pad
    for i, (label, im) in enumerate(renders):
        up = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
        cx = pad + i * cell_w + (cell_w - up.width) // 2
        cy = y0 + 18 + (cell_h - 20 - up.height) // 2
        bg.paste(up, (cx, cy), up)
        draw.text((pad + i * cell_w + 4, y0), label, fill=(70, 80, 95, 255))

    bg.convert("RGB").save(out_path)


def compute_normals(vol: np.ndarray) -> np.ndarray:
    """Estimate outward 3D unit normals per occupied voxel, packed as RGBA uint8."""
    occ = (vol[..., 3] > 0).astype(np.float32)
    p = np.pad(occ, 1, mode="constant", constant_values=0.0)

    def smooth_x(a: np.ndarray) -> np.ndarray:
        return a[:, :, :-2] + 2.0 * a[:, :, 1:-1] + a[:, :, 2:]

    def smooth_y(a: np.ndarray) -> np.ndarray:
        return a[:, :-2, :] + 2.0 * a[:, 1:-1, :] + a[:, 2:, :]

    def smooth_z(a: np.ndarray) -> np.ndarray:
        return a[:-2, :, :] + 2.0 * a[1:-1, :, :] + a[2:, :, :]

    nz = smooth_x(smooth_y(p[:-2, :, :] - p[2:, :, :]))
    ny = smooth_x(smooth_z(p[:, :-2, :] - p[:, 2:, :]))
    nx = smooth_y(smooth_z(p[:, :, :-2] - p[:, :, 2:]))

    mag = np.sqrt(nx * nx + ny * ny + nz * nz)
    zero = mag < 1e-5
    nz = np.where(zero, 1.0, nz)
    mag = np.where(zero, 1.0, mag)
    nx /= mag
    ny /= mag
    nz /= mag

    out = np.zeros_like(vol)
    solid = vol[..., 3] > 0
    out[solid, 0] = np.clip(np.round((nx[solid] * 0.5 + 0.5) * 255.0), 0, 255).astype(np.uint8)
    out[solid, 1] = np.clip(np.round((ny[solid] * 0.5 + 0.5) * 255.0), 0, 255).astype(np.uint8)
    out[solid, 2] = np.clip(np.round((nz[solid] * 0.5 + 0.5) * 255.0), 0, 255).astype(np.uint8)
    out[solid, 3] = 255
    return out


def detect_emissive(vol: np.ndarray) -> np.ndarray:
    """Detect small bright/vivid surface accents (headlights, windows, neon) as an RGBA emissive volume."""
    solid = vol[..., 3] > 0
    out = np.zeros_like(vol)
    if not solid.any():
        return out

    p = np.pad(solid, 1, mode="constant", constant_values=False)
    surface = solid & ~(
        p[:-2, 1:-1, 1:-1]
        & p[2:, 1:-1, 1:-1]
        & p[1:-1, :-2, 1:-1]
        & p[1:-1, 2:, 1:-1]
        & p[1:-1, 1:-1, :-2]
        & p[1:-1, 1:-1, 2:]
    )
    surf_count = int(surface.sum())
    if surf_count == 0:
        return out

    rgb = vol[..., :3].astype(np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    sat = (max_c - min_c) / np.maximum(max_c, 1.0)

    cand = surface & (
        ((luma >= 180.0) & ((sat >= 0.30) | (luma >= 232.0)))
        | ((max_c >= 215.0) & (sat >= 0.62) & (luma >= 110.0))
    )
    if not cand.any():
        return out

    # Exclude dominant body colors (> 14% of surface) so a bright red car or white wall doesn't glow.
    surf_rgb = vol[surface, :3]
    surf_keys = (
        (surf_rgb[:, 0].astype(np.uint32) << 16)
        | (surf_rgb[:, 1].astype(np.uint32) << 8)
        | surf_rgb[:, 2].astype(np.uint32)
    )
    uniq, counts = np.unique(surf_keys, return_counts=True)
    dominant = set(int(k) for k, c in zip(uniq, counts) if c / surf_count > 0.14)

    cz, cy, cx = np.nonzero(cand)
    cand_rgb = vol[cz, cy, cx, :3]
    cand_keys = (
        (cand_rgb[:, 0].astype(np.uint32) << 16)
        | (cand_rgb[:, 1].astype(np.uint32) << 8)
        | cand_rgb[:, 2].astype(np.uint32)
    )
    keep = np.array([int(k) not in dominant for k in cand_keys], dtype=bool)
    if keep.any():
        out[cz[keep], cy[keep], cx[keep]] = vol[cz[keep], cy[keep], cx[keep]]
    return out


def to_data_uri(arr: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def build_html_viewer(vol: np.ndarray, views: list[np.ndarray], out_path: Path, title: str) -> None:
    template_path = Path(__file__).with_name("viewer.html")
    html = template_path.read_text(encoding="utf-8")
    strip = np.concatenate(list(vol), axis=1)
    payload = {
        "title": title,
        "slices": int(vol.shape[0]),
        "sliceWidth": int(vol.shape[2]),
        "sliceHeight": int(vol.shape[1]),
        "sheet": to_data_uri(strip),
        "top": to_data_uri(views[0]),
        "side": to_data_uri(views[1]),
        "front": to_data_uri(views[2]),
        "back": to_data_uri(views[3]),
    }
    marker = "/*__EMBEDDED_STACK__*/null"
    if marker not in html:
        raise RuntimeError(f"Template marker not found in {template_path}")
    out_path.write_text(html.replace(marker, json.dumps(payload), 1), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="Carve 4 orthographic pixel-art views into a sprite-stacking slice strip.")
    p.add_argument("sheet", type=Path, help="Input 4-view PNG (transparent or solid background)")
    p.add_argument("out", type=Path, help="Output horizontal slice strip PNG (ground slice on left)")
    p.add_argument("--slices", type=int, default=None, help="Target slice count / height (default: auto, 0 = native)")
    p.add_argument("--top-nose", choices=["auto", "up", "down"], default="auto")
    p.add_argument("--side-nose", choices=["left", "right"], default="left")
    p.add_argument("--order", choices=["auto", "reading"], default="auto", help="auto = match views by proportion; reading = top,side,front,back")
    p.add_argument("--colours", type=int, default=24, help="Shared palette size (0 = keep original colors)")
    p.add_argument("--shade", type=float, default=0.2, help="Darken side faces near ground (0 = flat, 0.2-0.25 = subtle depth)")
    p.add_argument("--round", action="store_true", help="Lathe each slice to an ellipse: towers, balloons, pots, bottles")
    p.add_argument("--dark-thresh", type=int, default=70, help="Luminance cutoff for stripping 1px dark view outlines (0 = disable)")
    p.add_argument("--bg-tol", type=int, default=28, help="Color tolerance for flood-fill background removal on opaque sheets")
    p.add_argument("--preview", type=Path, default=None, help="Save a visual verification contact sheet PNG")
    p.add_argument("--html", type=Path, default=None, help="Save a self-contained interactive HTML turntable/scan viewer")
    p.add_argument("--normals", type=Path, default=None, help="Save a matching 3D normal-map slice strip PNG")
    p.add_argument("--emissive", type=Path, default=None, help="Save an auto-detected emissive mask slice strip PNG")
    a = p.parse_args()

    sheet = np.array(Image.open(a.sheet).convert("RGBA"))
    vol, views = views_to_slices(
        sheet,
        slices=a.slices,
        top_nose=a.top_nose,
        side_nose=a.side_nose,
        order=a.order,
        colours=a.colours,
        shade=a.shade,
        dark_thresh=a.dark_thresh,
        bg_tol=a.bg_tol,
        round_=a.round,
    )

    a.out.parent.mkdir(parents=True, exist_ok=True)
    strip = np.concatenate(list(vol), axis=1)
    Image.fromarray(strip).save(a.out)
    print(f"{vol.shape[0]} slices of {vol.shape[2]} x {vol.shape[1]} px -> {a.out}")
    for z0, z1 in thin_runs(vol):
        print(f"warning: slices {z0}-{z1} hold a 1px-thin part; it will blink as the stack turns. "
              "Draw posts, ropes and antennas at least 2px wide in the views.")

    if a.normals:
        a.normals.parent.mkdir(parents=True, exist_ok=True)
        norm_strip = np.concatenate(list(compute_normals(vol)), axis=1)
        Image.fromarray(norm_strip).save(a.normals)
        print(f"normals -> {a.normals}")

    if a.emissive:
        a.emissive.parent.mkdir(parents=True, exist_ok=True)
        emis_strip = np.concatenate(list(detect_emissive(vol)), axis=1)
        Image.fromarray(emis_strip).save(a.emissive)
        print(f"emissive -> {a.emissive}")

    if a.preview:
        a.preview.parent.mkdir(parents=True, exist_ok=True)
        build_preview(vol, views, a.preview)
        print(f"preview -> {a.preview}")

    if a.html:
        a.html.parent.mkdir(parents=True, exist_ok=True)
        build_html_viewer(vol, views, a.html, title=a.out.stem)
        print(f"viewer -> {a.html}")


if __name__ == "__main__":
    main()
