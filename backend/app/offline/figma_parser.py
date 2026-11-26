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


_JUNK_FRAME_NAMES = {
    "demo",
    "home",
    "homepage",
    "trang chu",
    "desktop",
    "page",
    "hotline",
    "email",
    "mail",
    "diachi",
    "dia chi",
    "address",
    "phone",
    "sdt",
    "tab",
    "icon",
    "logo",
    "btn",
    "button",
    "search",
    "tim kiem",
    "social",
    "mxh",
}


def is_junk_section_name(name: str) -> bool:
    low = re.sub(r"\s+", " ", (name or "").strip().lower())
    if not low:
        return True
    if low in _JUNK_FRAME_NAMES:
        return True
    if re.fullmatch(
        r"(?:frame|group|rectangle|ellipse|vector|line|sp|item|card|box|img|image)\s*\d*",
        low,
    ):
        return True
    return False


def _collect_texts(node: dict[str, Any], out: list[dict[str, Any]], max_items: int = 80) -> None:
    if len(out) >= max_items or not isinstance(node, dict) or node.get("visible") is False:
        return
    if node.get("type") == "TEXT":
        chars = " ".join(str(node.get("characters") or "").split()).strip()
        if chars:
            bbox = node.get("absoluteBoundingBox") or {}
            style = node.get("style") or {}
            out.append(
                {
                    "text": chars,
                    "x": float(bbox.get("x") or 0),
                    "y": float(bbox.get("y") or 0),
                    "fontSize": float(style.get("fontSize") or 14),
                }
            )
    for child in node.get("children") or []:
        _collect_texts(child, out, max_items)


def _extract_heading_text(node: dict[str, Any]) -> str:
    texts: list[dict[str, Any]] = []
    _collect_texts(node, texts, max_items=40)
    candidates = [
        t
        for t in texts
        if 3 <= len(t["text"]) <= 55
        and t["fontSize"] >= 18
        and "@" not in t["text"]
        and not re.fullmatch(r"[\d\s.+()-]+", t["text"])
    ]
    if not candidates:
        return ""
    candidates.sort(key=lambda t: (-t["fontSize"], t["y"]))
    return candidates[0]["text"]


def extract_compact_tokens(figma_json: dict[str, Any]) -> dict[str, Any]:
    """
    Strip invisible/junk nodes and extract deduplicated colors, fonts,
    menu items, major homepage sections, and exportable image node IDs.
    """
    colors: dict[str, int] = {}
    typography: dict[tuple[str, float, int], dict[str, Any]] = {}
    raw_sections: list[dict[str, Any]] = []
    font_counts: dict[str, int] = {}
    container_widths: dict[int, int] = {}
    all_texts: list[str] = []
    menu_items: list[str] = []
    export_nodes: list[dict[str, Any]] = []
    image_dimensions: dict[str, dict[str, int]] = {}
    section_export_counts: dict[str, int] = {}
    seen_bg_sections: set[str] = set()
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

    def _canonical_section_slug(raw_sec_name: str) -> str:
        low = _slugify(re.sub(r"[_#]+", " ", raw_sec_name))
        if re.search(r"\b(qc|quangcao|quang-cao|banner)\b", low):
            return "quang-cao"
        if "slide" in low or low in {"hing", "hero"}:
            return "slideshow"
        if any(k in low for k in ("tieuchi", "tieu-chi", "taisao", "tai-sao", "visao", "vi-sao")):
            return "vi-sao" if "visao" in low or "vi-sao" in low else "tieu-chi"
        if any(k in low for k in ("thanhtuu", "thanh-tuu", "thongke", "thong-ke")):
            return "thanh-tuu"
        if any(k in low for k in ("noibat", "sanpham", "san-pham", "nhom-sp")):
            return "san-pham"
        if any(k in low for k in ("gioithieu", "gioi-thieu")):
            return "gioi-thieu"
        if any(k in low for k in ("ykien", "y-kien", "camnhan", "cam-nhan")):
            return "cam-nhan-khach-hang"
        if "tintuc" in low or "tin-tuc" in low:
            return "tin-tuc"
        if "footer" in low:
            return "footer"
        if "album" in low:
            return "album"
        return low

    def _is_vector_icon_container(n: dict[str, Any], nw: float | None, nh: float | None) -> bool:
        if nw is None or nh is None or not (18 <= nw <= 160 and 18 <= nh <= 160):
            return False
        kids = [k for k in (n.get("children") or []) if isinstance(k, dict) and k.get("visible") is not False]
        if not kids:
            return False
        # Exclude interactive buttons / text labels; icon containers hold vector/shape primitives only
        def _only_shapes(sub: dict[str, Any]) -> bool:
            st = str(sub.get("type", ""))
            if st == "TEXT":
                return False
            if st in {"VECTOR", "BOOLEAN_OPERATION", "ELLIPSE", "STAR", "REGULAR_POLYGON", "LINE"}:
                return True
            if st in {"GROUP", "FRAME", "RECTANGLE"}:
                if any(isinstance(p, dict) and p.get("type") == "IMAGE" and p.get("visible") is not False for p in (sub.get("fills") or [])):
                    return False
                sub_kids = [c for c in (sub.get("children") or []) if isinstance(c, dict) and c.get("visible") is not False]
                if st == "RECTANGLE" and not sub_kids:
                    return False
                return all(_only_shapes(c) for c in sub_kids) if sub_kids else False
            return False
        return all(_only_shapes(k) for k in kids)

    def _extract_sub_categories(sec_node: dict[str, Any]) -> list[str]:
        subs: list[str] = []
        for c in sec_node.get("children") or []:
            if not isinstance(c, dict) or c.get("visible") is False:
                continue
            cbb = c.get("absoluteBoundingBox") or {}
            cw = float(cbb.get("width") or 0)
            ch = float(cbb.get("height") or 0)
            if cw >= 650 and ch >= 200 and not any(k in str(c.get("name", "")).lower() for k in ("tile", "title")):
                ts: list[dict[str, Any]] = []
                _collect_texts(c, ts, max_items=10)
                ts.sort(key=lambda t: (t["y"], t["x"]))
                for t in ts:
                    lbl = t["text"].strip()
                    if 2 <= len(lbl) <= 40 and lbl.lower() not in {"xem tất cả", "xem chi tiết", "liên hệ ngay"}:
                        subs.append(lbl)
                        break
        return subs

    def walk(
        node: dict[str, Any],
        depth: int,
        parent_type: str = "",
        current_section: str = "",
        parent_is_page_root: bool = False,
        inside_banner_composite: bool = False,
    ) -> None:
        if not isinstance(node, dict):
            return
        stats["raw_node_count"] += 1
        if node.get("visible") is False:
            return

        bbox = node.get("absoluteBoundingBox") or {}
        width = bbox.get("width")
        height = bbox.get("height")
        x_pos = float(bbox.get("x") or 0)
        y_pos = float(bbox.get("y") or 0)
        node_type = str(node.get("type", ""))
        node_name = str(node.get("name", "")).strip()
        norm_name = node_name.lower()

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

        w_val = float(width) if width is not None else 1440.0
        h_val = float(height) if height is not None else 600.0
        is_whole_page_canvas = (
            node_type in {"FRAME", "COMPONENT", "SECTION", "GROUP"}
            and w_val >= 1000
            and h_val >= 1500
            and (depth == 0 or parent_type == "CANVAS")
        )
        if (
            not is_whole_page_canvas
            and node_type in {"FRAME", "GROUP", "COMPONENT"}
            and 1080 <= round(w_val) <= 1440
            and round(w_val) not in {1440}
            and current_section
        ):
            rw = round(w_val)
            container_widths[rw] = container_widths.get(rw, 0) + 1

        # Solid fills / strokes for colors + IMAGE fills for item photos / backgrounds
        for paint_list_key in ("fills", "strokes"):
            for paint in node.get(paint_list_key) or []:
                if not isinstance(paint, dict) or paint.get("visible") is False:
                    continue
                if paint.get("type") == "SOLID":
                    hex_code = _rgba_to_hex(paint.get("color", {}), paint.get("opacity"))
                    if hex_code:
                        colors[hex_code] = colors.get(hex_code, 0) + 1
                elif paint.get("type") == "IMAGE" and node.get("id"):
                    slug = _slugify(node_name or f"img-{node['id']}")
                    w_px = round(float(width or 0))
                    h_px = round(float(height or 0))
                    min_dim = min(w_px, h_px) if w_px > 0 and h_px > 0 else 0
                    max_dim = max(w_px, h_px)
                    is_whole_page_img = h_px >= 2000
                    is_extreme_strip = min_dim < 40 or (min_dim > 0 and (max_dim / min_dim) > 7.0)
                    is_named_photo = any(k in norm_name for k in ("logo", "favicon", "slide", "banner"))
                    sec_key = current_section or slug
                    is_bg_node = (
                        norm_name.startswith(("::before", "::after", "bg", "background"))
                        or (
                            w_px >= 1400
                            and not is_named_photo
                            and sec_key not in {"slide", "slideshow", "quang-cao", "quang-cao-2"}
                        )
                    )
                    if is_whole_page_img:
                        continue
                    if not inside_banner_composite:
                        if is_bg_node:
                            if sec_key not in seen_bg_sections:
                                seen_bg_sections.add(sec_key)
                                export_nodes.append(
                                    {
                                        "node_id": str(node["id"]),
                                        "name": slug,
                                        "kind": "image",
                                        "role": "section_bg",
                                        "section": sec_key,
                                        "image_ref": str(paint.get("imageRef") or ""),
                                        "width": w_px,
                                        "height": h_px,
                                    }
                                )
                        elif is_named_photo or not is_extreme_strip:
                            if is_named_photo or section_export_counts.get(sec_key, 0) < 6:
                                section_export_counts[sec_key] = section_export_counts.get(sec_key, 0) + 1
                                export_nodes.append(
                                    {
                                        "node_id": str(node["id"]),
                                        "name": slug,
                                        "kind": "image",
                                        "role": "item_photo",
                                        "section": sec_key,
                                        "image_ref": str(paint.get("imageRef") or ""),
                                        "width": w_px,
                                        "height": h_px,
                                    }
                                )
                    if not is_bg_node and w_px > 0 and h_px > 0:
                        if slug not in image_dimensions:
                            image_dimensions[slug] = {"width": w_px, "height": h_px}
                        if sec_key and sec_key not in image_dimensions and "logo" not in slug and min_dim >= 45:
                            image_dimensions[sec_key] = {"width": w_px, "height": h_px}

        # Extract typography from TEXT nodes
        if node_type == "TEXT":
            chars = " ".join(str(node.get("characters") or "").split()).strip()
            if chars and len(all_texts) < 150:
                all_texts.append(chars)
            style = node.get("style") or {}
            font_family = str(style.get("fontFamily") or "").strip()
            font_size = float(style.get("fontSize") or 16)
            font_weight = int(style.get("fontWeight") or 400)
            if font_family:
                font_counts[font_family] = font_counts.get(font_family, 0) + 1
                key = (font_family, round(font_size, 1), font_weight)
                if key not in typography:
                    typography[key] = {
                        "fontFamily": font_family,
                        "fontSize": round(font_size, 1),
                        "fontWeight": font_weight,
                        "lineHeightPx": round(float(style.get("lineHeightPx") or font_size * 1.4), 1),
                    }

        # Extract Menu items from navigation/menu containers
        if node_type in {"FRAME", "GROUP", "COMPONENT"} and any(
            k in norm_name for k in ("menu", "nav", "navigation")
        ):
            if width is None or float(width) >= 240:
                m_texts: list[dict[str, Any]] = []
                _collect_texts(node, m_texts, max_items=20)
                m_texts.sort(key=lambda t: t["x"])
                for t in m_texts:
                    label = t["text"]
                    if (
                        2 <= len(label) <= 32
                        and "@" not in label
                        and not re.fullmatch(r"[\d\s.+()-]+", label)
                        and label not in menu_items
                    ):
                        menu_items.append(label)

        # Collect major homepage sections strictly from direct children of Page Root (or CANVAS if no whole-page wrapper)
        canvas_has_page_wrapper = node_type == "CANVAS" and any(
            isinstance(c, dict)
            and c.get("visible") is not False
            and float((c.get("absoluteBoundingBox") or {}).get("height") or 0) >= 1500
            for c in (node.get("children") or [])
        )
        children_are_page_sections = is_whole_page_canvas or (node_type == "CANVAS" and not canvas_has_page_wrapper)

        next_section = current_section
        next_inside_composite = inside_banner_composite
        hero_child = None
        is_section_candidate = (
            parent_is_page_root
            and node_type in {"FRAME", "COMPONENT", "SECTION", "GROUP"}
            and not is_whole_page_canvas
            and w_val >= 500
            and h_val >= 70
        )

        if is_section_candidate:
            sec_title = node_name
            if is_junk_section_name(sec_title):
                sec_title = _extract_heading_text(node)
            if sec_title and not is_junk_section_name(sec_title):
                next_section = _canonical_section_slug(sec_title)
                sec_texts: list[dict[str, Any]] = []
                _collect_texts(node, sec_texts, max_items=80)
                unique_sec_texts = list(dict.fromkeys(t["text"] for t in sec_texts if t.get("text")))[:50]

                # Combined Header + Hero Slide group (e.g. leviet `header` 1920x900 containing `hing` 1920x700)
                hero_child = None
                if next_section == "header" and h_val >= 550:
                    for ch in node.get("children") or []:
                        if not isinstance(ch, dict) or ch.get("visible") is False:
                            continue
                        ch_bb = ch.get("absoluteBoundingBox") or {}
                        ch_w, ch_h = float(ch_bb.get("width") or 0), float(ch_bb.get("height") or 0)
                        ch_low = str(ch.get("name") or "").lower()
                        if ch_w >= 1200 and ch_h >= 400 and ("menu" not in ch_low and "nav" not in ch_low):
                            hero_child = ch
                            break

                if hero_child is not None:
                    hbb = hero_child.get("absoluteBoundingBox") or {}
                    hw, hh = round(float(hbb.get("width") or 1920)), round(float(hbb.get("height") or 700))
                    raw_sections.append(
                        {
                            "id": str(node.get("id", "")),
                            "name": "Header",
                            "width": round(w_val),
                            "height": max(70, round(h_val - hh)),
                            "x": round(x_pos),
                            "y": round(y_pos),
                            "layoutMode": node.get("layoutMode", "NONE"),
                            "texts": unique_sec_texts,
                        }
                    )
                    raw_sections.append(
                        {
                            "id": str(hero_child.get("id", "")),
                            "name": "Slide",
                            "width": hw,
                            "height": hh,
                            "x": round(float(hbb.get("x") or 0)),
                            "y": round(float(hbb.get("y") or y_pos)) + 1,
                            "layoutMode": hero_child.get("layoutMode", "NONE"),
                            "texts": [],
                        }
                    )
                else:
                    sub_cats = _extract_sub_categories(node) if next_section == "san-pham" and h_val >= 900 else []
                    raw_sections.append(
                        {
                            "id": str(node.get("id", "")),
                            "name": sec_title,
                            "width": round(w_val),
                            "height": round(h_val),
                            "x": round(x_pos),
                            "y": round(y_pos),
                            "layoutMode": node.get("layoutMode", "NONE"),
                            "texts": unique_sec_texts,
                            "sub_categories": sub_cats,
                        }
                    )

                if any(k in norm_name for k in ("slide", "qc", "quangcao", "quang cao", "quảng cáo")):
                    next_inside_composite = True

        # Vector icon groups inside sections (e.g. vi_sao 54x49, product category icon 45x40, customer/social icons)
        elif (
            node.get("id")
            and not inside_banner_composite
            and current_section
            and node_type in {"FRAME", "GROUP", "INSTANCE", "COMPONENT"}
            and _is_vector_icon_container(node, width, height)
        ):
            w_px, h_px = round(w_val), round(h_val)
            icon_key = f"icon:{current_section}"
            if section_export_counts.get(icon_key, 0) < 6:
                section_export_counts[icon_key] = section_export_counts.get(icon_key, 0) + 1
                export_nodes.append(
                    {
                        "node_id": str(node["id"]),
                        "name": _slugify(node_name or f"icon-{node['id']}"),
                        "kind": "vector",
                        "role": "item_icon",
                        "section": current_section,
                        "width": w_px,
                        "height": h_px,
                    }
                )
            if current_section not in image_dimensions:
                image_dimensions[current_section] = {"width": w_px, "height": h_px}

        # Explicit exportSettings on icons/vectors
        if node.get("exportSettings") and node.get("id") and not is_whole_page_canvas:
            slug = _slugify(node_name or f"asset-{node['id']}")
            w_px = round(float(width or 0))
            h_px = round(float(height or 0))
            if h_px < 2000:
                export_nodes.append(
                    {
                        "node_id": str(node["id"]),
                        "name": slug,
                        "kind": "vector" if node_type in {"VECTOR", "BOOLEAN_OPERATION"} else "image",
                        "role": "item_icon" if w_px <= 160 else "item_photo",
                        "section": next_section or slug,
                        "width": w_px,
                        "height": h_px,
                    }
                )
            if w_px > 0 and h_px > 0 and slug not in image_dimensions:
                image_dimensions[slug] = {"width": w_px, "height": h_px}

        for child in node.get("children") or []:
            child_sec = next_section
            if hero_child is not None and child is hero_child:
                child_sec = "slideshow"
            walk(
                child,
                depth + 1,
                node_type,
                child_sec,
                children_are_page_sections,
                next_inside_composite or (hero_child is not None and child is hero_child),
            )

    for root in collect_roots(figma_json):
        walk(root, 0, "", "", False, False)

    def _is_ad_sec(name_val: str) -> bool:
        low_s = re.sub(r"\s+", " ", (name_val or "").strip().lower())
        return bool(re.search(r"\b(?:qc|quangcao|quang cao|quảng cáo|banner)\b", low_s))

    raw_sections.sort(key=lambda s: (s.get("y", 0), s.get("x", 0), -s.get("width", 0)))

    # Merge side-by-side ad banners on the same horizontal row (e.g. QC 1 + QC 2 at same y)
    grouped_raw: list[dict[str, Any]] = []
    ad_group_counter = 0
    for sec in raw_sections:
        if _is_ad_sec(sec["name"]):
            if (
                grouped_raw
                and grouped_raw[-1].get("_is_ad")
                and abs(sec.get("y", 0) - grouped_raw[-1].get("y", 0)) <= 24
            ):
                prev = grouped_raw[-1]
                prev["child_ids"].append(sec["id"])
                prev["item_count"] += 1
                for txt in sec.get("texts") or []:
                    if txt not in prev["texts"]:
                        prev["texts"].append(txt)
                continue
            ad_group_counter += 1
            canonical_ad_name = "Quảng cáo" if ad_group_counter == 1 else f"Quảng cáo {ad_group_counter}"
            grouped_raw.append(
                {
                    **sec,
                    "name": canonical_ad_name,
                    "_is_ad": True,
                    "child_ids": [sec["id"]] if sec.get("id") else [],
                    "item_count": 1,
                }
            )
        else:
            grouped_raw.append({**sec, "_is_ad": False, "child_ids": [sec["id"]] if sec.get("id") else [], "item_count": 1})

    sections: list[dict[str, Any]] = []
    seen_sec_names: set[str] = set()
    for sec in grouped_raw:
        key = sec["name"].strip().lower()
        if key in seen_sec_names:
            continue
        seen_sec_names.add(key)
        sec_entry: dict[str, Any] = {
            "id": sec["id"],
            "name": sec["name"],
            "width": sec["width"],
            "height": sec["height"],
            "layoutMode": sec["layoutMode"],
            "texts": sec.get("texts", []),
            "item_count": sec.get("item_count", 1),
        }
        if sec.get("sub_categories"):
            sec_entry["sub_categories"] = sec["sub_categories"]
        if len(sec.get("child_ids") or []) > 1:
            sec_entry["child_node_ids"] = sec["child_ids"]
        sections.append(sec_entry)

        # Ensure composite WebP exports for Slide & Ad Banners (text baked into graphic)
        if sec.get("_is_ad") or "slide" in key:
            export_sec = "slideshow" if "slide" in key else _slugify(sec["name"])
            for idx_c, cid in enumerate(sec.get("child_ids") or [], start=1):
                if cid:
                    export_nodes.append(
                        {
                            "node_id": str(cid),
                            "name": f"{export_sec}-{idx_c}",
                            "kind": "image",
                            "role": "banner",
                            "section": export_sec,
                            "width": int(sec["width"]),
                            "height": int(sec["height"]),
                        }
                    )
        if len(sections) >= 16:
            break

    # Extract real contact info from Figma header/footer/all texts (joining split 2-line company names)
    combined_candidates: list[str] = []
    for s in sections:
        if any(k in s["name"].lower() for k in ("header", "footer", "lienhe", "liên hệ")):
            combined_candidates.extend(s.get("texts") or [])
    combined_candidates.extend(all_texts)

    contact_info: dict[str, str] = {}
    for idx_t, t in enumerate(combined_candidates):
        t_str = str(t or "").strip()
        if not t_str:
            continue
        if "email" not in contact_info:
            m_mail = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", t_str)
            if m_mail:
                contact_info["email"] = m_mail.group(0)
        if "hotline" not in contact_info:
            m_tel = re.search(r"(?:0|\+84)[\d\s.]{7,13}\d", t_str)
            if m_tel:
                contact_info["hotline"] = m_tel.group(0).strip()
        if "company_name" not in contact_info and any(
            k in t_str.upper() for k in ("CÔNG TY", "CTY ", "CƠ KHÍ", "DOANH NGHIỆP")
        ) and len(t_str) <= 120:
            full_name = t_str
            if idx_t + 1 < len(combined_candidates):
                nxt = str(combined_candidates[idx_t + 1] or "").strip()
                if nxt and nxt.isupper() and 3 <= len(nxt) <= 60 and "ĐỊA CHỈ" not in nxt and "HOTLINE" not in nxt:
                    full_name = f"{t_str} {nxt}".strip()
            contact_info["company_name"] = full_name
        if "address" not in contact_info and any(
            k in t_str.lower() for k in ("phường", "quận", "tỉnh", "tp.", "tp ", "thửa đất", "ấp ", "đường ", "địa chỉ", "lô ", "kcn")
        ) and len(t_str) >= 15:
            contact_info["address"] = re.sub(r"^(?:địa\s*chỉ\s*[:：]\s*)", "", t_str, flags=re.IGNORECASE).strip()

    sorted_colors = [
        {"hex": hex_code, "count": count}
        for hex_code, count in sorted(colors.items(), key=lambda x: -x[1])[:16]
    ]
    fonts_unique = (
        [f for f, _ in sorted(font_counts.items(), key=lambda x: (-x[1], x[0]))]
        if font_counts
        else sorted({t["fontFamily"] for t in typography.values()})
    )
    dedup_exports: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in export_nodes:
        if item["node_id"] not in seen_ids:
            seen_ids.add(item["node_id"])
            dedup_exports.append(item)

    raw_cnt = max(1, stats["raw_node_count"])
    kept_cnt = stats["kept_node_count"]
    saved_pct = max(0, min(95, round((1 - kept_cnt / raw_cnt) * 100)))

    detected_container_w = (
        max(container_widths.items(), key=lambda x: (x[1], x[0]))[0]
        if container_widths
        else 1200
    )
    return {
        "source": "figma_api",
        "file_name": figma_json.get("name", "Figma Design"),
        "colors": sorted_colors,
        "fonts": fonts_unique or ["Be Vietnam Pro"],
        "container_width": detected_container_w,
        "typography_scale": list(typography.values())[:16],
        "menu_items": menu_items[:12],
        "sections": sections,
        "export_nodes": dedup_exports[:60],
        "image_dimensions": image_dimensions,
        "contact_info": contact_info,
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
        "menu_items": ["Trang chủ", "Giới thiệu", "Sản phẩm", "Dịch vụ", "Tin tức", "Liên hệ"],
        "sections": [
            {"id": "10:101", "name": "Header Navigation", "width": 1440, "height": 80, "layoutMode": "HORIZONTAL"},
            {"id": "10:201", "name": "Hero Banner", "width": 1440, "height": 620, "layoutMode": "HORIZONTAL"},
            {"id": "10:301", "name": "San Pham Noi Bat", "width": 1440, "height": 680, "layoutMode": "VERTICAL"},
            {"id": "10:401", "name": "Ve Chung Toi & Uy Tin", "width": 1440, "height": 520, "layoutMode": "HORIZONTAL"},
            {"id": "10:501", "name": "Lien He & Footer", "width": 1440, "height": 420, "layoutMode": "VERTICAL"},
        ],
        "export_nodes": [
            {"node_id": "20:1", "name": "hero-banner", "kind": "image", "width": 1920, "height": 650},
            {"node_id": "20:2", "name": "product-1", "kind": "image", "width": 600, "height": 600},
            {"node_id": "20:3", "name": "product-2", "kind": "image", "width": 600, "height": 600},
            {"node_id": "20:4", "name": "product-3", "kind": "image", "width": 600, "height": 600},
            {"node_id": "20:5", "name": "about-showcase", "kind": "image", "width": 600, "height": 400},
        ],
        "image_dimensions": {
            "hero-banner": {"width": 1920, "height": 650},
            "product-1": {"width": 600, "height": 600},
            "about-showcase": {"width": 600, "height": 400},
        },
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
