from __future__ import annotations

import asyncio
import io
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import httpx
from PIL import Image, ImageDraw, ImageFont

from .font_manager import resolve_and_install_fonts


def _hex_to_rgb(hex_color: str, default: tuple[int, int, int] = (37, 99, 235)) -> tuple[int, int, int]:
    cleaned = hex_color.strip().lstrip("#")
    if len(cleaned) != 6:
        return default
    try:
        return (int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))
    except ValueError:
        return default


def _build_google_fonts_css(fonts: list[str]) -> str:
    clean_fonts = [f.strip() for f in fonts if f and f.strip()] or ["Be Vietnam Pro"]
    imports: list[str] = []
    for font_name in clean_fonts[:4]:
        encoded = quote_plus(font_name)
        imports.append(
            f"@import url('https://fonts.googleapis.com/css2?family={encoded}:wght@400;500;600;700;800&display=swap');"
        )
    main_font = clean_fonts[0]
    heading_font = clean_fonts[1] if len(clean_fonts) > 1 else main_font
    return (
        "\n".join(imports)
        + "\n\n:root {\n"
        + f"  --font-main: '{main_font}', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;\n"
        + f"  --font-heading: '{heading_font}', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;\n"
        + "}\n"
    )


def _generate_webp_graphic(
    dest: Path,
    width: int,
    height: int,
    c1: tuple[int, int, int],
    c2: tuple[int, int, int],
    label: str,
) -> None:
    """Create a crisp gradient + geometric local WebP asset offline (0 tokens)."""
    img = Image.new("RGB", (width, height), c1)
    draw = ImageDraw.Draw(img)

    for y in range(height):
        t = y / max(1, height - 1)
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Subtle geometric accents
    accent = (min(255, c2[0] + 55), min(255, c2[1] + 55), min(255, c2[2] + 55))
    draw.ellipse(
        (int(width * 0.62), int(-height * 0.15), int(width * 1.1), int(height * 0.72)),
        outline=accent,
        width=6,
    )
    draw.rounded_rectangle(
        (int(width * 0.08), int(height * 0.15), int(width * 0.48), int(height * 0.78)),
        radius=20,
        outline=(255, 255, 255),
        width=3,
    )

    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    draw.text((int(width * 0.12), int(height * 0.42)), label, fill=(255, 255, 255), font=font)

    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, format="WEBP", quality=100, method=6)


def _write_svg_icons(images_dir: Path, primary_hex: str) -> list[str]:
    icons: dict[str, str] = {
        "logo-mark.svg": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" fill="none">'
            f'<rect width="40" height="40" rx="10" fill="{primary_hex}"/>'
            f'<path d="M11 26L19 12L24 20L29 14L29 26H11Z" fill="#FFFFFF"/>'
            f"</svg>"
        ),
        "icon-check.svg": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
            f'<circle cx="12" cy="12" r="10" fill="{primary_hex}" fill-opacity="0.14"/>'
            f'<path d="M7.5 12.5L10.5 15.5L16.5 9" stroke="{primary_hex}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
            f"</svg>"
        ),
        "icon-phone.svg": (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
            f'<path d="M5 4H9L11 9L8.5 10.5C9.6 12.7 11.3 14.4 13.5 15.5L15 13L20 15V19C20 20.1 19.1 21 18 21C10.8 21 3 13.2 3 6C3 4.9 3.9 4 5 4Z" stroke="{primary_hex}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
            f"</svg>"
        ),
    }
    created: list[str] = []
    for fname, svg_content in icons.items():
        target = images_dir / fname
        target.write_text(svg_content, encoding="utf-8")
        created.append(f"assets/images/{fname}")
    return created


async def _export_figma_images_to_webp(
    file_key: str,
    figma_token: str,
    export_nodes: list[dict[str, Any]],
    images_dir: Path,
) -> tuple[list[str], dict[str, dict[str, int]]]:
    if not export_nodes:
        return [], {}
    selected = export_nodes[:60]
    headers = {"X-Figma-Token": figma_token.strip()}
    dims_out: dict[str, dict[str, int]] = {}
    image_urls: dict[str, str] = {}
    svg_urls: dict[str, str] = {}
    file_image_refs: dict[str, str] = {}

    async with httpx.AsyncClient(timeout=45.0) as client:
        # 1. Fetch raw fill imageRef URLs for background/image fills so section backgrounds never capture child text/cards
        if any(str(n.get("image_ref") or "").strip() for n in selected):
            try:
                refs_resp = await client.get(
                    f"https://api.figma.com/v1/files/{file_key}/images",
                    headers=headers,
                )
                if refs_resp.status_code == 200:
                    file_image_refs = ((refs_resp.json() or {}).get("meta") or {}).get("images") or {}
            except Exception:
                file_image_refs = {}

        # 2. Export vector icons as true .svg files
        vector_nodes = [n for n in selected if n.get("kind") == "vector" and n.get("node_id")]
        for i in range(0, len(vector_nodes), 20):
            batch = vector_nodes[i : i + 20]
            node_ids = ",".join(str(n["node_id"]) for n in batch)
            meta_resp = await client.get(
                f"https://api.figma.com/v1/images/{file_key}?ids={node_ids}&format=svg",
                headers=headers,
            )
            meta_resp.raise_for_status()
            svg_urls.update((meta_resp.json() or {}).get("images") or {})

        # 3. Export raster nodes (excluding ones already satisfied by raw image_ref for section_bg)
        raster_nodes = [
            n for n in selected
            if n.get("kind") != "vector"
            and n.get("node_id")
            and not (n.get("role") == "section_bg" and n.get("image_ref") and file_image_refs.get(str(n["image_ref"])))
        ]
        for i in range(0, len(raster_nodes), 20):
            batch = raster_nodes[i : i + 20]
            node_ids = ",".join(str(n["node_id"]) for n in batch)
            if not node_ids:
                continue
            meta_resp = await client.get(
                f"https://api.figma.com/v1/images/{file_key}?ids={node_ids}&format=png&scale=2",
                headers=headers,
            )
            meta_resp.raise_for_status()
            image_urls.update((meta_resp.json() or {}).get("images") or {})

        async def download_one(idx_n: int, item: dict[str, Any]) -> str | None:
            raw_name = str(item.get("name") or "asset")
            sec_tag = str(item.get("section") or "").strip()
            role_tag = str(item.get("role") or "").strip()
            w_cfg = int(item.get("width") or 0)
            h_cfg = int(item.get("height") or 0)

            if role_tag == "section_bg":
                out_stem = f"bg-{sec_tag}-{raw_name}" if sec_tag else f"bg-{raw_name}"
            elif role_tag == "item_icon":
                prefix = f"{sec_tag}-" if sec_tag and not raw_name.startswith(sec_tag) else ""
                out_stem = f"{prefix}icon-{idx_n}-{raw_name}"
            elif sec_tag and not raw_name.startswith(sec_tag):
                out_stem = f"{sec_tag}-{raw_name}"
            else:
                out_stem = raw_name

            if item.get("kind") == "vector":
                s_url = svg_urls.get(item["node_id"])
                if not s_url:
                    return None
                r = await client.get(s_url)
                r.raise_for_status()
                dims_out[raw_name] = {"width": w_cfg or 48, "height": h_cfg or 48}
                out_name = f"{out_stem}.svg"
                (images_dir / out_name).write_bytes(r.content)
                return f"assets/images/{out_name}"

            img_ref = str(item.get("image_ref") or "").strip()
            url = (
                file_image_refs.get(img_ref)
                if (role_tag == "section_bg" and img_ref and file_image_refs.get(img_ref))
                else image_urls.get(item["node_id"])
            )
            if not url:
                return None
            r = await client.get(url)
            r.raise_for_status()
            im = Image.open(io.BytesIO(r.content)).convert("RGBA")
            w_cfg = w_cfg or im.width
            h_cfg = h_cfg or im.height
            dims_out[raw_name] = {"width": w_cfg, "height": h_cfg}
            out_name = f"{out_stem}.webp"
            out_path = images_dir / out_name
            im.save(out_path, format="WEBP", quality=100, method=6)
            return f"assets/images/{out_name}"

        results = await asyncio.gather(
            *(download_one(idx_n, item) for idx_n, item in enumerate(selected, start=1)),
            return_exceptions=True,
        )
    return [res for res in results if isinstance(res, str)], dims_out


def convert_workspace_images_to_webp(target_root: Path) -> list[str]:
    """
    Convert any `.png`/`.jpg`/`.jpeg` images downloaded into `assets/images/` (excluding `_figma_ref`)
    to `.webp` at quality=100 and update references in Blade views & CSS files.
    """
    images_dir = target_root / "assets" / "images"
    if not images_dir.is_dir():
        return []

    replacements: list[tuple[str, str]] = []
    converted: list[str] = []
    for img_path in list(images_dir.rglob("*")):
        if not img_path.is_file():
            continue
        if "_figma_ref" in img_path.parts:
            continue
        if img_path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        webp_path = img_path.with_suffix(".webp")
        try:
            with Image.open(img_path) as im:
                im.convert("RGBA").save(webp_path, format="WEBP", quality=100, method=6)
            img_path.unlink(missing_ok=True)
            rel_old = img_path.relative_to(target_root).as_posix()
            rel_new = webp_path.relative_to(target_root).as_posix()
            replacements.append((rel_old, rel_new))
            replacements.append((img_path.name, webp_path.name))
            converted.append(rel_new)
        except Exception:
            continue

    if replacements:
        scan_dirs = [target_root / "src" / "Views", target_root / "assets" / "css"]
        for sdir in scan_dirs:
            if not sdir.is_dir():
                continue
            for f in sdir.rglob("*"):
                if not f.is_file() or f.suffix.lower() not in {".php", ".css"}:
                    continue
                txt = f.read_text(encoding="utf-8", errors="ignore")
                new_txt = txt
                for old_s, new_s in replacements:
                    if old_s in new_txt:
                        new_txt = new_txt.replace(old_s, new_s)
                if new_txt != txt:
                    f.write_text(new_txt, encoding="utf-8")

    return converted


async def _export_figma_reference_pngs(
    file_key: str,
    figma_token: str,
    figma_node_id: str | None,
    sections: list[dict[str, Any]],
    ref_dir: Path,
) -> list[str]:
    """Export full-frame and major section PNGs from Figma so Vy can visually inspect the design."""
    targets: list[tuple[str, str]] = []
    if figma_node_id:
        targets.append((figma_node_id, "00-full-design.png"))
    for idx, sec in enumerate(sections[:16], start=1):
        nid = str(sec.get("node_id") or sec.get("id") or "").strip()
        if nid and nid != figma_node_id:
            sec_slug = re.sub(r"[^a-z0-9]+", "-", str(sec.get("name") or f"section-{idx}").lower()).strip("-") or f"section-{idx}"
            targets.append((nid, f"{idx:02d}-{sec_slug[:32]}.png"))
    if not targets:
        return []

    ref_dir.mkdir(parents=True, exist_ok=True)
    node_ids = ",".join(nid for nid, _ in targets)
    headers = {"X-Figma-Token": figma_token.strip()}
    async with httpx.AsyncClient(timeout=35.0) as client:
        meta_resp = await client.get(
            f"https://api.figma.com/v1/images/{file_key}?ids={node_ids}&format=png&scale=1",
            headers=headers,
        )
        meta_resp.raise_for_status()
        image_urls = (meta_resp.json() or {}).get("images") or {}

        async def download_ref(nid: str, fname: str) -> str | None:
            url = image_urls.get(nid)
            if not url:
                return None
            r = await client.get(url)
            r.raise_for_status()
            dest = ref_dir / fname
            dest.write_bytes(r.content)
            return str(dest)

        results = await asyncio.gather(
            *(download_ref(nid, fname) for nid, fname in targets),
            return_exceptions=True,
        )
    return [res for res in results if isinstance(res, str)]


async def run_asset_and_font_pipeline(
    tokens: dict[str, Any],
    output_dir: Path,
    figma_file_key: str | None = None,
    figma_token: str | None = None,
    font_source_dir: str = "",
    figma_node_id: str | None = None,
    ref_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Offline 0-token pipeline: resolves Google/local WOFF2 fonts into fonts.css,
    exports/optimizes WebP assets, and writes SVG icons into output_dir/assets/.
    """
    assets_dir = output_dir / "assets"
    css_dir = assets_dir / "css"
    images_dir = assets_dir / "images"
    css_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    fonts = tokens.get("fonts") or ["Be Vietnam Pro", "Plus Jakarta Sans"]
    font_result = await resolve_and_install_fonts(
        fonts, output_dir, font_source_dir=font_source_dir
    )

    colors = tokens.get("colors") or []
    primary_hex = colors[0]["hex"] if colors else "#1d4ed8"
    accent_hex = colors[1]["hex"] if len(colors) > 1 else "#0f766e"
    c1 = _hex_to_rgb(primary_hex, (29, 78, 216))
    c2 = _hex_to_rgb(accent_hex, (15, 118, 110))

    exported_images: list[str] = []
    exported_dims: dict[str, dict[str, int]] = dict(tokens.get("image_dimensions") or {})
    source_mode = "offline_pillow_webp"
    if figma_token and figma_file_key and tokens.get("export_nodes"):
        try:
            exported_images, figma_dims = await _export_figma_images_to_webp(
                figma_file_key,
                figma_token,
                tokens["export_nodes"],
                images_dir,
            )
            if exported_images:
                source_mode = "figma_api_to_webp"
                exported_dims.update(figma_dims)
        except Exception:
            exported_images = []

    if not exported_images:
        specs = [
            ("hero-banner.webp", 960, 580, c1, c2, "HERO SHOWCASE"),
            ("product-1.webp", 640, 440, c1, (30, 41, 59), "SAN PHAM 01"),
            ("product-2.webp", 640, 440, c2, (15, 23, 42), "SAN PHAM 02"),
            ("product-3.webp", 640, 440, (51, 65, 85), c1, "SAN PHAM 03"),
            ("about-showcase.webp", 780, 500, (15, 23, 42), c2, "VE CHUNG TOI"),
        ]
        for fname, w, h, col1, col2, label in specs:
            _generate_webp_graphic(images_dir / fname, w, h, col1, col2, label)
            exported_images.append(f"assets/images/{fname}")

    svg_icons = _write_svg_icons(images_dir, primary_hex)
    figma_svgs = [p for p in exported_images if p.endswith(".svg")]
    raster_images = [p for p in exported_images if not p.endswith(".svg")]

    reference_images: list[str] = []
    if figma_token and figma_file_key and ref_dir is not None:
        try:
            reference_images = await _export_figma_reference_pngs(
                figma_file_key,
                figma_token,
                figma_node_id,
                list(tokens.get("sections") or []),
                ref_dir,
            )
        except Exception:
            reference_images = []

    return {
        "mode": source_mode,
        "fonts": fonts,
        "fonts_css": "assets/css/fonts.css",
        "installed_fonts": font_result.get("installed_fonts", []),
        "missing_fonts": font_result.get("missing_fonts", []),
        "images": raster_images,
        "icons": [*figma_svgs, *svg_icons],
        "dimensions": exported_dims,
        "reference_images": reference_images,
    }
