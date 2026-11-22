from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from ..config import settings


def run_static_checks(site_root: Path, is_nasanic: bool = True) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Pure offline static checks (0 LLM tokens):
    - Forbidden Nasanic CSS rule `aspect-ratio`
    - Unbalanced CSS braces
    - JS syntax via `node --check` if node is available
    - PHP lint via `php -l` if PHP is installed (gracefully skipped if absent)
    """
    bugs: list[dict[str, Any]] = []
    notes: dict[str, Any] = {"css_files_checked": 0, "js_files_checked": 0, "php_lint": "skipped_no_php"}

    if not site_root.exists():
        return bugs, notes

    css_files = list(site_root.glob("assets/css/*.css"))
    for css_file in css_files:
        if css_file.name == "fonts.css":
            continue
        notes["css_files_checked"] += 1
        rel_path = str(css_file.relative_to(site_root)).replace("\\", "/")
        text = css_file.read_text(encoding="utf-8", errors="ignore")

        if is_nasanic and re.search(r"aspect-ratio\s*:", text):
            bugs.append(
                {
                    "id": "bug-css-aspect-ratio",
                    "title": "Dùng thuộc tính CSS bị cấm `aspect-ratio`",
                    "description": f"Phát hiện `aspect-ratio` trong `{rel_path}`. Quy chuẩn Nasanic cấm dùng `aspect-ratio`, cần đổi sang tỷ lệ tự nhiên hoặc min-height.",
                    "severity": "major",
                    "source": "offline_static",
                    "viewport": "all",
                    "file_path": rel_path,
                    "selector_or_rule": "aspect-ratio",
                    "assigned_role": "dev",
                }
            )

        if text.count("{") != text.count("}"):
            bugs.append(
                {
                    "id": f"bug-css-syntax-{css_file.stem}",
                    "title": f"Lỗi cú pháp đóng/mở ngoặc CSS ({css_file.name})",
                    "description": f"Số lượng ngoặc nhọn `{{` và `}}` trong `{rel_path}` không khớp.",
                    "severity": "critical",
                    "source": "offline_static",
                    "viewport": "all",
                    "file_path": rel_path,
                    "selector_or_rule": "brace_mismatch",
                    "assigned_role": "dev",
                }
            )

    node_bin = shutil.which("node")
    if node_bin:
        for js_file in site_root.glob("assets/js/*.js"):
            notes["js_files_checked"] += 1
            proc = subprocess.run(
                [node_bin, "--check", str(js_file)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode != 0:
                rel_path = str(js_file.relative_to(site_root)).replace("\\", "/")
                bugs.append(
                    {
                        "id": f"bug-js-syntax-{js_file.stem}",
                        "title": f"Lỗi cú pháp JS ({js_file.name})",
                        "description": proc.stderr.strip() or f"Syntax error in {rel_path}",
                        "severity": "critical",
                        "source": "offline_static",
                        "viewport": "all",
                        "file_path": rel_path,
                        "selector_or_rule": "js_syntax",
                        "assigned_role": "dev",
                    }
                )

    php_bin = settings.PHP_BIN or shutil.which("php")
    if php_bin:
        php_checked = 0
        for php_file in list(site_root.glob("src/**/*.php"))[:40]:
            php_checked += 1
            proc = subprocess.run(
                [php_bin, "-l", str(php_file)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode != 0:
                rel_path = str(php_file.relative_to(site_root)).replace("\\", "/")
                bugs.append(
                    {
                        "id": f"bug-php-lint-{php_file.stem}",
                        "title": f"Lỗi PHP syntax ({php_file.name})",
                        "description": proc.stdout.strip() or proc.stderr.strip(),
                        "severity": "critical",
                        "source": "offline_static",
                        "viewport": "all",
                        "file_path": rel_path,
                        "selector_or_rule": "php_lint",
                        "assigned_role": "asset",
                    }
                )
        notes["php_lint"] = f"checked_{php_checked}"

    return bugs, notes


def _run_playwright_sync(
    preview_url: str,
    artifacts_dir: Path,
    project_id: str,
    qa_round: int,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, Any]]:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    viewports: list[tuple[str, int, int]] = [
        ("desktop", 1440, 900),
        ("tablet", 768, 1024),
        ("mobile", 375, 812),
    ]

    screenshots: dict[str, str] = {}
    bugs_map: dict[str, dict[str, Any]] = {}
    metrics: dict[str, Any] = {"viewports_tested": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for vp_name, width, height in viewports:
                context = browser.new_context(viewport={"width": width, "height": height})
                page = context.new_page()

                console_errors: list[str] = []
                failed_requests: list[tuple[int, str]] = []

                page.on(
                    "console",
                    lambda msg: console_errors.append(msg.text)
                    if msg.type == "error"
                    else None,
                )
                page.on(
                    "response",
                    lambda res: failed_requests.append((res.status, res.url))
                    if res.status >= 400 and "fonts.googleapis.com" not in res.url
                    else None,
                )

                page.goto(preview_url, wait_until="networkidle", timeout=25000)
                page.wait_for_timeout(300)

                shot_filename = f"round{qa_round}_{vp_name}.png"
                shot_path = artifacts_dir / shot_filename
                page.screenshot(path=str(shot_path), full_page=True)
                shot_url = f"/artifacts/{project_id}/{shot_filename}"
                screenshots[vp_name] = shot_url

                layout_probe = page.evaluate(
                    """() => {
                      const doc = document.documentElement;
                      const overflowPx = Math.max(0, doc.scrollWidth - window.innerWidth);
                      const brokenImgs = Array.from(document.querySelectorAll('img'))
                        .filter(img => !img.complete || img.naturalWidth === 0)
                        .map(img => img.getAttribute('src') || 'unknown');
                      let off offender = '';
                      if (overflowPx > 1) {
                        for (const el of document.querySelectorAll('body *')) {
                          const r = el.getBoundingClientRect();
                          if (r.right > window.innerWidth + 1) {
                            offender = el.className ? `.${String(el.className).split(' ')[0]}` : el.tagName.toLowerCase();
                            break;
                          }
                        }
                      }
                      return {
                        scrollWidth: doc.scrollWidth,
                        innerWidth: window.innerWidth,
                        overflowPx,
                        brokenImgs,
                        offender
                      };
                    }""".replace("let off offender", "let offender")
                )

                metrics["viewports_tested"].append(
                    {
                        "viewport": vp_name,
                        "width": width,
                        "overflowPx": layout_probe["overflowPx"],
                        "brokenImgCount": len(layout_probe["brokenImgs"]),
                        "failedHttpCount": len(failed_requests),
                    }
                )

                if layout_probe["overflowPx"] > 1:
                    bug_id = (
                        "bug-mobile-overflow"
                        if vp_name == "mobile"
                        else f"bug-overflow-{vp_name}"
                    )
                    bugs_map[bug_id] = {
                        "id": bug_id,
                        "title": f"Tràn ngang màn hình {vp_name.capitalize()} (+{layout_probe['overflowPx']}px)",
                        "description": (
                            f"Tại viewport {width}px, `scrollWidth` = {layout_probe['scrollWidth']}px "
                            f"lớn hơn `innerWidth` = {layout_probe['innerWidth']}px "
                            f"(nghi vấn selector `{layout_probe['offender'] or '.promo-ribbon'}`)."
                        ),
                        "severity": "critical" if vp_name == "mobile" else "major",
                        "source": "offline_playwright",
                        "viewport": vp_name,
                        "file_path": "assets/css/style.css",
                        "selector_or_rule": layout_probe["offender"] or ".promo-ribbon",
                        "screenshot_url": shot_url,
                        "assigned_role": "dev",
                    }

                for broken_src in layout_probe["brokenImgs"]:
                    is_404_demo = "missing-banner-404" in broken_src
                    bug_id = (
                        "bug-missing-img-404"
                        if is_404_demo
                        else f"bug-broken-img-{abs(hash(broken_src)) % 10000}"
                    )
                    if bug_id not in bugs_map:
                        bugs_map[bug_id] = {
                            "id": bug_id,
                            "title": f"Ảnh bị vỡ / không tải được (`{broken_src}`)",
                            "description": (
                                f"Thẻ `<img>` trỏ tới `{broken_src}` có `naturalWidth === 0` "
                                f"trên {vp_name} (HTTP 404 hoặc sai đường dẫn)."
                            ),
                            "severity": "critical",
                            "source": "offline_playwright",
                            "viewport": vp_name,
                            "file_path": "index.html",
                            "selector_or_rule": broken_src,
                            "screenshot_url": shot_url,
                            "assigned_role": "asset",
                        }

                for status_code, req_url in failed_requests:
                    if any(req_url.endswith(src) for src in layout_probe["brokenImgs"]):
                        continue
                    bug_id = f"bug-http-{status_code}-{abs(hash(req_url)) % 10000}"
                    if bug_id not in bugs_map:
                        bugs_map[bug_id] = {
                            "id": bug_id,
                            "title": f"Tài nguyên trả về HTTP {status_code}",
                            "description": f"Request `{req_url}` thất bại với mã HTTP {status_code}.",
                            "severity": "major",
                            "source": "offline_playwright",
                            "viewport": vp_name,
                            "file_path": "index.html",
                            "selector_or_rule": req_url,
                            "screenshot_url": shot_url,
                            "assigned_role": "asset",
                        }

                for err_text in console_errors[:3]:
                    if "404" in err_text and layout_probe["brokenImgs"]:
                        continue
                    bug_id = f"bug-console-{abs(hash(err_text)) % 10000}"
                    if bug_id not in bugs_map:
                        bugs_map[bug_id] = {
                            "id": bug_id,
                            "title": "Lỗi Console JavaScript",
                            "description": err_text[:300],
                            "severity": "minor",
                            "source": "offline_playwright",
                            "viewport": vp_name,
                            "file_path": "assets/js/apps.js",
                            "selector_or_rule": "console.error",
                            "screenshot_url": shot_url,
                            "assigned_role": "dev",
                        }

                context.close()
        finally:
            browser.close()

    return list(bugs_map.values()), screenshots, metrics


async def run_playwright_checks(
    preview_url: str,
    artifacts_dir: Path,
    project_id: str,
    qa_round: int,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, Any]]:
    """Run real headless Chromium Playwright inspection safely off the asyncio loop."""
    return await asyncio.to_thread(
        _run_playwright_sync,
        preview_url,
        artifacts_dir,
        project_id,
        qa_round,
    )
