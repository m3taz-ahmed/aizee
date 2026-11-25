# Engine recipes

All of these run the loop from SKILL.md step 3: rotate each slice around its centre, scale y by `squash`, lift by `-round(z * spacing)`, whole-pixel position, nearest filtering.

## Web (Canvas 2D, React)

For a crisp outer outline, render into an offscreen canvas at 1x art-pixel size, outline its alpha once, then draw it onto the display canvas at an integer scale (`4`, `6`, etc.) with `imageSmoothingEnabled = false`. In software pixel-buffer rasterizers, rotate around symmetric centres `(w - 1) * 0.5, (h - 1) * 0.5` with `Math.round(...)` nearest sampling to avoid 0.5-art-px rotational drift across 90° turns. For smooth 60 fps animation (bobbing, orbiting, child props on a spinning parent), keep positions in continuous screen-space floats and round only once at the final 1-screen-pixel `drawImage` destination (`Math.round(dx), Math.round(dy)`). Animate grounded prop entrances bottom-to-top via per-slice `lifts` (extending the reveal frontier past `count` by the blend width so top slices finish easing before returning `null`), add per-slice lateral `xOffsets` scaled by `(z / (count - 1))²` for anchored swaying props like kelp or banners, and apply per-slice `(xOffsets, yOffsets)` proportional to `(z - centerZ) * sin(pitchAngle)` for 3D pitch/roll tilt on leaping creatures or rolling hulls. Validate `sheet.width % count === 0` at load time, verify each strip's native nose axis (`+x`, `+y`, or `-y`) visually before computing `turn` from velocity, and depth-tint submerged stacks toward the water hue (omitting hard outlines) so surface and underwater layers separate cleanly. For multi-frame articulated creatures (fluke-beats, wing-waves, tail-swishes, bird flaps/glides), load `f0..fN-1` strips with identical `(w, h, count)`, extra Z-slice headroom, and shared symmetric pivots, selecting frames deterministically from the creature's physical phase. `scripts/viewer.html` implements the full reference pipeline, plus orbit, slice scan, exploded view and 16-direction export.

Without an outline, draw straight to the canvas:

```ts
function drawStack(
  ctx: CanvasRenderingContext2D,
  sheet: HTMLImageElement | HTMLCanvasElement,
  count: number,
  x: number,
  y: number,
  turn: number,
  squash = 0.75,
  spacing = 1,
) {
  const w = sheet.width / count;
  const h = sheet.height;
  const ox = -(w - 1) * 0.5;
  const oy = -(h - 1) * 0.5;
  ctx.imageSmoothingEnabled = false;
  for (let z = 0; z < count; z++) {
    ctx.save();
    ctx.translate(Math.round(x), Math.round(y - z * spacing));
    ctx.scale(1, squash);
    ctx.rotate(turn);
    ctx.drawImage(sheet, z * w, 0, w, h, ox, oy, w, h);
    ctx.restore();
  }
}
```

## Godot 4 (`Node2D`)

Set the default texture filter to Nearest and keep the node on whole pixels.

```gdscript
extends Node2D

@export var sheet: Texture2D
@export var slices := 15
@export var turn := 0.0:
	set(v):
		turn = v
		queue_redraw()
@export_range(0.1, 1.0) var squash := 0.75
@export var spacing := 1.0

func _draw() -> void:
	if sheet == null:
		return
	var w := float(sheet.get_width()) / slices
	var h := float(sheet.get_height())
	var rect := Rect2(-floorf(w / 2.0), -floorf(h / 2.0), w, h)
	var spin := Transform2D(turn, Vector2.ZERO)
	for z in slices:
		var lift := Transform2D(Vector2(1, 0), Vector2(0, squash), Vector2(0, -roundf(z * spacing)))
		draw_set_transform_matrix(lift * spin)
		draw_texture_rect_region(sheet, rect, Rect2(z * w, 0, w, h))
```

`_draw()` only runs again after `queue_redraw()`, which is why `turn` has a setter. For an outer outline, draw the stack into a `SubViewport` and run a 1px silhouette outline shader on its texture once.

## Unity

One child `SpriteRenderer` per slice with ascending sorting order, Point filter mode, parent snapped to whole pixels. To outline, render all slices into a `RenderTexture` once and outline that.

## Phaser, Pygame, anything else

The same loop: rotate each slice around its centre, scale y by `squash`, lift by `-round(z * spacing)`, nearest filter.

## Spherical bodies & world-space terminator lighting

Under orthographic pitch `squash` and vertical slice lift `spacing`, a sphere with horizontal radius `R_xy` projects to an exact circle only when its vertical slice half-height satisfies the Cauchy-Schwarz envelope:

```ts
// Vertical half-height in slices so the projected silhouette is circular
const R_z = (R_xy * Math.sqrt(1 - squash * squash)) / spacing;
```

For rotating planets or moons, keep the strip in pure albedo (cloud bands, storms, craters) and evaluate `dot(normal, sunDir)` in world space when blitting each slice so the surface rotates smoothly through a fixed day/night terminator. For planetary rings, draw back-half particles (`y_local < 0`) before the planet stack, front-half particles (`y_local >= 0`) after, and darken particles inside the cylindrical shadow cone cast away from `sunDir`.
