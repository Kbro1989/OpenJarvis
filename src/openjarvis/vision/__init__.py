"""OpenJarvis vision bridge — color-by-number parts detection + Gemini understanding.

Ported from ChromaNumber `services/imageProcessor.ts` and `services/geminiService.ts`,
wired into OpenJarvis `/blueprint` as optional image ingestion.
"""

from __future__ import annotations

import base64
import json
import math
import os
from typing import Any, Dict, List, Optional, Tuple


class ColorSegmenter:
    """K-Means + connected-components parts detector.

    Input: raw RGB bytes, width, height
    Output: palette + regions with centroids and border pixels
    """

    def __init__(self, max_colors: int = 48) -> None:
        self.max_colors = max_colors

    def segment(self, data: bytes, width: int, height: int) -> Dict[str, Any]:
        if not data or len(data) != width * height * 4:
            raise ValueError("image data must be RGBA bytes with length == width*height*4")

        pixel_count = width * height
        centroids = self._smart_init(data, pixel_count)
        assignments = self._assign(data, pixel_count, centroids)

        # Merge small regions by color similarity
        regions, palette, region_map = self._build_regions(assignments, data, width, height, pixel_count, centroids)

        return {
            "width": width,
            "height": height,
            "pixel_count": pixel_count,
            "palette": palette,
            "regions": regions,
            "region_map": region_map,
        }

    @staticmethod
    def _smart_init(data: bytes, pixel_count: int) -> List[Tuple[int, int, int]]:
        centroids: List[Tuple[int, int, int]] = []
        r_idx = 0
        centroids.append((data[r_idx], data[r_idx + 1], data[r_idx + 2]))
        for _ in range(1, min(48, max(pixel_count, 1))):
            r_idx = (r_idx * 131 + 37) % max(1, len(data) - 2)
            centroids.append((data[r_idx], data[r_idx + 1], data[r_idx + 2]))
        return centroids

    @staticmethod
    def _assign(data: bytes, pixel_count: int, centroids: List[Tuple[int, int, int]]) -> List[int]:
        max_colors = len(centroids)
        assignments = [0] * pixel_count
        for i in range(pixel_count):
            r, g, b = data[i * 4], data[i * 4 + 1], data[i * 4 + 2]
            min_dist = math.inf
            best = 0
            for c in range(max_colors):
                cr, cg, cb = centroids[c]
                d = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
                if d < min_dist:
                    min_dist = d
                    best = c
            assignments[i] = best
        return assignments

    @staticmethod
    def _build_regions(
        assignments: List[int],
        data: bytes,
        width: int,
        height: int,
        pixel_count: int,
        raw_centroids: List[Tuple[int, int, int]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[int]]:
        uniques = sorted(set(assignments))
        palette = [
            {
                "id": idx + 1,
                "rgb": raw_centroids[old],
                "hex": "#{:02x}{:02x}{:02x}".format(*raw_centroids[old]),
            }
            for idx, old in enumerate(uniques)
        ]
        remap = {old: idx for idx, old in enumerate(uniques)}
        remapped = [remap[a] for a in assignments]

        region_map = [-1] * pixel_count
        regions: List[Dict[str, Any]] = []
        visited = [False] * pixel_count
        stack = []

        for i in range(pixel_count):
            if visited[i]:
                continue
            color_idx = remapped[i]
            region_pixels = []
            stack.append(i)
            visited[i] = True
            while stack:
                p = stack.pop()
                region_map[p] = len(regions)
                region_pixels.append(p)
                px = p % width
                for n in (p - width, p + width, px - 1 if px > 0 else -1, px + 1 if px < width - 1 else -1):
                    if 0 <= n < pixel_count and not visited[n] and remapped[n] == color_idx:
                        visited[n] = True
                        stack.append(n)

            regions.append({"colorId": color_idx, "pixels": region_pixels, "borderPixels": [], "centroid": {"x": 0, "y": 0}})

        # Merge small regions without expanding palette
        min_size = max(20, pixel_count // 40000)
        region_map = [-1] * pixel_count
        by_id: Dict[int, Dict[str, Any]] = {i: r for i, r in enumerate(regions)}
        active = set(by_id)
        sorted_ids = sorted(active, key=lambda i: len(by_id[i]["pixels"]))
        for r_id in sorted_ids:
            region = by_id[r_id]
            if len(region["pixels"]) >= min_size:
                continue
            neighbors = []
            for p in region["pixels"]:
                px = p % width
                for n in (p - width, p + width, px - 1 if px > 0 else -1, px + 1 if px < width - 1 else -1):
                    if 0 <= n < pixel_count and region_map[n] != r_id and region_map[n] in active:
                        neighbors.append(region_map[n])
            if not neighbors:
                continue
            target_id = max(set(neighbors), key=neighbors.count)
            target = by_id[target_id]
            for p in region["pixels"]:
                region_map[p] = target_id
                target["pixels"].append(p)
            active.discard(r_id)

        final = []
        for new_id, old_id in enumerate(sorted(active, key=lambda i: len(by_id[i]["pixels"]))):
            region = by_id[old_id]
            sum_x = sum(p % width for p in region["pixels"])
            sum_y = sum(p // width for p in region["pixels"])
            cx = round(sum_x / len(region["pixels"]))
            cy = round(sum_y / len(region["pixels"]))
            borders = []
            for p in region["pixels"]:
                px = p % width
                is_border = False
                for n in (p - width, p + width, px - 1 if px > 0 else -1, px + 1 if px < width - 1 else -1):
                    if n < 0 or n >= pixel_count or region_map[n] != new_id:
                        is_border = True
                        break
                if is_border:
                    borders.append(p)
            final.append(
                {
                    "id": new_id,
                    "colorId": region["colorId"],
                    "pixelCount": len(region["pixels"]),
                    "centroid": {"x": cx, "y": cy},
                    "borderPixels": borders,
                }
            )

        for idx, region in enumerate(final):
            for p in region.get("pixels", []):
                region_map[p] = idx

        return final, palette, region_map


class GeminiVision:
    """Gemini-based image understanding for detected parts."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.model = os.environ.get("GEMINI_FLASH_MODEL", "gemini-1.5-flash-latest")
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

    def describe_regions(self, base64_image: str, regions: List[Dict[str, Any]], prompt: str = "") -> List[Dict[str, Any]]:
        if not self.api_key:
            return [{"region_id": r["id"], "label": f"part_{r['id']}", "confidence": 0.0, "backend": "none"} for r in regions]

        text = prompt or "Identify the object or part shown in each numbered color region. Return JSON array only."
        payload = json.dumps(
            {
                "contents": [
                    {
                        "parts": [
                            {"text": text},
                            {
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": base64_image,
                                }
                            },
                        ]
                    }
                ],
                "generationConfig": {"temperature": 0.2, "topP": 0.4, "maxOutputTokens": 2048},
            }
        ).encode()
        req = urllib.request.Request(
            self.endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = json.loads(r.read())
            text_out = body.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            try:
                parsed = json.loads(text_out)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
            return [{"region_id": r["id"], "label": text_out or f"part_{r['id']}", "confidence": 0.5, "backend": "gemini"} for r in regions]
        except Exception as exc:
            return [{"region_id": r["id"], "label": f"part_{r['id']}", "confidence": 0.0, "backend": "error", "error": str(exc)} for r in regions]


class BlueprintEyes:
    """Bridge regions + labels into `/blueprint` scene facts."""

    def __init__(self, api_key: Optional[str] = None, max_regions: int = 12) -> None:
        self.segmenter = ColorSegmenter(max_colors=64)
        self.vision = GeminiVision(api_key)
        self.max_regions = max_regions

    def parse(self, raw_image: bytes, width: int, height: int, base64_image: str) -> Dict[str, Any]:
        segmentation = self.segmenter.segment(raw_image, width, height)
        regions = segmentation["regions"][: self.max_regions]
        descriptions = self.vision.describe_regions(base64_image, regions)
        labeled = []
        for region, desc in zip(regions, descriptions):
            labeled.append(
                {
                    "region_id": region["id"],
                    "color_id": region["colorId"],
                    "palette_hex": segmentation["palette"][region["colorId"]]["hex"],
                    "pixel_count": region["pixelCount"],
                    "centroid": region["centroid"],
                    "label": desc.get("label", f"part_{region['id']}"),
                    "confidence": desc.get("confidence", 0.0),
                    "backend": desc.get("backend", "unknown"),
                }
            )
        return {
            "width": width,
            "height": height,
            "palette": segmentation["palette"],
            "labeled_regions": labeled,
            "scene_facts": {
                "visual_prompts": [item["label"] for item in labeled[:3]],
                "dominant_palette_hex": segmentation["palette"][0]["hex"] if segmentation["palette"] else "#000000",
                "part_count": len(labeled),
            },
        }
