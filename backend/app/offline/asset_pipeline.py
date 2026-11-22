from __future__ import annotations

import asyncio
import io
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import httpx
from PIL import Image, ImageDraw, ImageFont


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
    img.save(dest, format="WEBP", quality=86, method=4)


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
    export_nodes: list[dict[str, str]],
    images_dir: Path,
) -> list[str]:
    if not export_nodes:
        return []
    node_ids = ",".join(n["node_id"] for n in export_nodes[:10])
    headers = {"X-Figma-Token": figma_token.strip()}
    async with httpx.AsyncClient(timeout=30.0) as client:
        meta_resp = await client.get(
            f"https://api.figma.com/v1/images/{file_key}?ids={node_ids}&format=png&scale=2",
            headers=headers,
        )
        meta_resp.raise_for_status()
        image_urls = (meta_resp.json() or {}).get("images") or {}

        async def download_one(item: dict[str, str]) -> str | None:
            url = image_urls.get(item["node_id"])
            if not url:
                return None
            r = await client.get(url)
            r.raise_for_status()
            im = Image.open(io.BytesIO(r.content)).convert("RGBA")
            out_name = f"{item['name']}.webp"
            out_path = images_dir / out_name
            im.save(out_path, format="WEBP", quality=85)
            return f"assets/images/{out_name}"

        results = await asyncio.gather(
            *(download_one(item) for item in export_nodes[:10]),
            return_exceptions=True,
        )
    return [res for res in results if isinstance(res, str)]


async def run_asset_and_font_pipeline(
    tokens: dict[str, Any],
    output_dir: Path,
    figma_file_key: str | None = None,
    figma_token: str | None = None,
) -> dict[str, Any]:
    """
    Offline 0-token pipeline: generates fonts.css, exports/optimizes WebP assets,
    and writes SVG icons into output_dir/assets/.
    """
    assets_dir = output_dir / "assets"
    css_dir = assets_dir / "css"
    images_dir = assets_dir / "images"
    css_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    fonts = tokens.get("fonts") or ["Be Vietnam Pro", "Plus Jakarta Sans"]
    fonts_css_path = css_dir / "fonts.css"
    fonts_css_path.write_text(_build_google_fonts_css(fonts), encoding="utf-8")

    colors = tokens.get("colors") or []
    primary_hex = colors[0]["hex"] if colors else "#1d4ed8"
    accent_hex = colors[1]["hex"] if len(colors) > 1 else "#0f766e"
    c1 = _hex_to_rgb(primary_hex, (29, 78, 216))
    c2 = _hex_to_rgb(accent_hex, (15, 118, 110))

    exported_images: list[str] = []
    source_mode = "offline_pillow_webp"
    if figma_token and figma_file_key and tokens.get("export_nodes"):
        try:
            exported_images = await _export_figma_images_to_webp(
                figma_file_key,
                figma_token,
                tokens["export_nodes"],
                images_dir,
            )
            if exported_images:
                source_mode = "figma_api_to_webp"
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

    return {
        "mode": source_mode,
        "fonts": fonts,
        "fonts_css": "assets/css/fonts.css",
        "images": exported_images,
        "icons": svg_icons,
    }
