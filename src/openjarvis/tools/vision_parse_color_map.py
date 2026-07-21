#!/usr/bin/env python3
"""Color-by-number vision parser for Jarvis.

Backup vision path when vision models fail or are less convenient.
Ports the parsing logic from:
  C:/Users/krist/Desktop/Color-by-number-main/Color-by-number-main/services/imageProcessor.ts

Input: image path
Output: color/number/location key + region map + palette
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


@dataclass
class RGB:
    r: int
    g: int
    b: int


@dataclass
class PaletteColor:
    id: int
    rgb: RGB
    hex: str
    textColor: str
    count: int


@dataclass
class Region:
    id: int
    colorId: int
    pixels: List[int]
    centroid: Tuple[int, int]
    borderPixels: List[int]


@dataclass
class ProcessedImage:
    originalWidth: int
    originalHeight: int
    regions: List[Region]
    palette: List[PaletteColor]
    pixelData: List[int]
    regionMap: List[int]
    key: Dict[str, Any]


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).to_bytes(4, "big").hex()[1:]


def _get_contrast_color(r: int, g: int, b: int) -> str:
    yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000
    return "#000000" if yiq >= 128 else "#ffffff"


def _color_dist_sq(c1: RGB, c2: RGB) -> float:
    return (c1.r - c2.r) ** 2 + (c1.g - c2.g) ** 2 + (c1.b - c2.b) ** 2


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _load_image(image_path: str) -> Tuple[List[int], int, int]:
    path = os.path.expanduser(image_path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Image not found: {path}")

    try:
        from PIL import Image  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required for vision parsing. Install with: pip install Pillow"
        ) from exc

    img = Image.open(path)
    img = img.convert("RGB")
    width, height = img.size
    pixels = list(img.getdata())
    flat: List[int] = []
    for p in pixels:
        flat.extend([_clamp(int(p[0]), 0, 255), _clamp(int(p[1]), 0, 255), _clamp(int(p[2]), 0, 255), 255])
    return flat, width, height


def _build_color_key(
    image_path: str,
    regions: List[Region],
    palette: List[PaletteColor],
    width: int,
    height: int,
    region_map: List[int],
) -> Dict[str, Any]:
    by_color: Dict[int, List[Dict[str, Any]]] = {}
    for region in regions:
        by_color.setdefault(region.colorId, []).append({
            "region_id": region.id,
            "centroid": {"x": region.centroid[0], "y": region.centroid[1]},
            "pixel_count": len(region.pixels),
            "border_pixels": region.borderPixels[:20],
        })

    color_entries = []
    for color in palette:
        entries = by_color.get(color.id, [])
        color_entries.append({
            "color_id": color.id,
            "hex": color.hex,
            "rgb": asdict(color.rgb),
            "textColor": color.textColor,
            "pixel_count": color.count,
            "region_count": len(entries),
            "regions": entries,
        })

    digest = hashlib.sha256(json.dumps({
        "w": width,
        "h": height,
        "colors": [c.hex for c in palette],
        "region_count": len(regions),
    }, sort_keys=True).encode()).hexdigest()[:16]

    return {
        "image_path": image_path,
        "width": width,
        "height": height,
        "digest": digest,
        "color_count": len(palette),
        "region_count": len(regions),
        "colors": color_entries,
        "map": "color_id -> region_id -> centroid/location",
        "key": "number = color_id; location = centroid(x,y) per region",
    }


def process_image(
    image_path: str,
    max_colors: int = 48,
    merge_min_size_factor: int = 40000,
) -> ProcessedImage:
    data, width, height = _load_image(image_path)
    pixel_count = width * height

    # 1. K-Means quantization
    centroids: List[RGB] = []
    for i in range(max_colors):
        idx = (i * 9973 + 101) % max(1, pixel_count)
        r = data[idx * 4]
        g = data[idx * 4 + 1]
        b = data[idx * 4 + 2]
        centroids.append(RGB(r, g, b))

    assignments = [0] * pixel_count
    iterations = 10
    for _ in range(iterations):
        sums = [[0, 0, 0] for _ in range(max_colors)]
        counts = [0] * max_colors
        for i in range(pixel_count):
            r, g, b = data[i * 4], data[i * 4 + 1], data[i * 4 + 2]
            best = 0
            best_d = float("inf")
            for c in range(max_colors):
                d = (r - centroids[c].r) ** 2 + (g - centroids[c].g) ** 2 + (b - centroids[c].b) ** 2
                if d < best_d:
                    best_d = d
                    best = c
            assignments[i] = best
            sums[best][0] += r
            sums[best][1] += g
            sums[best][2] += b
            counts[best] += 1

        changed = False
        for c in range(max_colors):
            if counts[c] > 0:
                nr = round(sums[c][0] / counts[c])
                ng = round(sums[c][1] / counts[c])
                nb = round(sums[c][2] / counts[c])
                if (nr, ng, nb) != (centroids[c].r, centroids[c].g, centroids[c].b):
                    centroids[c] = RGB(nr, ng, nb)
                    changed = True
        if not changed:
            break

    unique_indices = sorted(set(assignments))
    palette = []
    for new_idx, old_idx in enumerate(unique_indices):
        rgb = centroids[old_idx]
        palette.append(PaletteColor(
            id=new_idx + 1,
            rgb=rgb,
            hex=_rgb_to_hex(rgb.r, rgb.g, rgb.b),
            textColor=_get_contrast_color(rgb.r, rgb.g, rgb.b),
            count=0,
        ))
    remap = {old_idx: new_idx for new_idx, old_idx in enumerate(unique_indices)}
    remapped = [remap[a] for a in assignments]
    for ridx in remapped:
        palette[ridx].count += 1

    # 2. Connected components / flood fill
    region_map = [-1] * pixel_count
    regions: List[Region] = []
    visited = [False] * pixel_count
    for i in range(pixel_count):
        if visited[i]:
            continue
        color_id = remapped[i]
        stack = [i]
        visited[i] = True
        pixels = []
        while stack:
            p = stack.pop()
            region_map[p] = len(regions)
            pixels.append(p)
            px = p % width
            for n in (p - width, p + width, px - 1 if px > 0 else -1, px + 1 if px < width - 1 else -1):
                if 0 <= n < pixel_count and not visited[n] and remapped[n] == color_id:
                    visited[n] = True
                    stack.append(n)
        regions.append(Region(id=len(regions), colorId=color_id, pixels=pixels, centroid=(0, 0), borderPixels=[]))

    # 3. Merge small regions
    dynamic_min_size = max(20, math.floor(pixel_count / max(1, merge_min_size_factor)))
    region_obj_map = {r.id: r for r in regions}
    active = set(r.id for r in regions)
    sorted_ids = sorted(active, key=lambda rid: len(region_obj_map[rid].pixels))
    for r_id in sorted_ids:
        region = region_obj_map[r_id]
        if len(region.pixels) >= dynamic_min_size:
            continue
        neighbors = set()
        for p in region.pixels:
            px = p % width
            for adj in (p - width, p + width, px - 1 if px > 0 else -1, px + 1 if px < width - 1 else -1):
                if 0 <= adj < pixel_count:
                    nid = region_map[adj]
                    if nid != region.id and nid in active:
                        neighbors.add(nid)
        if not neighbors:
            continue
        best = None
        best_diff = float("inf")
        for nid in neighbors:
            nregion = region_obj_map[nid]
            diff = _color_dist_sq(palette[region.colorId].rgb, palette[nregion.colorId].rgb)
            if diff < best_diff:
                best_diff = diff
                best = nid
        target = region_obj_map[best]
        for p in region.pixels:
            region_map[p] = target.id
            target.pixels.append(p)
        active.discard(region.id)

    final_regions = [region_obj_map[rid] for rid in active if rid in region_obj_map]

    # 4. Borders/centroids
    for region in final_regions:
        sum_x = 0
        sum_y = 0
        borders = []
        for p in region.pixels:
            px = p % width
            py = p // width
            sum_x += px
            sum_y += py
            is_border = False
            for adj in (p - width, p + width, px - 1 if px > 0 else -1, px + 1 if px < width - 1 else -1):
                if not (0 <= adj < pixel_count and region_map[adj] == region.id):
                    is_border = True
                    break
            if is_border:
                borders.append(p)
        cx = round(sum_x / len(region.pixels))
        cy = round(sum_y / len(region.pixels))
        region.centroid = (cx, cy)
        region.borderPixels = borders
        palette[region.colorId].count = max(palette[region.colorId].count, len(region.pixels))

    key = _build_color_key(image_path, final_regions, palette, width, height, region_map)
    return ProcessedImage(
        originalWidth=width,
        originalHeight=height,
        regions=final_regions,
        palette=palette,
        pixelData=data,
        regionMap=region_map,
        key=key,
    )


@ToolRegistry.register("vision_parse_color_map")
class VisionParseColorMapTool(BaseTool):
    """Parse an image into a color/number/location map.

    Backup vision path when vision models fail or are less convenient.
    Returns palette, regions, centroids, borders, and a usable key.
    """

    tool_id = "vision_parse_color_map"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="vision_parse_color_map",
            description=(
                "Parse an image into a color-by-number map: palette, regions, centroids, borders, and key. "
                "Use when vision models fail or when a deterministic color/location map is needed."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Absolute path to the image to parse.",
                    },
                    "max_colors": {
                        "type": "integer",
                        "description": "Maximum palette colors. Default 48.",
                        "default": 48,
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Optional path to write the parsed JSON key.",
                    },
                },
                "required": ["image_path"],
            },
            category="vision",
            required_capabilities=["filesystem:read"],
        )

    def execute(self, **params: Any) -> ToolResult:
        image_path = params.get("image_path")
        if not image_path:
            return ToolResult(tool_name="vision_parse_color_map", content="image_path is required.", success=False)
        max_colors = int(params.get("max_colors", 48))
        output_path = params.get("output_path")

        try:
            result = process_image(image_path, max_colors=max_colors)
        except Exception as exc:
            return ToolResult(tool_name="vision_parse_color_map", content=f"Parse failed: {exc}", success=False)

        payload = {
            "image_path": image_path,
            "width": result.originalWidth,
            "height": result.originalHeight,
            "palette": [asdict(c) for c in result.palette],
            "regions": [
                {
                    "id": r.id,
                    "colorId": r.colorId,
                    "centroid": {"x": r.centroid[0], "y": r.centroid[1]},
                    "pixel_count": len(r.pixels),
                    "border_pixels": r.borderPixels[:50],
                }
                for r in result.regions
            ],
            "key": result.key,
        }

        if output_path:
            try:
                os.makedirs(os.path.dirname(output_path), exist_ok=True) if os.path.dirname(output_path) else None
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
            except Exception as exc:
                payload["write_error"] = str(exc)

        return ToolResult(
            tool_name="vision_parse_color_map",
            content=json.dumps(payload, ensure_ascii=False),
            success=True,
            metadata=payload,
        )


__all__ = ["process_image", "VisionParseColorMapTool"]
