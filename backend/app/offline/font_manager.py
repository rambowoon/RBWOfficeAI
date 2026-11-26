from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import httpx


def _norm_font_key(text: str) -> str:
    text = (text or "").replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]", "", stripped.lower())


def _slug_folder(text: str) -> str:
    text = (text or "").replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", stripped.strip()).strip("-") or "font"


def _parse_weight_and_style(filename: str) -> tuple[int, str]:
    low = filename.lower()
    style = "italic" if "italic" in low or re.search(r"[-_](?:it|i)$", low) else "normal"
    weight = 400
    weight_map = [
        (("thin", "hairline"), 100),
        (("extralight", "ultralight"), 200),
        (("light",), 300),
        (("regular", "normal", "book"), 400),
        (("medium",), 500),
        (("semibold", "demibold"), 600),
        (("extrabold", "ultrabold"), 800),
        (("bold",), 700),
        (("black", "heavy"), 900),
    ]
    for keys, val in weight_map:
        if any(k in low for k in keys):
            weight = val
            break
    else:
        m = re.search(r"\b([1-9]00)\b", low)
        if m:
            weight = int(m.group(1))
    return weight, style


async def _try_resolve_google_font_import(family: str) -> dict[str, Any] | None:
    """Check Google Fonts availability and return a clean @import url(...) line (no file download)."""
    encoded = quote_plus(family.strip())
    candidate_urls = [
        f"https://fonts.googleapis.com/css2?family={encoded}:ital,wght@0,100..900;1,100..900&display=swap",
        f"https://fonts.googleapis.com/css2?family={encoded}:wght@400;500;600;700&display=swap",
        f"https://fonts.googleapis.com/css2?family={encoded}&display=swap",
    ]
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            for url in candidate_urls:
                resp = await client.get(url, headers=headers)
                if resp.status_code < 400 and "@font-face" in resp.text:
                    return {
                        "family": family,
                        "source": "google_import",
                        "files": [],
                        "css": f'@import url("{url}");',
                    }
    except Exception:
        return None
    return None


def _convert_to_woff2(src_path: Path, dest_woff2: Path) -> bool:
    """Convert .ttf/.otf to .woff2 using fontTools (0-token offline)."""
    try:
        from fontTools.ttLib import TTFont  # type: ignore

        font = TTFont(str(src_path))
        font.flavor = "woff2"
        dest_woff2.parent.mkdir(parents=True, exist_ok=True)
        font.save(str(dest_woff2))
        font.close()
        return True
    except Exception:
        return False


def _scan_and_install_local_font(
    family: str,
    font_source_dir: Path,
    fonts_root: Path,
) -> dict[str, Any] | None:
    """
    Scan `font_source_dir` (e.g. E:\\Font) for `family`.
    Only outputs .woff/.woff2 into `fonts_root/<slug>/`; converts .ttf/.otf -> .woff2 if needed.
    """
    if not font_source_dir.exists() or not font_source_dir.is_dir():
        return None

    target_key = _norm_font_key(family)
    if not target_key:
        return None

    matched_files: list[Path] = []
    # Check matching subdirectories first (fast)
    for entry in font_source_dir.iterdir():
        if entry.is_dir() and target_key in _norm_font_key(entry.name):
            for f in entry.rglob("*"):
                if f.is_file() and f.suffix.lower() in {".woff2", ".woff", ".ttf", ".otf"}:
                    matched_files.append(f)

    # Fallback: scan top-level / nested filenames if directory name didn't match
    if not matched_files:
        for f in font_source_dir.rglob("*"):
            if f.is_file() and f.suffix.lower() in {".woff2", ".woff", ".ttf", ".otf"}:
                if target_key in _norm_font_key(f.stem):
                    matched_files.append(f)
            if len(matched_files) >= 16:
                break

    if not matched_files:
        return None

    # Group by (weight, style) and prefer woff2 > woff > ttf/otf (convert to woff2)
    by_variant: dict[tuple[int, str], dict[str, Path]] = {}
    for f in matched_files:
        w, st = _parse_weight_and_style(f.stem)
        ext = f.suffix.lower().lstrip(".")
        by_variant.setdefault((w, st), {})[ext] = f

    folder_name = _slug_folder(family)
    dest_dir = fonts_root / folder_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    css_blocks: list[str] = []
    files_created: list[str] = []
    converted_count = 0

    for (w, st), ext_map in sorted(by_variant.items()):
        out_files: list[tuple[str, str]] = []
        base_name = f"{folder_name}-{w}{'i' if st == 'italic' else ''}"

        if "woff2" in ext_map:
            dst = dest_dir / f"{base_name}.woff2"
            shutil.copy2(ext_map["woff2"], dst)
            out_files.append((dst.name, "woff2"))
            files_created.append(f"assets/fonts/{folder_name}/{dst.name}")
        if "woff" in ext_map:
            dst = dest_dir / f"{base_name}.woff"
            shutil.copy2(ext_map["woff"], dst)
            out_files.append((dst.name, "woff"))
            files_created.append(f"assets/fonts/{folder_name}/{dst.name}")

        if not out_files:
            raw_src = ext_map.get("ttf") or ext_map.get("otf")
            if raw_src:
                dst = dest_dir / f"{base_name}.woff2"
                if _convert_to_woff2(raw_src, dst):
                    converted_count += 1
                    out_files.append((dst.name, "woff2"))
                    files_created.append(f"assets/fonts/{folder_name}/{dst.name}")

        if out_files:
            src_parts = ", ".join(
                f"url('../fonts/{folder_name}/{fname}') format('{fmt}')"
                for fname, fmt in out_files
            )
            css_blocks.append(
                f"@font-face {{\n"
                f"  font-family: '{family}';\n"
                f"  font-style: {st};\n"
                f"  font-weight: {w};\n"
                f"  font-display: swap;\n"
                f"  src: {src_parts};\n"
                f"}}"
            )

    if not css_blocks:
        return None

    return {
        "family": family,
        "source": "local_converted_woff2" if converted_count else "local_woff",
        "converted_count": converted_count,
        "files": files_created,
        "css": "\n".join(css_blocks),
    }


async def resolve_and_install_fonts(
    fonts: list[str],
    output_dir: Path,
    font_source_dir: str = "",
) -> dict[str, Any]:
    """
    Resolve fonts in order:
      1. Google Fonts (download .woff2/.woff locally)
      2. Local `font_source_dir` (e.g. E:\\Font), keeping only .woff/.woff2 (converting .ttf/.otf -> .woff2)
      3. Report any unresolved fonts in `missing_fonts` for manual addition.
    """
    clean_fonts = [f.strip() for f in fonts if f and f.strip()] or ["Be Vietnam Pro"]
    fonts_root = output_dir / "assets" / "fonts"
    css_dir = output_dir / "assets" / "css"
    fonts_root.mkdir(parents=True, exist_ok=True)
    css_dir.mkdir(parents=True, exist_ok=True)

    source_dir_path = Path(font_source_dir) if font_source_dir else None

    installed: list[dict[str, Any]] = []
    missing_fonts: list[str] = []
    css_chunks: list[str] = []

    for family in clean_fonts[:4]:
        res = await _try_resolve_google_font_import(family)
        if not res and source_dir_path:
            res = _scan_and_install_local_font(family, source_dir_path, fonts_root)

        if res:
            installed.append(
                {
                    "family": family,
                    "source": res["source"],
                    "files": res["files"],
                }
            )
            css_chunks.append(res["css"])
        else:
            missing_fonts.append(family)
            css_chunks.append(
                f"/* Font '{family}' chưa tìm thấy trên Google Fonts hoặc {font_source_dir or 'local'} — vui lòng thêm file .woff/.woff2 thủ công */"
            )

    main_font = clean_fonts[0]
    heading_font = clean_fonts[1] if len(clean_fonts) > 1 else main_font
    (css_dir / "fonts.css").write_text(
        "\n\n".join(css_chunks) + "\n",
        encoding="utf-8",
    )

    return {
        "fonts_css": "assets/css/fonts.css",
        "installed_fonts": installed,
        "missing_fonts": missing_fonts,
        "main_font": main_font,
        "heading_font": heading_font,
    }


def upsert_root_fonts_in_style_css(
    style_css_path: Path,
    main_font: str,
    heading_font: str = "",
    primary_color: str = "",
) -> None:
    """Write or update `:root { --color-main; --font-main; }` in `assets/css/style.css`."""
    src = style_css_path.read_text(encoding="utf-8", errors="ignore") if style_css_path.is_file() else ""
    color_val = (primary_color or "").strip()
    if not color_val and src:
        m_col = re.search(r"--color-main\s*:\s*([^;}\n]+)", src)
        if m_col:
            color_val = m_col.group(1).strip()
    lines = [":root {\n"]
    if color_val:
        lines.append(f"  --color-main: {color_val};\n")
    lines.append(f"  --font-main: '{main_font}', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;\n")
    lines.append("}\n")
    vars_block = "".join(lines)
    if not style_css_path.is_file():
        style_css_path.parent.mkdir(parents=True, exist_ok=True)
        style_css_path.write_text(vars_block, encoding="utf-8")
        return
    if re.search(r":root\s*\{[^}]*(?:--font-main|--color-main)\s*:", src):
        src = re.sub(
            r":root\s*\{[^}]*(?:--font-main|--color-main)\s*:[^}]*\}\r?\n?",
            vars_block,
            src,
            count=1,
        )
    else:
        src = vars_block + "\n" + src
    style_css_path.write_text(src, encoding="utf-8")

