from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any


def _slugify_vi(text: str) -> str:
    text = (text or "").replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    slug = re.sub(r"[^a-z0-9]+", "-", stripped.lower()).strip("-")
    return slug or "muc"


def _strip_prefix(name: str) -> str:
    cleaned = re.sub(r"^(?:Menu|Mục|Phần|Khối)\s*:\s*", "", (name or "").strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:Mục|Phần|Khối)\s+", "", cleaned, flags=re.IGNORECASE)
    # Strip trailing "(...)" if reconciled name like "San Pham Noi Bat (Sản phẩm)"
    m = re.match(r"^(.+?)\s*\(([^)]+)\)$", cleaned)
    if m:
        # Prefer the Vietnamese spec part inside parentheses if it looks cleaner
        inner = m.group(2).strip()
        if len(inner) >= 2:
            return inner
    return cleaned.strip()


def _scale_dimensions(
    w: int,
    h: int,
    *,
    min_width: int,
    scale_above: float = 1.0,
) -> tuple[int, int]:
    """Enforce minimum width (preserving aspect ratio) and optional scale factor when above min_width."""
    if w <= 0 or h <= 0:
        return min_width, min_width
    if w < min_width:
        return min_width, max(40, round(h * (min_width / w)))
    if w > min_width and scale_above != 1.0:
        return round(w * scale_above), max(40, round(h * scale_above))
    return w, h


def _resolve_dimensions(
    slug: str,
    raw_name: str,
    tokens_data: dict[str, Any],
    assets_manifest: dict[str, Any],
    default_w: int,
    default_h: int,
    figma_section_name: str = "",
    *,
    prefer_icon: bool = False,
) -> tuple[int, int]:
    """Match a section/type slug against Figma image_dimensions, export_nodes, or sections."""
    figma_slug = _slugify_vi(figma_section_name) if figma_section_name else ""
    if prefer_icon:
        for node in tokens_data.get("export_nodes") or []:
            if not isinstance(node, dict) or node.get("role") != "item_icon":
                continue
            nsec = _slugify_vi(str(node.get("section") or ""))
            nw, nh = int(node.get("width") or 0), int(node.get("height") or 0)
            if nw >= 16 and nh >= 16 and nsec and (
                nsec == slug or nsec == figma_slug or nsec in slug or slug in nsec
            ):
                return nw, nh

    dims_map: dict[str, dict[str, int]] = {}
    for k, v in (assets_manifest.get("dimensions") or {}).items():
        if isinstance(v, dict) and v.get("width") and v.get("height"):
            ks = _slugify_vi(k)
            if not ks.startswith("bg-"):
                dims_map[ks] = {"width": int(v["width"]), "height": int(v["height"])}
    for k, v in (tokens_data.get("image_dimensions") or {}).items():
        if isinstance(v, dict) and v.get("width") and v.get("height"):
            dims_map.setdefault(_slugify_vi(k), {"width": int(v["width"]), "height": int(v["height"])})
    for node in tokens_data.get("export_nodes") or []:
        if node.get("role") == "section_bg":
            continue
        if node.get("width") and node.get("height"):
            dims_map.setdefault(
                _slugify_vi(str(node.get("name") or "")),
                {"width": int(node["width"]), "height": int(node["height"])},
            )

    slug_tokens = {t for t in slug.split("-") if len(t) >= 2}
    if figma_slug:
        slug_tokens |= {t for t in figma_slug.split("-") if len(t) >= 2}
    for candidate in (slug, figma_slug):
        if candidate and candidate in dims_map:
            d = dims_map[candidate]
            return max(40, d["width"]), max(40, d["height"])

    # Fuzzy token match on Figma image names
    for img_slug, d in dims_map.items():
        img_tokens = {t for t in img_slug.split("-") if len(t) >= 2}
        if slug_tokens & img_tokens:
            return max(40, d["width"]), max(40, d["height"])

    # Fallback: check matching Figma section height (bounded reasonably for web cards)
    name_norm = _slugify_vi(raw_name)
    for sec in tokens_data.get("sections") or []:
        sec_slug = _slugify_vi(str(sec.get("name") or ""))
        if sec_slug == slug or sec_slug == name_norm or (slug_tokens & set(sec_slug.split("-"))):
            sw = int(sec.get("width") or 0)
            sh = int(sec.get("height") or 0)
            if 80 <= sw <= 1920 and 80 <= sh <= 1200:
                if slug in {"slideshow", "slide", "hero", "hero-banner"}:
                    return sw, sh

    return default_w, default_h


def _php_literal(value: Any, indent: int = 0) -> str:
    pad = "    " * indent
    next_pad = "    " * (indent + 1)
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"
    if isinstance(value, list):
        if not value:
            return "[]"
        items = ",\n".join(f"{next_pad}{_php_literal(v, indent + 1)}" for v in value)
        return f"[\n{items},\n{pad}]"
    if isinstance(value, dict):
        if not value:
            return "[]"
        rows = ",\n".join(
            f"{next_pad}{_php_literal(str(k))} => {_php_literal(v, indent + 1)}"
            for k, v in value.items()
        )
        return f"[\n{rows},\n{pad}]"
    return _php_literal(str(value))


def _render_php_return(data: dict[str, Any]) -> str:
    return (
        "<?php\n\n"
        "/******************************************************************************\n"
        " * NASANI VIỆT NAM — Auto-configured by RBWOfficeAI from Figma & Spec\n"
        " */\n\n"
        f"return {_php_literal(data, 0)};\n"
    )


def _build_categories_block(
    levels: int,
    w: int,
    h: int,
    *,
    include_list_icon: bool = False,
) -> dict[str, Any]:
    cat_keys = [
        ("list", "danhmuccap1"),
        ("cat", "danhmuccap2"),
        ("item", "danhmuccap3"),
    ]
    out: dict[str, Any] = {}
    for idx in range(min(3, max(0, levels))):
        key, label = cat_keys[idx]
        images_blk: dict[str, Any] = {
            "photo": {
                "title": "anhdaidien",
                "width": w,
                "height": h,
                "thumb": f"{w}x{h}x1",
            }
        }
        if idx == 0 and include_list_icon:
            images_blk["icon"] = {
                "title": "Icon",
                "width": 49,
                "height": 43,
                "thumb": "49x43x2",
            }
        out[key] = {
            "title_main_categories": label,
            "images": images_blk,
            "show_images_categories": True,
            "slug_categories": True,
            "status_categories": (
                {"is_featured": "noibat", "is_show": "hienthi"} if idx == 0 else {"is_show": "hienthi"}
            ),
            "name_categories": True,
            "desc_categories": False,
            "content_categories": True,
            "content_categories_cke": True,
            "seo_categories": True,
        }
    return out


def _detect_options2(slug: str, title: str, reqs: str, notes: str) -> dict[str, Any]:
    """Detect Nasanic `options2` custom fields (video_mp4, link-youtube, statistical, address) from spec."""
    combined = f"{slug} {_slugify_vi(title)} {_slugify_vi(reqs)} {_slugify_vi(notes)}"
    opts: dict[str, Any] = {}
    if "mp4" in combined or "dang-video" in combined or ("video" in combined and "vong-lap" in combined):
        opts["video_mp4"] = {"title": "Video mp4", "type": "mp4"}
    if "youtube" in combined or ("video" in slug and "link" in combined):
        opts["link-youtube"] = {"type": "text", "title": "Link youtube", "lang": "true"}
    if any(k in combined for k in ("so-lieu", "con-so", "thong-ke", "statistical")):
        opts["statistical"] = {"type": "text", "title": "Số liệu"}
    if any(k in slug for k in ("cam-nhan", "y-kien", "khach-hang")) and ("dia-chi" in combined or "cam-nhan" in slug):
        opts["address"] = {"type": "text", "title": "Địa chỉ"}
    return opts


def configure_nasanic_types(
    config_dir: Path,
    spec_sections: list[Any],
    tokens_data: dict[str, Any],
    assets_manifest: dict[str, Any],
    global_features: list[str],
) -> dict[str, Any]:
    """
    Generate/update Nasanic v8.5 `config/type-*.php` files directly from approved
    `spec_sections` and Figma image dimensions (`width`, `height`, `thumb`).
    """
    config_dir.mkdir(parents=True, exist_ok=True)

    header_reqs = ""
    merged_entries: dict[str, dict[str, Any]] = {}
    for raw in spec_sections:
        sec = raw.model_dump(mode="json") if hasattr(raw, "model_dump") else dict(raw)
        clean_name = _strip_prefix(str(sec.get("name") or ""))
        if not clean_name:
            continue
        slug = _slugify_vi(clean_name)
        ctype = str(sec.get("content_type") or "layout")
        slug = re.sub(r"^(?:muc|phan|khoi)-", "", slug)
        if slug.startswith("vi-sao") and len(slug) > 22:
            slug = "vi-sao"
            clean_name = "Vì sao chọn chúng tôi"
        elif slug.startswith("tai-sao") and len(slug) > 22:
            slug = "tai-sao"
            clean_name = "Tại sao chọn chúng tôi"
        elif slug.startswith("tieu-chi") and len(slug) > 16:
            slug = "tieu-chi"
            clean_name = "Tiêu chí"
        elif ctype == "video" and slug != "video-clip":
            slug = "video"
            clean_name = "Video"
        elif slug in {"goc-nhin-tu-khach-hang", "cam-nhan-tu-khach-hang", "y-kien-tu-khach-hang"}:
            slug = "cam-nhan-khach-hang"
            clean_name = "Cảm nhận khách hàng"
        if slug in {"san-pham-noi-bat", "menu"} and any(
            _slugify_vi(_strip_prefix(str((r.model_dump() if hasattr(r, "model_dump") else r).get("name") or ""))) == "san-pham"
            for r in spec_sections
        ):
            slug = "san-pham"
        if slug == "header":
            header_reqs = f"{sec.get('spec_requirements') or ''} {sec.get('notes') or ''}".lower()
            continue

        scope_val = str(sec.get("scope") or "").lower()
        cat_lvl = int(sec.get("category_levels") or 0)
        notes = str(sec.get("notes") or "")
        reqs = str(sec.get("spec_requirements") or "")
        figma_sec_name = str(sec.get("figma_section_name") or "")

        # Keep multiple distinct ad/banner blocks (e.g. Quảng cáo 1, Quảng cáo 2) separate
        if slug in merged_entries and slug in {"quang-cao", "banner"}:
            existing_fsn = merged_entries[slug].get("figma_section_name", "")
            if figma_sec_name != existing_fsn or not existing_fsn:
                suffix_idx = 2
                while f"{slug}-{suffix_idx}" in merged_entries:
                    suffix_idx += 1
                slug = f"{slug}-{suffix_idx}"
                clean_name = f"{clean_name} {suffix_idx}"

        existing = merged_entries.get(slug)
        is_homepage = scope_val != "menu"
        if existing:
            existing["category_levels"] = max(existing["category_levels"], cat_lvl)
            existing["in_menu"] = existing["in_menu"] or (scope_val == "menu")
            existing["homepage"] = existing["homepage"] or is_homepage
            existing["notes"] = f"{existing['notes']} {notes}".strip()
            existing["spec_requirements"] = f"{existing['spec_requirements']} {reqs}".strip()
            if existing["content_type"] in {"layout", "feature"} and ctype not in {"layout", "feature"}:
                existing["content_type"] = ctype
        else:
            merged_entries[slug] = {
                "slug": slug,
                "title": clean_name,
                "content_type": ctype,
                "in_menu": scope_val == "menu",
                "homepage": is_homepage,
                "category_levels": cat_lvl,
                "notes": notes,
                "spec_requirements": reqs,
                "figma_section_name": figma_sec_name,
            }

    all_notes_lower = " ".join(
        [*(e["notes"].lower() for e in merged_entries.values()), *(g.lower() for g in global_features)]
    )
    enable_watermark = "đóng dấu" in all_notes_lower or "watermark" in all_notes_lower

    products_cfg: dict[str, Any] = {}
    news_cfg: dict[str, Any] = {}
    static_cfg: dict[str, Any] = {}
    photo_cfg: dict[str, Any] = {}
    newsletters_cfg: dict[str, Any] = {}
    summary_items: list[dict[str, Any]] = []

    for slug, entry in merged_entries.items():
        ctype = entry["content_type"]
        title = entry["title"]
        cat_lvl = entry["category_levels"]
        notes_low = entry["notes"].lower()
        hide_price = "không hiện giá" in notes_low
        options2 = _detect_options2(slug, title, entry["spec_requirements"], entry["notes"])

        if ctype == "product":
            w, h = _resolve_dimensions(
                slug,
                title,
                tokens_data,
                assets_manifest,
                800,
                800,
                figma_section_name=entry.get("figma_section_name", ""),
            )
            w, h = _scale_dimensions(w, h, min_width=800)
            cfg: dict[str, Any] = {
                "title_main": title,
                "website": {
                    "type": {"index": "object", "detail": "article"},
                    "title": title,
                    "amp": False,
                    "route": {
                        "controller": "ProductController@index",
                        "name": "product" if slug == "san-pham" else slug,
                        "method": "get",
                        "slugs": {"vi": slug, "en": "product" if slug == "san-pham" else slug},
                    },
                },
                "copy": True,
                "tags": False,
                "slug": True,
                "view": True,
                "code": True,
                "regular_price": not hide_price,
                "sale_price": not hide_price,
                "discount": not hide_price,
                "datePublish": True,
                "name": True,
                "desc": True,
                "desc_cke": True,
                "content": True,
                "content_cke": True,
                "schema": True,
                "seo": True,
                "status": {"is_featured": "noibat", "is_show": "hienthi"},
                "images": {
                    "photo": {
                        "title": "anhdaidien",
                        "width": w,
                        "height": h,
                        "thumb": f"{w}x{h}x1",
                    }
                },
                "show_images": True,
                "gallery": {
                    slug: {
                        "title_main_photo": "hinhanhsanpham",
                        "title_sub_photo": "hinhanh",
                        "status_photo": {"is_show": "hienthi"},
                        "number_photo": 3,
                        "images_photo": True,
                        "avatar_photo": True,
                        "name_photo": True,
                        "photo_width": w,
                        "photo_height": h,
                        "photo_thumb": f"{w}x{h}x1",
                    }
                },
            }
            prod_reqs_low = f"{entry['spec_requirements'].lower()} {notes_low}"
            has_figma_subcats = any(
                isinstance(s, dict)
                and _slugify_vi(str(s.get("name") or "")) in {"san-pham", "nhom-sp", "sp-noibat"}
                and bool(s.get("sub_categories"))
                for s in (tokens_data.get("sections") or [])
            )
            has_cat_icon_node = any(
                isinstance(n, dict)
                and n.get("section") == "san-pham"
                and n.get("role") == "item_icon"
                for n in (tokens_data.get("export_nodes") or [])
            )
            include_list_icon = cat_lvl > 0 and ("icon" in prod_reqs_low or has_cat_icon_node)
            product_by_list_on_home = cat_lvl > 0 and (
                "theo cấp 1 ra ngoài trang chủ" in prod_reqs_low
                or ("cấp 1" in prod_reqs_low and "trang chủ" in prod_reqs_low)
                or has_figma_subcats
            )
            if cat_lvl > 0:
                cfg["categories"] = _build_categories_block(cat_lvl, w, h, include_list_icon=include_list_icon)
            if options2:
                cfg["options2"] = options2
            products_cfg[slug] = cfg
            summary_items.append(
                {
                    "file": "config/type-products.php",
                    "key": slug,
                    "content_type": ctype,
                    "category_levels": cat_lvl,
                    "image_size": f"{w}x{h}",
                    "show_price": not hide_price,
                    "has_list_icon": include_list_icon,
                    "product_by_list_on_home": product_by_list_on_home,
                    "homepage": bool(entry.get("homepage", True)),
                }
            )

        elif slug in {"slide", "slideshow", "hero", "hero-banner", "doi-tac", "partner", "banner", "quang-cao"} or re.fullmatch(r"(?:quang-cao|banner)-\d+", slug):
            photo_key = "slideshow" if slug in {"slide", "slideshow", "hero", "hero-banner"} else slug
            def_w, def_h = (1920, 650) if photo_key == "slideshow" else (600, 450)
            w, h = _resolve_dimensions(
                photo_key,
                title,
                tokens_data,
                assets_manifest,
                def_w,
                def_h,
                figma_section_name=entry.get("figma_section_name", ""),
            )
            photo_cfg[photo_key] = {
                "title_main": title,
                "kind": "album",
                "status": {"is_show": "hienthi"},
                "number": 5,
                "images": True,
                "show_images": True,
                "gallery": True,
                "link": True,
                "name": True,
                "desc": False,
                "width": w,
                "height": h,
                "thumb": f"{w}x{h}x1",
            }
            sec_item_count = 1
            for s in tokens_data.get("sections") or []:
                if isinstance(s, dict) and _slugify_vi(str(s.get("name") or "")) == slug:
                    sec_item_count = max(1, int(s.get("item_count") or 1))
                    break
            summary_items.append(
                {
                    "file": "config/type-photo.php",
                    "key": photo_key,
                    "content_type": ctype,
                    "category_levels": 0,
                    "image_size": f"{w}x{h}",
                    "item_count": sec_item_count,
                    "homepage": bool(entry.get("homepage", True)),
                }
            )

        elif ctype in {"article_list", "video", "album", "feature"} or slug in {"tieu-chi", "vi-sao", "tai-sao", "thong-ke", "thanh-tuu", "vi-sao-chon", "cam-ket"}:
            route_name = "news" if slug == "tin-tuc" else ("service" if slug == "dich-vu" else slug)
            core_inner_news = {
                "tin-tuc",
                "dich-vu",
                "du-an",
                "cong-trinh",
                "tuyen-dung",
                "thu-vien-anh",
                "chinh-sach",
                "huong-dan",
                "bai-viet",
                "kien-thuc",
            }
            combined_spec_text = f"{notes_low} {entry['spec_requirements'].lower()}"
            explicit_no_inner = any(
                neg in combined_spec_text
                for neg in (
                    "không trang con",
                    "khong trang con",
                    "ko trang con",
                    "không có trang con",
                    "không trang trong",
                    "khong trang trong",
                )
            )
            has_inner_page = (
                bool(entry.get("in_menu"))
                or slug in core_inner_news
                or (
                    not explicit_no_inner
                    and any(
                        kw in combined_spec_text
                        for kw in ("trang trong", "trang con", "chi tiết", "chi tiet", "xem thêm", "xem them")
                    )
                )
            )
            prefer_icon = not has_inner_page and (
                "icon" in combined_spec_text or slug in {"vi-sao", "tai-sao", "tieu-chi"}
            )
            default_news_w, default_news_h = (800, 451) if ctype == "video" else (400, 300)
            raw_w, raw_h = _resolve_dimensions(
                slug,
                title,
                tokens_data,
                assets_manifest,
                default_news_w,
                default_news_h,
                figma_section_name=entry.get("figma_section_name", ""),
                prefer_icon=prefer_icon,
            )
            if ctype == "video" and raw_h > raw_w:
                raw_w, raw_h = 800, 451
            if not has_inner_page and slug in {"cam-nhan-khach-hang", "cam-nhan", "y-kien-khach-hang"} and raw_w >= 300:
                raw_w, raw_h = 150, 150
            if slug == "dich-vu" and "theo tin tức" in combined_spec_text and (raw_w, raw_h) == (400, 300):
                raw_w, raw_h = _resolve_dimensions("tin-tuc", "Tin Tức", tokens_data, assets_manifest, 400, 300)
            if not has_inner_page and raw_w <= 200:
                w, h = raw_w, raw_h
                thumb_mode = 2
            else:
                w, h = _scale_dimensions(raw_w, raw_h, min_width=400, scale_above=1.2)
                thumb_mode = 1

            if has_inner_page:
                cfg = {
                    "title_main": title,
                    "website": {
                        "amp": False,
                        "route": {
                            "controller": "NewsController@index",
                            "method": "get",
                            "slugs": {"vi": slug, "en": route_name},
                            "name": route_name,
                        },
                        "type": {"index": "object", "detail": "article"},
                        "title": title,
                    },
                    "name": True,
                    "slug": True,
                    "seo": True,
                    "show_images": True,
                    "images": {
                        "photo": {
                            "title": "anhdaidien",
                            "width": w,
                            "height": h,
                            "thumb": f"{w}x{h}x{thumb_mode}",
                        }
                    },
                    "status": (
                        {"is_featured": "noibat", "is_show": "hienthi"}
                        if entry.get("homepage")
                        else {"is_show": "hienthi"}
                    ),
                    "desc": True,
                    "content": True,
                    "content_cke": True,
                    "schema": True,
                    "view": True,
                    "datePublish": True,
                    "template_detail": "detail",
                    "dropdown": cat_lvl > 0,
                }
            else:
                cfg = {
                    "title_main": title,
                    "name": True,
                    "show_images": True,
                    "images": {
                        "photo": {
                            "title": "anhdaidien",
                            "width": w,
                            "height": h,
                            "thumb": f"{w}x{h}x{thumb_mode}",
                        }
                    },
                    "status": {"is_show": "hienthi"},
                }
                if ctype not in {"album", "video"}:
                    cfg["desc"] = True
            if ctype == "video":
                cfg["template"] = "video"
                if not options2:
                    options2 = {"link-youtube": {"type": "text", "title": "Link youtube", "lang": "true"}}
            if options2:
                cfg["options2"] = options2
            if cat_lvl > 0:
                cfg["categories"] = _build_categories_block(cat_lvl, w, h)
            news_cfg[slug] = cfg
            summary_items.append(
                {
                    "file": "config/type-news.php",
                    "key": slug,
                    "content_type": ctype,
                    "category_levels": cat_lvl,
                    "image_size": f"{w}x{h}",
                    "options2": list(options2.keys()) if options2 else [],
                    "options2_schema": options2,
                    "has_inner_page": has_inner_page,
                    "homepage": bool(entry.get("homepage", True)),
                }
            )

        elif ctype == "article_single":
            if slug in {"trang-chu", "home", "index", "lien-he"}:
                continue
            w, h = _resolve_dimensions(slug, title, tokens_data, assets_manifest, 600, 400)
            route_name = "about" if slug == "gioi-thieu" else ("rerecruitment" if slug == "tuyen-dung" else slug)
            about_photos = [
                n for n in (tokens_data.get("export_nodes") or [])
                if isinstance(n, dict) and n.get("section") == slug and n.get("role") == "item_photo"
            ]
            has_photo2 = slug == "gioi-thieu" and len(about_photos) >= 2
            images_blk_static: dict[str, Any] = {
                "photo": {
                    "title": "hinhanh",
                    "width": w,
                    "height": h,
                    "thumb": f"{w}x{h}x1",
                }
            }
            if has_photo2:
                w2 = int(about_photos[1].get("width") or 400)
                h2 = int(about_photos[1].get("height") or 311)
                images_blk_static["photo2"] = {
                    "title": "Hình ảnh 2",
                    "width": w2,
                    "height": h2,
                    "thumb": f"{w2}x{h2}x1",
                }
            static_cfg[slug] = {
                "title_main": title,
                "website": {
                    "type": "object",
                    "title": title,
                    "route": {
                        "controller": "StaticController@index",
                        "name": route_name,
                        "method": "get",
                        "slugs": {"vi": slug, "en": route_name},
                    },
                },
                "images": images_blk_static,
                "name": True,
                "desc": True,
                "desc_cke": slug == "gioi-thieu" and has_photo2,
                "content": True,
                "content_cke": True,
                "seo": True,
            }
            summary_items.append(
                {
                    "file": "config/type-static.php",
                    "key": slug,
                    "content_type": ctype,
                    "category_levels": 0,
                    "image_size": f"{w}x{h}",
                    "has_photo2": has_photo2,
                    "homepage": bool(entry.get("homepage", True)),
                }
            )

        elif ctype == "form":
            newsletters_cfg[slug] = {
                "title_main": title,
                "file": True,
                "email": True,
                "fullname": True,
                "phone": True,
                "address": True,
                "subject": True,
                "content": True,
                "show_subject": True,
                "show_fullname": True,
                "show_phone": True,
            }
            summary_items.append(
                {
                    "file": "config/type-newsletters.php",
                    "key": slug,
                    "content_type": ctype,
                    "category_levels": 0,
                    "image_size": "-",
                }
            )

        # Auto-create admin-editable slogan/description static entry ONLY when spec explicitly asks for it (or homepage video has heading+desc)
        reqs_slug = _slugify_vi(entry["spec_requirements"])
        no_auto_slogan_slugs = {"footer", "copyright", "slogan", "header", "tieu-chi", "vi-sao", "tai-sao", "thong-ke", "thanh-tuu", "quang-cao", "slide", "slideshow"}
        video_has_slogan = slug == "video" and (
            bool(entry.get("homepage"))
            or any(
                isinstance(s, dict) and _slugify_vi(str(s.get("name") or "")) == "video" and len(s.get("texts") or []) >= 1
                for s in (tokens_data.get("sections") or [])
            )
        )
        wants_section_slogan = (
            ctype not in {"article_single", "form"}
            and slug not in no_auto_slogan_slugs
            and not re.fullmatch(r"(?:quang-cao|banner)-\d+", slug)
            and (
                video_has_slogan
                or any(k in reqs_slug for k in ("slogan", "mo-ta-chu-nho", "chu-nho", "mo-ta-goc-phai"))
                or ("mo-ta" in reqs_slug and "admin" in reqs_slug)
            )
        )
        if wants_section_slogan:
            slogan_key = f"slogan-{slug}"
            if slogan_key not in static_cfg:
                static_cfg[slogan_key] = {
                    "title_main": f"Slogan {title}",
                    "name": True,
                    "desc": True,
                    "desc_cke": False,
                    "content": False,
                    "content_cke": False,
                }
                summary_items.append(
                    {
                        "file": "config/type-static.php",
                        "key": slogan_key,
                        "content_type": "article_single",
                        "category_levels": 0,
                        "image_size": "-",
                        "homepage": bool(entry.get("homepage", True)),
                    }
                )

    # Ensure core Nasanic static & photo entries always exist
    static_cfg.setdefault(
        "lien-he",
        {
            "title_main": "Liên hệ",
            "website": {
                "type": "object",
                "title": "Liên hệ",
                "route": {
                    "controller": "ContactController@index",
                    "name": "contact",
                    "method": "get",
                    "slugs": {"vi": "lien-he", "en": "contact"},
                },
            },
            "images": {
                "photo": {
                    "title": "hinhanh",
                    "width": 300,
                    "height": 300,
                    "thumb": "300x300x1",
                }
            },
            "name": False,
            "content": True,
            "content_cke": True,
            "seo": True,
        },
    )
    static_cfg.setdefault(
        "footer",
        {"title_main": "footer", "name": True, "desc": False, "content": True, "content_cke": True},
    )
    static_cfg.setdefault("copyright", {"title_main": "Copyright", "name": True})
    static_cfg.setdefault("slogan", {"title_main": "Slogan", "name": True})

    logo_w, logo_h = _resolve_dimensions("logo", "logo", tokens_data, assets_manifest, 100, 90)
    static_photo_head: dict[str, Any] = {}
    static_photo_head["logo"] = photo_cfg.pop(
        "logo",
        {
            "title_main": "logo",
            "kind": "static",
            "title": True,
            "link": False,
            "images": True,
            "width": logo_w,
            "height": logo_h,
            "thumb": f"{logo_w}x{logo_h}x2",
        },
    )
    static_photo_head["favicon"] = photo_cfg.pop(
        "favicon",
        {
            "title_main": "favicon",
            "kind": "static",
            "images": True,
            "width": 48,
            "height": 48,
            "thumb": "48x48x1",
        },
    )
    if "banner" in header_reqs:
        bw, bh = _resolve_dimensions("banner", "banner", tokens_data, assets_manifest, 563, 105)
        if bw >= 1000:
            bw, bh = 563, 105
        static_photo_head["banner"] = photo_cfg.pop(
            "banner",
            {
                "title_main": "Banner",
                "kind": "static",
                "title": True,
                "link": False,
                "images": True,
                "width": bw,
                "height": bh,
                "thumb": f"{bw}x{bh}x2",
            },
        )
    footer_logo_node = next(
        (
            n
            for n in (tokens_data.get("export_nodes") or [])
            if isinstance(n, dict) and n.get("section") == "footer" and n.get("role") == "item_photo" and int(n.get("width") or 0) <= 180
        ),
        None,
    )
    if footer_logo_node is not None:
        fl_w = int(footer_logo_node.get("width") or logo_w)
        fl_h = int(footer_logo_node.get("height") or logo_h)
        static_photo_head["logo-footer"] = {
            "title_main": "Logo Footer",
            "kind": "static",
            "title": True,
            "link": False,
            "images": True,
            "width": fl_w,
            "height": fl_h,
            "thumb": f"{fl_w}x{fl_h}x2",
        }
    if any("banner cho menu" in g.lower() or "mỗi menu có 1 banner" in g.lower() for g in global_features):
        for m_slug, m_entry in merged_entries.items():
            if m_entry.get("in_menu") and m_slug not in {"trang-chu"}:
                b_key = f"banner-{m_slug}"
                static_photo_head[b_key] = {
                    "title_main": f"Banner {m_entry['title']}",
                    "kind": "static",
                    "title": True,
                    "link": False,
                    "images": True,
                    "width": 1920,
                    "height": 400,
                    "thumb": "1920x400x1",
                }
    if enable_watermark:
        static_photo_head["watermark_product"] = photo_cfg.pop(
            "watermark_product",
            {
                "title_main": "condausanpham",
                "kind": "static",
                "watermark": True,
                "desc": False,
                "title": False,
                "desc_cke": False,
                "link": False,
                "status": {"is_show": "hienthi"},
                "images": True,
                "width": 150,
                "height": 150,
                "thumb": "150x150x1",
            },
        )
    if "slideshow" not in photo_cfg:
        sl_w, sl_h = _resolve_dimensions("slideshow", "slideshow", tokens_data, assets_manifest, 1920, 650)
        photo_cfg["slideshow"] = {
            "title_main": "slideshow",
            "kind": "album",
            "status": {"is_show": "hienthi"},
            "number": 5,
            "images": True,
            "show_images": True,
            "gallery": True,
            "link": True,
            "name": True,
            "desc": False,
            "width": sl_w,
            "height": sl_h,
            "thumb": f"{sl_w}x{sl_h}x1",
        }
    social_icon_node = next(
        (
            n
            for n in (tokens_data.get("export_nodes") or [])
            if isinstance(n, dict) and n.get("role") == "item_icon" and n.get("section") in {"footer", "social"} and 16 <= int(n.get("width") or 0) <= 48
        ),
        None,
    )
    soc_w = int(social_icon_node.get("width") or 27) if social_icon_node else 27
    soc_h = int(social_icon_node.get("height") or 27) if social_icon_node else 27
    photo_cfg.setdefault(
        "social",
        {
            "title_main": "mangxahoi",
            "kind": "album",
            "status": {"is_show": "hienthi"},
            "number": 4,
            "show_images": True,
            "images": True,
            "avatar": True,
            "link": True,
            "name": True,
            "desc": False,
            "width": soc_w,
            "height": soc_h,
            "thumb": f"{soc_w}x{soc_h}x2",
        },
    )
    photo_cfg = {**static_photo_head, **photo_cfg}

    if not newsletters_cfg:
        newsletters_cfg["lien-he"] = {
            "title_main": "lienhe",
            "file": True,
            "email": True,
            "fullname": True,
            "phone": True,
            "address": True,
            "subject": True,
            "content": True,
            "show_subject": True,
            "show_fullname": True,
            "show_phone": True,
        }

    written_files: list[str] = []
    file_map = {
        "type-products.php": products_cfg,
        "type-news.php": news_cfg,
        "type-static.php": static_cfg,
        "type-photo.php": photo_cfg,
        "type-newsletters.php": newsletters_cfg,
    }
    for fname, payload in file_map.items():
        (config_dir / fname).write_text(_render_php_return(payload), encoding="utf-8")
        written_files.append(f"config/{fname}")

    return {
        "written_files": written_files,
        "watermark_enabled": enable_watermark,
        "configured_types": summary_items,
    }


_SLUG_TO_EN = {
    "san-pham": "products",
    "san-pham-noi-bat": "featuredProducts",
    "dich-vu": "services",
    "tin-tuc": "news",
    "tieu-chi": "criteria",
    "vi-sao": "why",
    "tai-sao": "why",
    "thanh-tuu": "achievements",
    "thong-ke": "stats",
    "album": "albums",
    "album-hinh-anh-hoat-dong": "albums",
    "thu-vien-anh": "albums",
    "quang-cao": "ads",
    "doi-tac": "partners",
    "video": "videos",
    "gioi-thieu": "about",
    "tuyen-dung": "careers",
    "du-an": "projects",
    "cong-trinh": "projects",
    "chinh-sach": "policies",
    "cam-nhan-khach-hang": "customer",
    "y-kien": "customer",
    "y-kien-khach-hang": "testimonials",
    "khach-hang": "testimonials",
    "vi-sao-chon": "whyChooseUs",
    "vi-sao-chon-chung-toi": "whyChooseUs",
    "cam-ket": "commitments",
    "slideshow": "slideshow",
}


def _to_camel(slug: str) -> str:
    parts = [p for p in re.split(r"[^a-zA-Z0-9]+", slug) if p]
    if not parts:
        return "item"
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])


def _to_english_php_var(kind: str, slug: str) -> str:
    if slug.startswith("slogan-"):
        base = slug[7:]
        en_base = _SLUG_TO_EN.get(base) or _to_camel(base)
        return f"$slogan{en_base[0].upper()}{en_base[1:]}"
    m_ad = re.fullmatch(r"(quang-cao|banner)-(\d+)", slug)
    if m_ad:
        return f"$ads{m_ad.group(2)}"
    en = _SLUG_TO_EN.get(slug) or _to_camel(slug)
    if kind in {"nav_product", "nav_news"}:
        return f"$nav{en[0].upper()}{en[1:]}"
    return f"${en}"


_PROTECTED_SYSTEM_TYPES = {
    "slideshow",
    "logo",
    "favicon",
    "social",
    "footer",
    "copyright",
    "slogan",
    "popup",
    "hotline",
    "chen-link-tu-khoa",
}


def _prune_unused_controller_queries(
    src: str,
    active_keys: set[str],
) -> tuple[str, list[str]]:
    """
    Remove unused `$homeNews('x', ...)`, `$homePhotos('x', ...)`, and `*Model::...->where('type', 'x')...;`
    statements from HomeController/AllController when `x` is not in `active_keys` or protected system types.
    """
    keep_keys = active_keys | _PROTECTED_SYSTEM_TYPES
    pruned: list[str] = []
    removed_vars: set[str] = set()

    # 1. Single-line $var = $homePhotos('type', N); or $homeNews('type', N);
    def _repl_helper(m: re.Match[str]) -> str:
        var_name, t_key = m.group(1), m.group(2)
        if t_key in keep_keys:
            return m.group(0)
        pruned.append(t_key)
        removed_vars.add(var_name)
        return ""

    src = re.sub(
        r"^[ \t]*(\$\w+)\s*=\s*\$(?:homePhotos|homeNews)\(\s*['\"]([a-z0-9-]+)['\"]\s*,\s*\d+\s*\)\s*;\r?\n?",
        _repl_helper,
        src,
        flags=re.MULTILINE,
    )

    # 2. Multi-line $var = *Model::...->where('type', 'x')...;
    def _repl_eloquent(m: re.Match[str]) -> str:
        var_name, t_key = m.group(1), m.group(2)
        if t_key in keep_keys:
            return m.group(0)
        pruned.append(t_key)
        removed_vars.add(var_name)
        return ""

    src = re.sub(
        r"^[ \t]*(\$\w+)\s*=\s*(?:Product|News|Static|Photo|ProductList|NewsList)Model::[\s\S]*?->where\(\s*['\"]type['\"]\s*,\s*['\"]([a-z0-9-]+)['\"]\s*\)[\s\S]*?;\r?\n?",
        _repl_eloquent,
        src,
        flags=re.MULTILINE,
    )

    # 3. Clean up derived lines referencing removed variables (e.g. $branches = $footerNews->...)
    for rvar in removed_vars:
        escaped = re.escape(rvar)
        src = re.sub(
            rf"^[ \t]*\$\w+\s*=\s*{escaped}->[^\n;]+;\r?\n?",
            "",
            src,
            flags=re.MULTILINE,
        )

    # 4. If $branches is not defined (e.g. pruned or absent), remove the $mapIframe foreach($branches) block
    if not re.search(r"\$branches\s*=", src):
        src = re.sub(
            r"(?:^[ \t]*\$mapIframe\s*=\s*['\"]{2}\s*;\r?\n)?"
            r"^[ \t]*foreach\s*\(\s*\$branches\s+as\s+\$\w+\s*\)\s*\{(?:\{[^{}]*\}|[^{}])*\}\r?\n?"
            r"(?:[ \t]*if\s*\(\s*empty\(\s*\$mapIframe\s*\)\s*\)\s*\{[^{}]*\}\r?\n?)?",
            "",
            src,
            flags=re.MULTILINE,
        )

    # Collapse excessive blank lines created by pruning
    src = re.sub(r"\n{3,}", "\n\n", src)
    return src, pruned


def wire_nasanic_controllers(
    target_source_dir: Path,
    config_summary: dict[str, Any],
) -> dict[str, Any]:
    """
    Prune unused queries and inject missing data queries into
    `src/Controllers/Web/HomeController.php` and `src/Controllers/Web/AllController.php`
    so Blade views only receive queries matching `config/type-*.php`.
    """
    web_ctrl_dir = target_source_dir / "src" / "Controllers" / "Web"
    home_path = web_ctrl_dir / "HomeController.php"
    all_path = web_ctrl_dir / "AllController.php"

    updated_files: list[str] = []
    home_vars: list[dict[str, str]] = []
    all_vars: list[dict[str, str]] = []
    pruned_types: list[str] = []

    configured = config_summary.get("configured_types") or []
    active_keys = {str(item.get("key") or "") for item in configured if item.get("key")}
    home_active_keys = {
        str(item.get("key") or "")
        for item in configured
        if item.get("key") and item.get("homepage", True)
    }

    # 1. HomeController.php (ONLY homepage types)
    if home_path.is_file():
        orig_home_src = home_path.read_text(encoding="utf-8", errors="ignore")
        home_src, pruned_home = _prune_unused_controller_queries(orig_home_src, home_active_keys)
        pruned_types.extend(pruned_home)
        if "san-pham" in home_active_keys:
            home_src = re.sub(
                r"^[ \t]*\$productNew\s*=\s*ProductModel::[\s\S]*?;\r?\n?",
                "",
                home_src,
                flags=re.MULTILINE,
            )
        if "tin-tuc" in home_active_keys:
            home_src = re.sub(
                r"^[ \t]*\$newsnb\s*=\s*NewsModel::[\s\S]*?;\r?\n?",
                "",
                home_src,
                flags=re.MULTILINE,
            )
        home_src = re.sub(r"\n{3,}", "\n\n", home_src)
        home_lines: list[str] = []
        for item in configured:
            if not item.get("homepage", True):
                continue
            cfg_file = str(item.get("file") or "")
            key = str(item.get("key") or "")
            if not key:
                continue

            if cfg_file.endswith("type-products.php"):
                var_name = _to_english_php_var("product", key)
                home_vars.append({"var": var_name, "type": key, "kind": "product"})
                if not re.search(rf"{re.escape(var_name)}\s*=", home_src):
                    home_lines.extend(
                        [
                            f"            {var_name} = ProductModel::select('id', 'name' . $this->lang, 'desc' . $this->lang, 'slug' . $this->lang, 'photo', 'regular_price', 'sale_price', 'discount', 'type')",
                            f"                ->withEffectivePrice()",
                            f"                ->where('type', '{key}')",
                            f"                ->status('is_show')",
                            f"                ->orderBy('numb', 'asc')",
                            f"                ->orderBy('id', 'desc')",
                            f"                ->limit(20)",
                            f"                ->get();",
                        ]
                    )
                if item.get("product_by_list_on_home") and "$productListNB" not in home_src:
                    home_vars.append({"var": "$productListNB", "type": key, "kind": "product_list"})
                    home_lines.extend(
                        [
                            f"            $productListNB = ProductListModel::select('id', 'name' . $this->lang, 'slug' . $this->lang, 'photo', 'icon', 'type')",
                            f"                ->where('type', '{key}')",
                            f"                ->status('is_show', 'is_featured')",
                            f"                ->with(['getItems' => function ($query) {{",
                            f"                    $query->select('id', 'id_list', 'name' . $this->lang, 'slug' . $this->lang, 'photo', 'regular_price', 'sale_price', 'discount', 'type')",
                            f"                        ->where('type', '{key}')",
                            f"                        ->status('is_show', 'is_featured')",
                            f"                        ->orderBy('numb', 'asc')",
                            f"                        ->orderBy('id', 'desc')->take(6);",
                            f"                }}])",
                            f"                ->orderBy('numb', 'asc')",
                            f"                ->orderBy('id', 'desc')",
                            f"                ->get()",
                            f"                ->each(function ($list) {{ $list->setRelation('getItems', $list->getItems->take(6)); }});",
                        ]
                    )
            elif cfg_file.endswith("type-news.php"):
                var_name = _to_english_php_var("news", key)
                home_vars.append({"var": var_name, "type": key, "kind": "news"})
                if not re.search(rf"{re.escape(var_name)}\s*=", home_src):
                    home_lines.append(f"            {var_name} = $homeNews('{key}', 12);")
            elif cfg_file.endswith("type-static.php"):
                var_name = _to_english_php_var("static", key)
                home_vars.append({"var": var_name, "type": key, "kind": "static"})
                if item.get("has_photo2") and var_name == "$about" and "'photo2'" not in home_src:
                    home_src = home_src.replace("'photo', 'options2'", "'photo', 'photo2', 'options2', 'type'")
                if not re.search(rf"{re.escape(var_name)}\s*=", home_src):
                    cols_expr = "'id', 'name' . $this->lang, 'desc' . $this->lang, 'content' . $this->lang, 'photo', 'photo2', 'options2'" if item.get("has_photo2") else "'id', 'name' . $this->lang, 'desc' . $this->lang, 'content' . $this->lang, 'photo', 'options2'"
                    home_lines.extend(
                        [
                            f"            {var_name} = StaticModel::select({cols_expr})",
                            f"                ->where('type', '{key}')",
                            f"                ->first();",
                        ]
                    )
            elif cfg_file.endswith("type-photo.php"):
                var_name = _to_english_php_var("photo", key)
                home_vars.append({"var": var_name, "type": key, "kind": "photo"})
                if not re.search(rf"{re.escape(var_name)}\s*=", home_src):
                    home_lines.append(f"            {var_name} = $homePhotos('{key}', 12);")

        if home_lines and "return get_defined_vars();" in home_src:
            inject_block = (
                "            // [RBWOfficeAI] Auto-wired queries from config/type\n"
                + "\n".join(home_lines)
                + "\n\n            return get_defined_vars();"
            )
            home_src = home_src.replace("            return get_defined_vars();", inject_block, 1)

        if home_src != orig_home_src:
            home_path.write_text(home_src, encoding="utf-8")
            updated_files.append("src/Controllers/Web/HomeController.php")

    # 2. AllController.php (menu / category lists shared globally)
    if all_path.is_file():
        orig_all_src = all_path.read_text(encoding="utf-8", errors="ignore")
        all_src, pruned_all = _prune_unused_controller_queries(orig_all_src, active_keys)
        pruned_types.extend(pruned_all)
        all_lines: list[str] = []
        need_news_list_import = False

        for item in configured:
            cfg_file = str(item.get("file") or "")
            key = str(item.get("key") or "")
            cat_lvl = int(item.get("category_levels") or 0)
            if not key or cat_lvl <= 0:
                continue
            already_queried = f"'{key}'" in all_src or f'"{key}"' in all_src

            if cfg_file.endswith("type-products.php"):
                var_name = _to_english_php_var("nav_product", key)
                all_vars.append({"var": var_name, "type": key, "levels": str(cat_lvl)})
                if not already_queried and var_name not in all_src:
                    if cat_lvl >= 2:
                        all_lines.extend(
                            [
                                f"            {var_name} = ProductListModel::select('id', 'name' . $lang, 'slug' . $lang, 'type')",
                                f"                ->where('type', '{key}')",
                                f"                ->status('is_show')",
                                f"                ->with(['getCategoryCats' => fn($q) => $q->select('id', 'id_list', 'name' . $lang, 'slug' . $lang, 'type')->status('is_show')->orderBy('numb', 'asc')])",
                                f"                ->orderBy('numb', 'asc')",
                                f"                ->orderBy('id', 'desc')",
                                f"                ->get();",
                            ]
                        )
                    else:
                        all_lines.extend(
                            [
                                f"            {var_name} = ProductListModel::select('id', 'name' . $lang, 'slug' . $lang, 'type')",
                                f"                ->where('type', '{key}')",
                                f"                ->status('is_show')",
                                f"                ->orderBy('numb', 'asc')",
                                f"                ->orderBy('id', 'desc')",
                                f"                ->get();",
                            ]
                        )
            elif cfg_file.endswith("type-news.php"):
                var_name = _to_english_php_var("nav_news", key)
                all_vars.append({"var": var_name, "type": key, "levels": str(cat_lvl)})
                if not already_queried and var_name not in all_src:
                    need_news_list_import = True
                    all_lines.extend(
                        [
                            f"            {var_name} = NewsListModel::select('id', 'name' . $lang, 'slug' . $lang, 'type')",
                            f"                ->where('type', '{key}')",
                            f"                ->status('is_show')",
                            f"                ->orderBy('numb', 'asc')",
                            f"                ->orderBy('id', 'desc')",
                            f"                ->get();",
                        ]
                    )

        if all_lines and "return get_defined_vars();" in all_src:
            if need_news_list_import and "NewsListModel" not in all_src:
                all_src = all_src.replace(
                    "use NASANICORE\\Models\\NewsModel;",
                    "use NASANICORE\\Models\\NewsModel;\nuse NASANICORE\\Models\\NewsListModel;",
                    1,
                )
            inject_block = (
                "            // [RBWOfficeAI] Auto-wired global menu category queries\n"
                + "\n".join(all_lines)
                + "\n\n            return get_defined_vars();"
            )
            all_src = all_src.replace("            return get_defined_vars();", inject_block, 1)

        if all_src != orig_all_src:
            all_path.write_text(all_src, encoding="utf-8")
            updated_files.append("src/Controllers/Web/AllController.php")

    return {
        "updated_files": updated_files,
        "home_vars": home_vars,
        "all_vars": all_vars,
        "pruned_types": sorted(set(pruned_types)),
    }

