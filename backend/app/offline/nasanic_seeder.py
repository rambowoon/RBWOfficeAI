from __future__ import annotations

import json
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

from .nasanic_configurator import _slugify_vi


def _parse_laravel_env(env_path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not env_path.is_file():
        return out
    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _get_table_columns(cur: Any, table: str) -> set[str]:
    cur.execute(f"SHOW COLUMNS FROM `{table}`")
    return {row[0] for row in cur.fetchall()}


def _ensure_image_columns(
    cur: Any,
    table: str,
    existing_cols: set[str],
    required_cols: set[str] | list[str] | tuple[str, ...],
) -> None:
    """Ensure extra image columns (e.g. photo2, icon) exist with utf8mb4_general_ci."""
    for col in required_cols:
        col_clean = str(col or "").strip()
        if not col_clean or col_clean in existing_cols or not re.fullmatch(r"[a-zA-Z0-9_]+", col_clean):
            continue
        after_clause = " AFTER `photo`" if "photo" in existing_cols else ""
        cur.execute(
            f"ALTER TABLE `{table}` ADD COLUMN `{col_clean}` varchar(255) "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL{after_clause}"
        )
        existing_cols.add(col_clean)


def _scan_config_image_columns(config_dir: Path, prefix: str) -> dict[str, set[str]]:
    """Extract custom image column names (photo2, icon, ...) per DB table from config/type-*.php."""
    out: dict[str, set[str]] = {}
    file_to_base = {
        "type-static.php": "static",
        "type-products.php": "product",
        "type-news.php": "news",
    }
    for fname, base in file_to_base.items():
        fpath = config_dir / fname
        if not fpath.is_file():
            continue
        text = fpath.read_text(encoding="utf-8", errors="ignore")
        # Detect top-level 'images' => [ 'col' => [ ... ] ] vs inside 'categories' -> 'list'/'cat'/'item'
        cat_pos = text.find("'categories'")
        main_part = text[:cat_pos] if cat_pos >= 0 else text
        for blk_match in re.finditer(r"'images'\s*=>\s*\[(.*?)\n\s*\]", main_part, re.DOTALL):
            for key_match in re.finditer(r"^\s*'([a-zA-Z0-9_]+)'\s*=>\s*\[", blk_match.group(1), re.MULTILINE):
                col = key_match.group(1)
                if col != "photo":
                    out.setdefault(f"{prefix}{base}", set()).add(col)
        if cat_pos >= 0:
            cat_part = text[cat_pos:]
            for lvl in ("list", "cat", "item"):
                lvl_m = re.search(rf"'{lvl}'\s*=>\s*\[(.*?)(?='(?:cat|item)'\s*=>|\Z)", cat_part, re.DOTALL)
                if not lvl_m:
                    continue
                for blk_match in re.finditer(r"'images'\s*=>\s*\[(.*?)\n\s*\]", lvl_m.group(1), re.DOTALL):
                    for key_match in re.finditer(r"^\s*'([a-zA-Z0-9_]+)'\s*=>\s*\[", blk_match.group(1), re.MULTILINE):
                        col = key_match.group(1)
                        if col != "photo":
                            out.setdefault(f"{prefix}{base}_{lvl}", set()).add(col)
    return out


def _table_exists(cur: Any, table: str) -> bool:
    cur.execute("SHOW TABLES LIKE %s", (table,))
    return cur.fetchone() is not None


def _insert_row(cur: Any, table: str, data: dict[str, Any]) -> int:
    cols = ", ".join(f"`{k}`" for k in data)
    phs = ", ".join(["%s"] * len(data))
    cur.execute(f"INSERT INTO `{table}` ({cols}) VALUES ({phs})", list(data.values()))
    return int(cur.lastrowid)


def _make_unique_slug(base_slug: str, used_slugs: set[str]) -> str:
    clean = re.sub(r"[^a-z0-9-]+", "-", (base_slug or "muc").lower()).strip("-") or "muc"
    candidate = clean
    suffix = 2
    while candidate in used_slugs:
        candidate = f"{clean}-{suffix}"
        suffix += 1
    used_slugs.add(candidate)
    return candidate


_SECTION_IMAGE_ALIASES: dict[str, tuple[str, ...]] = {
    "san-pham": ("san-pham", "nhom-sp", "sp-noibat", "sp", "product", "khu", "bong", "vai", "soi"),
    "quang-cao": ("quang-cao-1", "quang-cao", "quangcao", "qc"),
    "quang-cao-2": ("quang-cao-2", "qc-1", "qc-2"),
    "slideshow": ("slideshow", "slide", "hing", "nh-1", "hero"),
    "tieu-chi": ("tieu-chi", "tieuchi", "tai-sao", "vi-sao"),
    "tai-sao": ("tai-sao", "tieu-chi", "vi-sao"),
    "vi-sao": ("vi-sao", "visao", "tieu-chi", "tai-sao"),
    "album": ("album", "thu-vien"),
    "album-hinh-anh-hoat-dong": ("album", "thu-vien"),
    "thanh-tuu": ("thanh-tuu", "thanhtuu", "thong-ke", "map"),
    "thong-ke": ("thong-ke", "thanh-tuu", "thanhtuu"),
    "tin-tuc": ("tin-tuc", "tintuc", "news"),
    "cam-nhan-khach-hang": ("cam-nhan", "y-kien", "khach-hang"),
    "gioi-thieu": ("gioi-thieu", "gioithieu", "about", "hinh"),
    "video": ("video", "may-keo"),
    "logo": ("logo",),
}


def _pick_section_images(
    images_pool: list[Path],
    type_key: str,
    *,
    prefer_icon: bool = False,
) -> list[Path]:
    """
    Pick Figma-exported images matching `type_key` (excluding `bg-*` section backgrounds).
    When `prefer_icon=True`, prioritize `*-icon-*` exported vector icons first.
    """
    if not images_pool:
        return []
    clean_pool = [p for p in images_pool if not p.stem.lower().startswith("bg-")]
    if not clean_pool:
        clean_pool = list(images_pool)

    aliases = _SECTION_IMAGE_ALIASES.get(type_key, ())
    tokens = {t for t in type_key.split("-") if len(t) >= 2}

    def _matches(p: Path) -> bool:
        stem = p.stem.lower()
        if stem.startswith(type_key):
            return True
        if aliases and any(a in stem for a in aliases):
            return True
        if stem not in {"logo", "favicon"} and tokens and any(tok in stem for tok in tokens):
            return True
        return False

    section_hits = [p for p in clean_pool if _matches(p)]
    if prefer_icon:
        sec_icons = [p for p in section_hits if "-icon-" in p.stem.lower() or p.stem.lower().startswith("icon-")]
        if sec_icons:
            return sec_icons
        any_icons = [p for p in clean_pool if "-icon-" in p.stem.lower()]
        if any_icons:
            return any_icons

    if section_hits:
        non_icon_hits = [p for p in section_hits if "-icon-" not in p.stem.lower()]
        return non_icon_hits or section_hits

    non_logo = [
        p for p in clean_pool
        if "logo" not in p.stem.lower() and "favicon" not in p.stem.lower()
    ]
    return non_logo or clean_pool


def _copy_seed_image(
    src_images: list[Path],
    idx: int,
    upload_dir: Path,
    upload_folder: str,
    type_key: str = "",
    *,
    prefer_icon: bool = False,
) -> str:
    """Copy (or convert to WebP quality=100) into `upload/{upload_folder}/YYYY/MM/DD/...webp` and return DB `photo` path."""
    pool = _pick_section_images(src_images, type_key, prefer_icon=prefer_icon) if type_key else src_images
    if not pool:
        return ""
    src = pool[idx % len(pool)]
    if not src.is_file():
        return ""
    date_subpath = datetime.now().strftime("%Y/%m/%d")
    dest_dir = upload_dir / date_subpath
    dest_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    dst_name = f"seed-{ts}-{idx}-{src.stem}.webp"
    dest_path = dest_dir / dst_name
    if src.suffix.lower() == ".webp":
        shutil.copy2(src, dest_path)
    else:
        try:
            with Image.open(src) as im:
                im.convert("RGBA").save(dest_path, format="WEBP", quality=100, method=6)
        except Exception:
            dst_name = f"seed-{ts}-{idx}-{src.name}"
            dest_path = dest_dir / dst_name
            shutil.copy2(src, dest_path)
    return f"{upload_folder}/{date_subpath}/{dst_name}"


def build_figma_and_ai_seed_data(
    tokens_data: dict[str, Any],
    config_summary: dict[str, Any],
    project_name: str,
    base_seed: dict[str, Any],
    ai_seed_override: dict[str, Any] | None = None,
    spec_metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Combine Figma extracted `sections` texts + `contact_info` with optional AI-generated
    structured seed items (including `options2` values like `statistical`, `link-youtube`, `address`).
    """
    out = dict(base_seed or {})
    contact_info = dict(tokens_data.get("contact_info") or {})
    contract_name = str((spec_metadata or {}).get("contract_name") or "").strip()
    if contract_name and len(contract_name) > len(str(contact_info.get("company_name") or "")):
        contact_info["company_name"] = contract_name
    if ai_seed_override and isinstance(ai_seed_override.get("contact_info"), dict):
        for k, v in ai_seed_override["contact_info"].items():
            if v:
                contact_info[k] = str(v).strip()
    out["contact_info"] = contact_info

    # Extract product sub-categories from Figma (e.g. ["Bông", "Vải", "Sợi"]) or AI
    prod_cats: list[str] = []
    if ai_seed_override and isinstance(ai_seed_override.get("product_categories"), list):
        prod_cats = [str(x).strip() for x in ai_seed_override["product_categories"] if str(x).strip()]
    if not prod_cats:
        for sec in tokens_data.get("sections") or []:
            if isinstance(sec, dict) and sec.get("sub_categories"):
                prod_cats = [str(x).strip() for x in sec["sub_categories"] if str(x).strip()]
                break
    out["product_categories"] = prod_cats

    figma_sec_texts: dict[str, list[str]] = {}
    for sec in tokens_data.get("sections") or []:
        if isinstance(sec, dict) and sec.get("name") and sec.get("texts"):
            figma_sec_texts[_slugify_vi(str(sec["name"]))] = list(sec["texts"])
    out["figma_section_texts"] = figma_sec_texts

    section_items: dict[str, list[dict[str, Any]]] = {}
    ai_sections = (ai_seed_override or {}).get("section_items")
    if isinstance(ai_sections, dict):
        for k, rows in ai_sections.items():
            if isinstance(rows, list):
                section_items[str(k)] = [r for r in rows if isinstance(r, dict)]

    # Deterministic Figma-text extraction fallback for any type missing from AI override
    for item in config_summary.get("configured_types") or []:
        t_key = str(item.get("key") or "")
        if not t_key or t_key in section_items:
            continue
        texts: list[str] = list(figma_sec_texts.get(t_key) or [])
        if not texts:
            for fk, fvals in figma_sec_texts.items():
                if t_key in fk or fk in t_key:
                    texts = list(fvals)
                    break
        opts_schema = item.get("options2_schema") or {}
        if opts_schema and "statistical" in opts_schema and texts:
            stat_pairs: list[dict[str, Any]] = []
            nums = [t for t in texts if re.fullmatch(r"[\d.,]+\s*\+*%?", t.strip())]
            labels = [t for t in texts if len(t) >= 4 and not re.fullmatch(r"[\d.,]+\s*\+*%?", t.strip()) and "CÔNG TY" not in t.upper()]
            for i in range(max(len(nums), 4)):
                num_val = nums[i] if i < len(nums) else f"{(i + 1) * 50}+"
                lbl_val = labels[i] if i < len(labels) else f"Thành tựu #{i + 1}"
                stat_pairs.append({"name": lbl_val, "desc": lbl_val, "options2": {"statistical": num_val}})
            section_items[t_key] = stat_pairs[:4]
        elif texts:
            clean_texts = [
                t for t in texts
                if len(t) >= 3 and t.upper() not in {"LIÊN HỆ NGAY", "XEM TẤT CẢ", "XEM CHI TIẾT"}
            ]
            if clean_texts:
                if opts_schema and "address" in opts_schema:
                    section_items[t_key] = [
                        {"name": t[:120], "desc": t, "options2": {"address": "TP. Hồ Chí Minh"}}
                        for t in clean_texts[:4]
                    ]
                else:
                    section_items[t_key] = [
                        {"name": t[:120], "desc": t} for t in clean_texts[:6]
                    ]

    out["section_items"] = section_items
    return out


def _wipe_template_tables(cur: Any, prefix: str) -> None:
    tables = [
        f"{prefix}product_status",
        f"{prefix}product",
        f"{prefix}product_list_status",
        f"{prefix}product_list",
        f"{prefix}product_cat_status",
        f"{prefix}product_cat",
        f"{prefix}product_item",
        f"{prefix}product_sub",
        f"{prefix}news_status",
        f"{prefix}news",
        f"{prefix}news_list",
        f"{prefix}news_cat",
        f"{prefix}news_item",
        f"{prefix}news_sub",
        f"{prefix}static",
        f"{prefix}slug",
        f"{prefix}photo_status",
        f"{prefix}photo",
    ]
    for tbl in tables:
        if _table_exists(cur, tbl):
            cur.execute(f"DELETE FROM `{tbl}`")


def _update_setting_table(cur: Any, prefix: str, contact_info: dict[str, str], project_name: str) -> None:
    tbl = f"{prefix}setting"
    if not _table_exists(cur, tbl):
        return
    cols = _get_table_columns(cur, tbl)
    cur.execute(f"SELECT id, options FROM `{tbl}` ORDER BY id ASC LIMIT 1")
    row = cur.fetchone()
    company_name = contact_info.get("company_name") or project_name
    address = contact_info.get("address") or ""
    hotline = contact_info.get("hotline") or ""
    email = contact_info.get("email") or ""
    if not row:
        return
    sid, raw_opts = row[0], row[1]
    try:
        opts = json.loads(raw_opts) if isinstance(raw_opts, str) and raw_opts.strip() else {}
    except Exception:
        opts = {}
    if not isinstance(opts, dict):
        opts = {}
    if hotline:
        opts["hotline"] = hotline
        opts["phone"] = hotline
        opts["zalo"] = re.sub(r"[^0-9]", "", hotline)
    if email:
        opts["email"] = email

    updates: list[str] = []
    params: list[Any] = []
    if "namevi" in cols and company_name:
        updates.append("`namevi` = %s")
        params.append(company_name)
    if "addressvi" in cols and address:
        updates.append("`addressvi` = %s")
        params.append(address)
    if "options" in cols:
        updates.append("`options` = %s")
        params.append(json.dumps(opts, ensure_ascii=False))
    if updates:
        params.append(sid)
        cur.execute(f"UPDATE `{tbl}` SET {', '.join(updates)} WHERE `id` = %s", params)


def _clear_nasanic_caches(target_source_dir: Path) -> None:
    cache_dir = target_source_dir / "caches"
    if cache_dir.is_dir():
        for child in cache_dir.iterdir():
            try:
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
            except Exception:
                pass


def seed_nasanic_database(
    target_source_dir: Path,
    project_name: str,
    config_summary: dict[str, Any],
    assets_dir: Path,
    seed_data: dict[str, Any],
    replace_template_data: bool = False,
) -> dict[str, Any]:
    """
    Populate Nasanic MySQL tables with design-matched data & WebP photos (`{folder}/YYYY/MM/DD/...webp`).
    Uses globally unique `slugvi` per run and commits per-type so one table error never rolls back everything.
    """
    env_cfg = _parse_laravel_env(target_source_dir / ".env")
    db_name = env_cfg.get("DB_DATABASE", "").strip()
    if not db_name:
        return {"seeded": [], "skipped_existing": [], "warnings": ["Thiếu DB_DATABASE trong .env của source"]}

    try:
        import pymysql  # type: ignore
    except ImportError:
        return {"seeded": [], "skipped_existing": [], "warnings": ["Thiếu thư viện pymysql"]}

    prefix = env_cfg.get("DB_PREFIX", "table_").strip() or "table_"
    host = env_cfg.get("DB_HOST", "localhost") or "localhost"
    port = int(env_cfg.get("DB_PORT", "3306") or 3306)
    user = env_cfg.get("DB_USERNAME", "root") or "root"
    password = env_cfg.get("DB_PASSWORD", "")

    images_pool: list[Path] = []
    if (assets_dir / "images").is_dir():
        images_pool = sorted(
            p for p in (assets_dir / "images").rglob("*")
            if p.is_file() and p.suffix.lower() in {".webp", ".png", ".jpg", ".jpeg"} and "_figma_ref" not in p.parts
        )

    contact_info: dict[str, str] = dict(seed_data.get("contact_info") or {})
    section_items_map: dict[str, list[dict[str, Any]]] = dict(seed_data.get("section_items") or {})
    product_categories: list[str] = list(seed_data.get("product_categories") or [])
    company_name = contact_info.get("company_name") or project_name

    seeded: list[dict[str, Any]] = []
    skipped_existing: list[dict[str, Any]] = []
    warnings: list[str] = []

    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=db_name,
            charset="utf8mb4",
            autocommit=False,
        )
    except Exception as exc:
        return {"seeded": [], "skipped_existing": [], "warnings": [f"Không kết nối được MySQL ({db_name}): {exc}"]}

    now_ts = int(time.time())
    now_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    used_slugs: set[str] = set()

    try:
        with conn.cursor() as cur:
            if replace_template_data:
                _wipe_template_tables(cur, prefix)
                _update_setting_table(cur, prefix, contact_info, project_name)
                conn.commit()
            elif _table_exists(cur, f"{prefix}slug"):
                cur.execute(f"SELECT `slugvi` FROM `{prefix}slug` WHERE `slugvi` IS NOT NULL")
                for r in cur.fetchall():
                    if r[0]:
                        used_slugs.add(str(r[0]))

            has_slug_table = _table_exists(cur, f"{prefix}slug")
            cfg_img_cols_by_table = _scan_config_image_columns(target_source_dir / "config", prefix)

            # Deduplicate configured types by (cfg_file, type_key) so nothing double-seeds
            seen_cfg_pairs: set[tuple[str, str]] = set()
            configured_list: list[dict[str, Any]] = []
            for raw_item in config_summary.get("configured_types") or []:
                pair = (str(raw_item.get("file") or ""), str(raw_item.get("key") or ""))
                if pair[1] and pair not in seen_cfg_pairs:
                    seen_cfg_pairs.add(pair)
                    configured_list.append(dict(raw_item))

            if replace_template_data:
                for core_static in ("footer", "copyright", "slogan", "lien-he"):
                    pair = ("config/type-static.php", core_static)
                    if pair not in seen_cfg_pairs:
                        seen_cfg_pairs.add(pair)
                        configured_list.append(
                            {"file": "config/type-static.php", "key": core_static, "category_levels": 0}
                        )
                for core_photo in ("logo", "favicon", "social"):
                    pair = ("config/type-photo.php", core_photo)
                    if pair not in seen_cfg_pairs:
                        seen_cfg_pairs.add(pair)
                        configured_list.append(
                            {"file": "config/type-photo.php", "key": core_photo, "category_levels": 0, "item_count": 3 if core_photo == "social" else 1}
                        )

            for item in configured_list:
                cfg_file = str(item.get("file") or "")
                type_key = str(item.get("key") or "")
                cat_levels = int(item.get("category_levels") or 0)
                has_inner_page = bool(item.get("has_inner_page", True))
                has_list_icon = bool(item.get("has_list_icon", False))
                has_photo2 = bool(item.get("has_photo2", False))
                opts2_schema = item.get("options2_schema") or {}
                if not type_key:
                    continue

                if cfg_file.endswith("type-products.php"):
                    base_table = f"{prefix}product"
                    upload_folder = "product"
                    controller = r"\NASANICORE\Controllers\Web\ProductController"
                    model_cls = r"\NASANICORE\Models\ProductModel"
                    com_prefix = "product"
                elif cfg_file.endswith("type-news.php"):
                    base_table = f"{prefix}news"
                    upload_folder = "news"
                    controller = r"\NASANICORE\Controllers\Web\NewsController"
                    model_cls = r"\NASANICORE\Models\NewsModel"
                    com_prefix = "news"
                elif cfg_file.endswith("type-static.php"):
                    base_table = f"{prefix}static"
                    upload_folder = "news"
                    controller = r"\NASANICORE\Controllers\Web\StaticController"
                    model_cls = r"\NASANICORE\Models\StaticModel"
                    com_prefix = "static"
                elif cfg_file.endswith("type-photo.php"):
                    base_table = f"{prefix}photo"
                    upload_folder = "photo"
                    controller = ""
                    model_cls = ""
                    com_prefix = "photo"
                else:
                    continue

                if not _table_exists(cur, base_table):
                    continue

                try:
                    cur.execute(f"SELECT COUNT(*) FROM `{base_table}` WHERE `type` = %s", (type_key,))
                    existing_count = int(cur.fetchone()[0])
                    if existing_count > 0:
                        skipped_existing.append({"table": base_table, "type": type_key, "existing": existing_count})
                        continue

                    cols = _get_table_columns(cur, base_table)
                    required_base_imgs = set(cfg_img_cols_by_table.get(base_table, set()))
                    if has_photo2:
                        required_base_imgs.add("photo2")
                    for extra_img in item.get("image_fields") or []:
                        required_base_imgs.add(str(extra_img))
                    if required_base_imgs:
                        _ensure_image_columns(cur, base_table, cols, required_base_imgs)
                    upload_dir = target_source_dir / "upload" / upload_folder
                    status_table = f"{base_table}_status"
                    has_status_pivot = _table_exists(cur, status_table)
                    status_fk = f"id_{base_table.removeprefix(prefix)}"
                    custom_items = section_items_map.get(type_key) or []

                    # Static single-record types
                    if base_table == f"{prefix}static":
                        is_system_text = type_key in {"footer", "copyright", "slogan"} or type_key.startswith("slogan")
                        img_name = _copy_seed_image(images_pool, 0, upload_dir, upload_folder, type_key) if not is_system_text else ""
                        img2_name = _copy_seed_image(images_pool, 1, upload_dir, upload_folder, type_key) if (has_photo2 and not is_system_text) else ""
                        first_custom = custom_items[0] if custom_items else {}
                        title_txt = str(first_custom.get("name") or "").strip() or (
                            company_name if type_key == "footer" else f"{type_key.replace('-', ' ').title()} — {company_name}"
                        )
                        desc_txt = str(first_custom.get("desc") or "").strip() or seed_data.get("hero", {}).get("subtitle", title_txt)
                        row: dict[str, Any] = {"type": type_key}
                        if "namevi" in cols:
                            row["namevi"] = title_txt[:190]
                        if "slugvi" in cols and type_key in {"gioi-thieu", "tuyen-dung", "lien-he"}:
                            static_slug = _make_unique_slug(type_key, used_slugs)
                            row["slugvi"] = static_slug
                        if "descvi" in cols:
                            row["descvi"] = desc_txt
                        if "contentvi" in cols:
                            if type_key == "footer":
                                addr_val = contact_info.get("address") or seed_data.get("address") or "TP. HCM"
                                hotline_val = contact_info.get("hotline") or seed_data.get("hotline") or "0909 888 666"
                                email_val = contact_info.get("email") or seed_data.get("email") or "contact@nasani.vn"
                                row["contentvi"] = (
                                    f"<p><strong>{company_name}</strong></p>"
                                    f"<p><strong>Địa chỉ:</strong> {addr_val}</p>"
                                    f"<p><strong>Hotline:</strong> {hotline_val}</p>"
                                    f"<p><strong>Email:</strong> {email_val}</p>"
                                )
                            else:
                                row["contentvi"] = f"<p>{desc_txt}</p>"
                        if "photo" in cols and img_name:
                            row["photo"] = img_name
                        if "photo2" in cols and img2_name:
                            row["photo2"] = img2_name
                        if "is_show" in cols:
                            row["is_show"] = 1
                        if "date_created" in cols:
                            row["date_created"] = now_ts
                        if "created_at" in cols:
                            row["created_at"] = now_dt
                        if "updated_at" in cols:
                            row["updated_at"] = now_dt
                        new_id = _insert_row(cur, base_table, row)
                        if has_slug_table and "slugvi" in row:
                            _insert_row(
                                cur,
                                f"{prefix}slug",
                                {
                                    "id_parent": new_id,
                                    "namevi": title_txt[:190],
                                    "slugvi": row["slugvi"],
                                    "com": type_key,
                                    "act": "save",
                                    "type": type_key,
                                    "model": model_cls,
                                    "controller": controller,
                                    "created_at": now_dt,
                                    "updated_at": now_dt,
                                },
                            )
                        conn.commit()
                        seeded.append({"table": base_table, "type": type_key, "inserted": 1})
                        continue

                    # Photo / Slideshow / Ad Banner / Logo / Social types
                    if base_table == f"{prefix}photo":
                        photo_count = 1 if type_key in {"logo", "logo-footer", "favicon", "quang-cao"} or type_key.startswith("banner") else max(1, int(item.get("item_count") or 3))
                        if type_key == "slideshow":
                            photo_count = max(photo_count, 2)
                        use_icon_pool = type_key in {"social"}
                        inserted_cnt = 0
                        for idx in range(photo_count):
                            img_name = _copy_seed_image(images_pool, idx, upload_dir, upload_folder, type_key, prefer_icon=use_icon_pool)
                            c_item = custom_items[idx] if idx < len(custom_items) else {}
                            row = {"type": type_key}
                            if "namevi" in cols:
                                row["namevi"] = str(c_item.get("name") or f"{type_key.replace('-', ' ').title()} #{idx + 1}")[:190]
                            if "photo" in cols and img_name:
                                row["photo"] = img_name
                            if "numb" in cols:
                                row["numb"] = idx + 1
                            if "com" in cols:
                                row["com"] = "photo"
                            if "act" in cols and (type_key in {"logo", "logo-footer", "favicon"} or type_key.startswith("banner")):
                                row["act"] = "photo_static"
                            if "date_created" in cols:
                                row["date_created"] = now_ts
                            if "created_at" in cols:
                                row["created_at"] = now_dt
                            if "updated_at" in cols:
                                row["updated_at"] = now_dt
                            new_id = _insert_row(cur, base_table, row)
                            if has_status_pivot and type_key not in {"logo", "logo-footer", "favicon"} and not type_key.startswith("banner"):
                                st_cols = _get_table_columns(cur, status_table)
                                if status_fk in st_cols and "status" in st_cols:
                                    _insert_row(cur, status_table, {status_fk: new_id, "status": "is_show"})
                            inserted_cnt += 1
                        conn.commit()
                        seeded.append({"table": base_table, "type": type_key, "inserted": inserted_cnt})
                        continue

                    # Product / News types: seed categories first if category_levels > 0
                    cat_ids_by_level: dict[str, list[int]] = {"list": [], "cat": [], "item": []}
                    level_names = ["list", "cat", "item"][: max(0, min(3, cat_levels))]
                    for lvl in level_names:
                        cat_table = f"{base_table}_{lvl}"
                        if not _table_exists(cur, cat_table):
                            continue
                        cat_cols = _get_table_columns(cur, cat_table)
                        required_cat_imgs = set(cfg_img_cols_by_table.get(cat_table, set()))
                        if lvl == "list" and has_list_icon:
                            required_cat_imgs.add("icon")
                        if required_cat_imgs:
                            _ensure_image_columns(cur, cat_table, cat_cols, required_cat_imgs)
                        cat_st_table = f"{cat_table}_status"
                        has_cat_st = _table_exists(cur, cat_st_table)
                        cat_st_fk = f"id_{cat_table.removeprefix(prefix)}"
                        cat_names_pool = product_categories if (base_table == f"{prefix}product" and lvl == "list" and product_categories) else []
                        c_total = len(cat_names_pool) if cat_names_pool else 2
                        for c_idx in range(c_total):
                            c_name = cat_names_pool[c_idx] if cat_names_pool else f"Danh mục {type_key.replace('-', ' ').title()} {lvl.upper()} {c_idx + 1}"
                            c_slug = _make_unique_slug(_slugify_vi(c_name), used_slugs)
                            c_row: dict[str, Any] = {"type": type_key}
                            if "namevi" in cat_cols:
                                c_row["namevi"] = c_name[:190]
                            if "slugvi" in cat_cols:
                                c_row["slugvi"] = c_slug
                            if "photo" in cat_cols:
                                cat_img = _copy_seed_image(images_pool, c_idx, upload_dir, upload_folder, type_key)
                                if cat_img:
                                    c_row["photo"] = cat_img
                            if "icon" in cat_cols and lvl == "list" and has_list_icon:
                                icon_img = _copy_seed_image(images_pool, c_idx, upload_dir, upload_folder, type_key, prefer_icon=True)
                                if icon_img:
                                    c_row["icon"] = icon_img
                            if "numb" in cat_cols:
                                c_row["numb"] = c_idx + 1
                            if "is_show" in cat_cols:
                                c_row["is_show"] = 1
                            if "is_featured" in cat_cols:
                                c_row["is_featured"] = 1
                            if lvl == "cat" and "id_list" in cat_cols and cat_ids_by_level["list"]:
                                c_row["id_list"] = cat_ids_by_level["list"][c_idx % len(cat_ids_by_level["list"])]
                            if lvl == "item":
                                if "id_cat" in cat_cols and cat_ids_by_level["cat"]:
                                    c_row["id_cat"] = cat_ids_by_level["cat"][c_idx % len(cat_ids_by_level["cat"])]
                                if "id_list" in cat_cols and cat_ids_by_level["list"]:
                                    c_row["id_list"] = cat_ids_by_level["list"][c_idx % len(cat_ids_by_level["list"])]
                            if "date_created" in cat_cols:
                                c_row["date_created"] = now_ts
                            if "created_at" in cat_cols:
                                c_row["created_at"] = now_dt
                            if "updated_at" in cat_cols:
                                c_row["updated_at"] = now_dt
                            cid = _insert_row(cur, cat_table, c_row)
                            cat_ids_by_level[lvl].append(cid)
                            if has_cat_st:
                                cst_cols = _get_table_columns(cur, cat_st_table)
                                if cat_st_fk in cst_cols and "status" in cst_cols:
                                    for st_val in ("is_show", "is_featured"):
                                        _insert_row(cur, cat_st_table, {cat_st_fk: cid, "status": st_val})
                            if has_slug_table and "slugvi" in cat_cols:
                                cat_model_suffix = {"list": "ListModel", "cat": "CatModel", "item": "ItemModel"}[lvl]
                                cat_cls_base = "Product" if base_table == f"{prefix}product" else "News"
                                _insert_row(
                                    cur,
                                    f"{prefix}slug",
                                    {
                                        "id_parent": cid,
                                        "namevi": c_name[:190],
                                        "slugvi": c_slug,
                                        "com": f"{com_prefix}-{lvl}",
                                        "act": "save",
                                        "type": type_key,
                                        "model": f"\\NASANICORE\\Models\\{cat_cls_base}{cat_model_suffix}",
                                        "controller": controller,
                                        "created_at": now_dt,
                                        "updated_at": now_dt,
                                    },
                                )

                    sample_products = seed_data.get("products") or []
                    is_icon_news = any(k in type_key for k in ("tieu-chi", "vi-sao", "tai-sao"))
                    base_cnt = 7 if "album" in type_key else (max(6, len(cat_ids_by_level["list"]) * 3) if base_table == f"{prefix}product" and cat_ids_by_level["list"] else 4)
                    item_count = max(base_cnt, min(12, len(custom_items))) if custom_items else base_cnt
                    inserted_cnt = 0
                    for idx in range(item_count):
                        c_item = custom_items[idx % len(custom_items)] if custom_items else {}
                        sample = sample_products[idx % len(sample_products)] if sample_products else {}
                        if c_item.get("name"):
                            raw_title = str(c_item["name"])[:160]
                            title_txt = raw_title if idx < len(custom_items) else f"{raw_title} ({idx + 1})"
                        elif sample.get("title") and base_table == f"{prefix}product":
                            title_txt = f"{sample.get('title')} ({idx + 1})"
                        else:
                            title_txt = f"{type_key.replace('-', ' ').title()} mẫu #{idx + 1}"
                        slug_val = _make_unique_slug(_slugify_vi(title_txt), used_slugs)
                        img_name = _copy_seed_image(images_pool, idx, upload_dir, upload_folder, type_key, prefer_icon=is_icon_news)
                        row = {"type": type_key}
                        if "namevi" in cols:
                            row["namevi"] = title_txt[:190]
                        if "slugvi" in cols and (base_table == f"{prefix}product" or has_inner_page):
                            row["slugvi"] = slug_val
                        if "descvi" in cols:
                            row["descvi"] = str(c_item.get("desc") or sample.get("desc") or f"Mô tả mẫu cho {title_txt}.")
                        if "contentvi" in cols and (base_table == f"{prefix}product" or has_inner_page):
                            row["contentvi"] = f"<p>Nội dung chi tiết cho {title_txt} — {company_name}.</p>"
                        if "photo" in cols and img_name:
                            row["photo"] = img_name
                        if "numb" in cols:
                            row["numb"] = idx + 1
                        if "options2" in cols and (c_item.get("options2") or opts2_schema):
                            opts2_payload = dict(c_item.get("options2") or {})
                            for ok in opts2_schema:
                                if ok not in opts2_payload:
                                    if ok == "statistical":
                                        opts2_payload[ok] = f"{(idx + 1) * 15}+"
                                    elif ok == "link-youtube":
                                        opts2_payload[ok] = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                                    elif ok == "address":
                                        opts2_payload[ok] = "TP. Hồ Chí Minh"
                                    else:
                                        opts2_payload[ok] = str(title_txt)
                            row["options2"] = json.dumps(opts2_payload, ensure_ascii=False)
                        if "regular_price" in cols and base_table == f"{prefix}product":
                            row["regular_price"] = 1250000 * (idx + 1)
                        if "sale_price" in cols and base_table == f"{prefix}product":
                            row["sale_price"] = 990000 * (idx + 1)
                        if "id_list" in cols and cat_ids_by_level["list"]:
                            row["id_list"] = cat_ids_by_level["list"][idx % len(cat_ids_by_level["list"])]
                        if "id_cat" in cols and cat_ids_by_level["cat"]:
                            row["id_cat"] = cat_ids_by_level["cat"][idx % len(cat_ids_by_level["cat"])]
                        if "id_item" in cols and cat_ids_by_level["item"]:
                            row["id_item"] = cat_ids_by_level["item"][idx % len(cat_ids_by_level["item"])]
                        if "date_created" in cols:
                            row["date_created"] = now_ts
                        if "created_at" in cols:
                            row["created_at"] = now_dt
                        if "updated_at" in cols:
                            row["updated_at"] = now_dt

                        new_id = _insert_row(cur, base_table, row)
                        if has_status_pivot:
                            st_cols = _get_table_columns(cur, status_table)
                            if status_fk in st_cols and "status" in st_cols:
                                statuses = ("is_show", "is_featured") if (base_table == f"{prefix}product" or has_inner_page) else ("is_show",)
                                for st_val in statuses:
                                    _insert_row(cur, status_table, {status_fk: new_id, "status": st_val})
                        if has_slug_table and "slugvi" in row:
                            _insert_row(
                                cur,
                                f"{prefix}slug",
                                {
                                    "id_parent": new_id,
                                    "namevi": title_txt[:190],
                                    "slugvi": slug_val,
                                    "com": f"{com_prefix}-detail",
                                    "act": "save",
                                    "type": type_key,
                                    "model": model_cls,
                                    "controller": controller,
                                    "created_at": now_dt,
                                    "updated_at": now_dt,
                                },
                            )
                        inserted_cnt += 1
                    conn.commit()
                    seeded.append({"table": base_table, "type": type_key, "inserted": inserted_cnt})
                except Exception as item_exc:
                    conn.rollback()
                    warnings.append(f"Lỗi khi seed `{type_key}` ({base_table}): {item_exc}")
    except Exception as exc:
        conn.rollback()
        warnings.append(f"Lỗi khi seed DB ({db_name}): {exc}")
    finally:
        conn.close()

    if replace_template_data:
        _clear_nasanic_caches(target_source_dir)

    return {"seeded": seeded, "skipped_existing": skipped_existing, "warnings": warnings}
