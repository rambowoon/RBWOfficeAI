from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx


def parse_figma_url(url: str) -> tuple[str | None, str | None]:
    """Extract (file_key, node_id) from a Figma file/design URL."""
    if not url or not url.strip():
        return None, None
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    match = re.search(r"/(?:file|design|proto)/([A-Za-z0-9]+)", parsed.path)
    file_key = match.group(1) if match else None
    qs = parse_qs(parsed.query)
    node_id = None
    if "node-id" in qs and qs["node-id"]:
        node_id = qs["node-id"][0].replace("-", ":")
    return file_key, node_id


def _rgba_to_hex(color: dict[str, Any], opacity: float | None = None) -> str | None:
    if not isinstance(color, dict):
        return None
    r = max(0, min(255, round(float(color.get("r", 0)) * 255)))
    g = max(0, min(255, round(float(color.get("g", 0)) * 255)))
    b = max(0, min(255, round(float(color.get("b", 0)) * 255)))
    a = float(color.get("a", 1.0))
    if opacity is not None:
        a = a * float(opacity)
    if a <= 0.01:
        return None
    return f"#{r:02x}{g:02x}{b:02x}"


def _slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "asset"


def extract_compact_tokens(figma_json: dict[str, Any]) -> dict[str, Any]:
    """
    Strip invisible/junk nodes and extract deduplicated colors, fonts,
    sections, and exportable image node IDs from a raw Figma REST payload.
    """
    colors: dict[str, int] = {}
    typography: dict[tuple[str, float, int], dict[str, Any]] = {}
    sections: list[dict[str, Any]] = []
    export_nodes: list[dict[str, str]] = []
    stats = {"raw_node_count": 0, "kept_node_count": 0}

    def collect_roots(payload: dict[str, Any]) -> list[dict[str, Any]]:
        if "document" in payload and isinstance(payload["document"], dict):
            return [payload["document"]]
        if "nodes" in payload and isinstance(payload["nodes"], dict):
            roots = []
            for entry in payload["nodes"].values():
                if isinstance(entry, dict) and isinstance(entry.get("document"), dict):
                    roots.append(entry["document"])
            return roots
        return [payload]

    def walk(node: dict[str, Any], depth: int, parent_type: str = "") -> None:
        if not isinstance(node, dict):
            return
        stats["raw_node_count"] += 1
        if node.get("visible") is False:
            return

        bbox = node.get("absoluteBoundingBox") or {}
        width = bbox.get("width")
        height = bbox.get("height")
        node_type = str(node.get("type", ""))
        node_name = str(node.get("name", "")).strip()

        # Skip degenerate empty shapes that carry no text, children, or image fills
        if (
            node_type not in {"DOCUMENT", "CANVAS"}
            and width is not None
            and height is not None
            and (width <= 0 or height <= 0)
            and not node.get("children")
            and not node.get("characters")
        ):
            return

        stats["kept_node_count"] += 1

        # Extract solid fills & strokes
        for paint_list_key in ("fills", "strokes"):
            for paint in node.get(paint_list_key) or []:
                if not isinstance(paint, dict) or paint.get("visible") is False:
                    continue
                if paint.get("type") == "SOLID":
                    hex_code = _rgba_to_hex(paint.get("color", {}), paint.get("opacity"))
                    if hex_code:
                        colors[hex_code] = colors.get(hex_code, 0) + 1
                elif paint.get("type") == "IMAGE" and node.get("id"):
                    export_nodes.append(
                        {
                            "node_id": str(node["id"]),
                            "name": _slugify(node_name or f"img-{node['id']}"),
                            "kind": "image",
                        }
                    )

        # Extract typography from TEXT nodes
        if node_type == "TEXT":
            style = node.get("style") or {}
            font_family = str(style.get("fontFamily") or "").strip()
            font_size = float(style.get("fontSize") or 16)
            font_weight = int(style.get("fontWeight") or 400)
            if font_family:
                key = (font_family, round(font_size, 1), font_weight)
                if key not in typography:
                    typography[key] = {
                        "fontFamily": font_family,
                        "fontSize": round(font_size, 1),
                        "fontWeight": font_weight,
                        "lineHeightPx": round(float(style.get("lineHeightPx") or font_size * 1.4), 1),
                    }

        # Collect top-level sections
        if node_type in {"FRAME", "COMPONENT", "SECTION"} and (
            parent_type in {"CANVAS", "SECTION", ""} or depth in {1, 2}
        ):
            if len(sections) < 20:
                sections.append(
                    {
                        "id": str(node.get("id", "")),
                        "name": node_name or f"Section {len(sections) + 1}",
                        "width": round(float(width or 1440)),
                        "height": round(float(height or 600)),
                        "layoutMode": node.get("layoutMode", "NONE"),
                    }
                )

        # Explicit exportSettings on icons/vectors
        if node.get("exportSettings") and node.get("id"):
            export_nodes.append(
                {
                    "node_id": str(node["id"]),
                    "name": _slugify(node_name or f"asset-{node['id']}"),
                    "kind": "vector" if node_type in {"VECTOR", "BOOLEAN_OPERATION"} else "image",
                }
            )

        for child in node.get("children") or []:
            walk(child, depth + 1, node_type)

    for root in collect_roots(figma_json):
        walk(root, 0, "")

    sorted_colors = [
        {"hex": hex_code, "count": count}
        for hex_code, count in sorted(colors.items(), key=lambda x: -x[1])[:16]
    ]
    fonts_unique = sorted({t["fontFamily"] for t in typography.values()})
    dedup_exports: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for item in export_nodes:
        if item["node_id"] not in seen_ids:
            seen_ids.add(item["node_id"])
            dedup_exports.append(item)

    raw_cnt = max(1, stats["raw_node_count"])
    kept_cnt = stats["kept_node_count"]
    saved_pct = max(0, min(95, round((1 - kept_cnt / raw_cnt) * 100)))

    return {
        "source": "figma_api",
        "file_name": figma_json.get("name", "Figma Design"),
        "colors": sorted_colors,
        "fonts": fonts_unique or ["Be Vietnam Pro"],
        "typography_scale": list(typography.values())[:16],
        "sections": sections,
        "export_nodes": dedup_exports[:16],
        "stats": {
            "raw_node_count": stats["raw_node_count"],
            "kept_node_count": stats["kept_node_count"],
            "compression_pct": saved_pct,
        },
    }


def build_offline_demo_tokens(figma_url: str, spec_text: str) -> dict[str, Any]:
    """Generate a realistic compact tokens package for offline/demo runs (0 LLM tokens)."""
    file_key, node_id = parse_figma_url(figma_url)
    lower_spec = spec_text.lower()

    primary = "#0f766e"
    accent = "#f59e0b"
    if any(k in lower_spec for k in ("công nghệ", "ai", "tech", "saas", "phần mềm")):
        primary = "#2563eb"
        accent = "#06b6d4"
    elif any(k in lower_spec for k in ("nội thất", "bất động sản", "kiến trúc", "nasanic")):
        primary = "#1d4ed8"
        accent = "#d97706"
    elif any(k in lower_spec for k in ("spa", "làm đẹp", "mỹ phẩm", "y tế")):
        primary = "#0d9488"
        accent = "#fb7185"

    return {
        "source": "demo_offline_parser",
        "file_key": file_key or "DEMO_FIGMA_KEY",
        "node_id": node_id or "0:1",
        "file_name": "Landing & Showcase Design System",
        "colors": [
            {"hex": primary, "count": 42, "role": "primary"},
            {"hex": accent, "count": 19, "role": "accent"},
            {"hex": "#0f172a", "count": 35, "role": "ink"},
            {"hex": "#475569", "count": 28, "role": "muted"},
            {"hex": "#f8fafc", "count": 24, "role": "surface"},
            {"hex": "#ffffff", "count": 51, "role": "background"},
        ],
        "fonts": ["Be Vietnam Pro", "Plus Jakarta Sans"],
        "typography_scale": [
            {"fontFamily": "Plus Jakarta Sans", "fontSize": 44.0, "fontWeight": 800, "lineHeightPx": 54.0},
            {"fontFamily": "Plus Jakarta Sans", "fontSize": 30.0, "fontWeight": 700, "lineHeightPx": 38.0},
            {"fontFamily": "Be Vietnam Pro", "fontSize": 18.0, "fontWeight": 600, "lineHeightPx": 26.0},
            {"fontFamily": "Be Vietnam Pro", "fontSize": 15.0, "fontWeight": 400, "lineHeightPx": 24.0},
        ],
        "sections": [
            {"id": "10:101", "name": "Header Navigation", "width": 1440, "height": 80, "layoutMode": "HORIZONTAL"},
            {"id": "10:201", "name": "Hero Banner", "width": 1440, "height": 620, "layoutMode": "HORIZONTAL"},
            {"id": "10:301", "name": "San Pham Noi Bat", "width": 1440, "height": 680, "layoutMode": "VERTICAL"},
            {"id": "10:401", "name": "Ve Chung Toi & Uy Tin", "width": 1440, "height": 520, "layoutMode": "HORIZONTAL"},
            {"id": "10:501", "name": "Lien He & Footer", "width": 1440, "height": 420, "layoutMode": "VERTICAL"},
        ],
        "export_nodes": [
            {"node_id": "20:1", "name": "hero-banner", "kind": "image"},
            {"node_id": "20:2", "name": "product-1", "kind": "image"},
            {"node_id": "20:3", "name": "product-2", "kind": "image"},
            {"node_id": "20:4", "name": "product-3", "kind": "image"},
            {"node_id": "20:5", "name": "about-showcase", "kind": "image"},
        ],
        "stats": {
            "raw_node_count": 480,
            "kept_node_count": 112,
            "compression_pct": 77,
        },
    }


async def fetch_figma_tokens(
    figma_url: str,
    figma_token: str | None,
    mode: str,
    spec_text: str = "",
) -> dict[str, Any]:
    """
    Fetch Figma design tokens via REST API when a token + valid URL are supplied,
    or fall back cleanly to deterministic offline tokens in Demo mode.
    """
    file_key, node_id = parse_figma_url(figma_url)
    if figma_token and figma_token.strip() and file_key:
        headers = {"X-Figma-Token": figma_token.strip()}
        endpoint = (
            f"https://api.figma.com/v1/files/{file_key}/nodes?ids={node_id}"
            if node_id
            else f"https://api.figma.com/v1/files/{file_key}?depth=5"
        )
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(endpoint, headers=headers)
                resp.raise_for_status()
                raw_json = resp.json()
            tokens = extract_compact_tokens(raw_json)
            tokens["file_key"] = file_key
            tokens["node_id"] = node_id
            return tokens
        except Exception as exc:
            if mode == "live_sdk":
                fallback = build_offline_demo_tokens(figma_url, spec_text)
                fallback["api_warning"] = f"Figma REST API fallback ({exc})"
                return fallback

    return build_offline_demo_tokens(figma_url, spec_text)
