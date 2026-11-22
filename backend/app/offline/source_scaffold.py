from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from ..models import BugItem


def inspect_workspace_context(target_source_dir: str) -> dict[str, Any]:
    """
    Inspect target project folder for Nasanic structure and existing .agents rules/skills
    without modifying any files inside it.
    """
    root = Path(target_source_dir) if target_source_dir else Path(".")
    exists = root.exists() and root.is_dir()
    is_nasanic = False
    agents_md = ""
    skills_summary: list[str] = []

    if exists:
        has_index = (root / "index.php").exists()
        has_src = (root / "src").exists()
        has_style = (root / "assets" / "css" / "style.css").exists()
        is_nasanic = has_index and has_src and has_style

        agents_file = root / ".agents" / "AGENTS.md"
        if agents_file.exists():
            agents_md = agents_file.read_text(encoding="utf-8", errors="ignore")[:3500]

        skills_dir = root / ".agents" / "skills"
        if skills_dir.exists():
            for skill_md in skills_dir.glob("*/SKILL.md"):
                content = skill_md.read_text(encoding="utf-8", errors="ignore")[:4000]
                skills_summary.append(f"### Skill: {skill_md.parent.name}\n{content}")

    return {
        "exists": exists,
        "target_source_dir": str(root),
        "framework": "nasanic" if is_nasanic else "generic",
        "agents_rules": agents_md,
        "skills_rules": "\n\n".join(skills_summary),
    }


def generate_demo_seed_data(
    project_name: str, spec_text: str, tokens: dict[str, Any]
) -> dict[str, Any]:
    """Generate structured Vietnamese sample data tailored to the spec."""
    raw_lines = [ln.strip() for ln in spec_text.splitlines() if ln.strip()]
    body_lines = [
        ln.lstrip("#-* \t")
        for ln in raw_lines
        if not ln.startswith("#") and ln.lstrip("#-* \t")
    ]
    cleaned_lines = body_lines or [ln.lstrip("#-* \t") for ln in raw_lines if ln.lstrip("#-* \t")]
    tagline = (
        cleaned_lines[0][:120]
        if cleaned_lines
        else f"Giải pháp thiết kế & vận hành chuyên nghiệp từ {project_name}"
    )

    return {
        "brand_name": project_name,
        "hotline": "0909 888 666",
        "email": "contact@nasanic-demo.vn",
        "address": "128 Nguyễn Thị Minh Khai, Quận 3, TP. HCM",
        "hero": {
            "badge": "Chuẩn hóa thiết kế từ Figma",
            "title": f"{project_name} — Giải pháp toàn diện & đồng bộ",
            "subtitle": tagline,
            "cta_primary": "Nhận tư vấn ngay",
            "cta_secondary": "Xem danh mục nổi bật",
        },
        "products": [
            {
                "id": "sp-01",
                "title": "Gói Thiết Kế Tiêu Chuẩn",
                "category": "Nổi bật",
                "price": "12.500.000đ",
                "desc": "Tối ưu bố cục chuẩn desktop & mobile, tối ưu tốc độ tải trang và hình ảnh WebP.",
                "image": "assets/images/product-1.webp",
            },
            {
                "id": "sp-02",
                "title": "Gói Triển Khai Chuyên Sâu",
                "category": "Phổ biến",
                "price": "24.000.000đ",
                "desc": "Tích hợp đa ngôn ngữ, tối ưu SEO kỹ thuật, form liên hệ bảo mật & dữ liệu động.",
                "image": "assets/images/product-2.webp",
            },
            {
                "id": "sp-03",
                "title": "Gói Doanh Nghiệp Toàn Diện",
                "category": "Cao cấp",
                "price": "38.000.000đ",
                "desc": "Hệ thống giao diện đồng nhất từ Design Tokens Figma kèm kiểm thử Playwright đa thiết bị.",
                "image": "assets/images/product-3.webp",
            },
        ],
        "highlights": [
            "Đồng bộ màu sắc & typography trực tiếp từ Figma Design Tokens",
            "Hình ảnh nén chuẩn WebP, tải nhanh trên thiết bị di động",
            "Kiểm thử tự động Desktop 1440px, Tablet 768px và Mobile 375px",
        ],
    }


def build_demo_preview_site(
    project_dir: Path,
    project_name: str,
    spec_text: str,
    tokens: dict[str, Any],
    assets_manifest: dict[str, Any],
    seed_data: dict[str, Any],
    inject_round1_bugs: bool = True,
) -> Path:
    """
    Build a complete multi-section Vietnamese preview website inside project_dir/preview_site/.
    When inject_round1_bugs=True, plants 3 realistic bugs for offline static + Playwright QA to catch.
    """
    preview_dir = project_dir / "preview_site"
    (preview_dir / "assets" / "css").mkdir(parents=True, exist_ok=True)
    (preview_dir / "assets" / "js").mkdir(parents=True, exist_ok=True)
    (preview_dir / "data").mkdir(parents=True, exist_ok=True)

    colors = tokens.get("colors") or []
    primary = colors[0]["hex"] if colors else "#1d4ed8"
    accent = colors[1]["hex"] if len(colors) > 1 else "#d97706"

    images = assets_manifest.get("images") or ["assets/images/hero-banner.webp"]
    hero_img = next((i for i in images if "hero" in i), images[0])
    about_img = next((i for i in images if "about" in i), images[-1])

    products = seed_data.get("products", [])
    # Plant Bug 3 (missing 404 image) on 3rd card when Round 1 bugs enabled
    card3_img = (
        "assets/images/missing-banner-404.webp"
        if inject_round1_bugs
        else products[2]["image"] if len(products) > 2 else hero_img
    )

    aspect_ratio_block = (
        "  /* BUG-DEMO: forbidden Nasanic CSS rule */\n  aspect-ratio: 16 / 9;\n"
        if inject_round1_bugs
        else "  min-height: 280px;\n"
    )

    overflow_rule = (
        "  /* BUG-DEMO: wide min-width overflows mobile 375px */\n  min-width: 520px;\n"
        if inject_round1_bugs
        else "  width: 100%;\n  flex-wrap: wrap;\n"
    )

    style_css = f"""@import url('./fonts.css');

:root {{
  --primary: {primary};
  --accent: {accent};
  --ink: #0f172a;
  --muted: #475569;
  --surface: #f8fafc;
  --border: #e2e8f0;
}}

* {{
  box-sizing: border-box;
}}

html, body {{
  margin: 0;
  padding: 0;
  font-family: var(--font-main);
  color: var(--ink);
  background: #ffffff;
  line-height: 1.6;
}}

img {{
  max-width: 100%;
  height: auto;
  display: block;
}}

.container {{
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}}

.site-header {{
  position: sticky;
  top: 0;
  z-index: 30;
  background: rgba(255, 255, 255, 0.94);
  border-bottom: 1px solid var(--border);
  backdrop-filter: blur(8px);
}}

.header-inner {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  height: 76px;
}}

.brand {{
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-heading);
  font-weight: 800;
  font-size: 18px;
  color: var(--ink);
  text-decoration: none;
}}

.nav-links {{
  display: flex;
  align-items: center;
  gap: 24px;
}}

.nav-links a {{
  text-decoration: none;
  color: var(--muted);
  font-weight: 500;
  font-size: 15px;
}}

.nav-links a:hover {{
  color: var(--primary);
}}

.btn-primary {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--primary);
  color: #ffffff;
  border: 0;
  border-radius: 10px;
  padding: 12px 22px;
  font-weight: 600;
  font-size: 15px;
  cursor: pointer;
  text-decoration: none;
}}

.btn-outline {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: var(--primary);
  border: 1px solid var(--primary);
  border-radius: 10px;
  padding: 11px 20px;
  font-weight: 600;
  font-size: 15px;
  cursor: pointer;
  text-decoration: none;
}}

.hero-section {{
  padding: 64px 0;
  background: linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%);
}}

.hero-grid {{
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 40px;
  align-items: center;
}}

.hero-badge {{
  display: inline-block;
  padding: 6px 14px;
  border-radius: 999px;
  background: rgba(29, 78, 216, 0.1);
  color: var(--primary);
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 14px;
}}

.hero-title {{
  font-family: var(--font-heading);
  font-size: 40px;
  line-height: 1.2;
  margin: 0 0 16px;
}}

.hero-subtitle {{
  font-size: 17px;
  color: var(--muted);
  margin: 0 0 26px;
}}

.hero-actions {{
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}}

.hero-media-frame {{
  border-radius: 18px;
  box-shadow: 0 20px 40px rgba(15, 23, 42, 0.12);
{aspect_ratio_block}}}

.hero-media-frame img {{
  border-radius: 18px;
  width: 100%;
}}

.promo-ribbon {{
  margin-top: 24px;
  background: #0f172a;
  color: #f8fafc;
  border-radius: 12px;
  padding: 12px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
{overflow_rule}}}

.section-block {{
  padding: 64px 0;
}}

.section-heading {{
  text-align: center;
  max-width: 680px;
  margin: 0 auto 40px;
}}

.section-heading h2 {{
  font-family: var(--font-heading);
  font-size: 30px;
  margin: 0 0 10px;
}}

.section-heading p {{
  color: var(--muted);
  margin: 0;
}}

.product-grid {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
}}

.product-card {{
  border: 1px solid var(--border);
  border-radius: 16px;
  background: #ffffff;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}}

.product-card-body {{
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}}

.product-cat {{
  font-size: 12px;
  font-weight: 700;
  color: var(--accent);
  text-transform: uppercase;
}}

.product-price {{
  font-weight: 700;
  color: var(--primary);
  font-size: 18px;
  margin-top: auto;
}}

.about-section {{
  background: var(--surface);
  padding: 64px 0;
}}

.about-grid {{
  display: grid;
  grid-template-columns: 0.95fr 1.05fr;
  gap: 40px;
  align-items: center;
}}

.check-list {{
  list-style: none;
  padding: 0;
  margin: 20px 0 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}}

.check-list li {{
  display: flex;
  align-items: center;
  gap: 10px;
}}

.site-footer {{
  background: #0f172a;
  color: #cbd5e1;
  padding: 48px 0;
}}

.footer-grid {{
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr;
  gap: 32px;
}}

.contact-form {{
  display: flex;
  flex-direction: column;
  gap: 10px;
}}

.contact-form input {{
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid #334155;
  background: #1e293b;
  color: #ffffff;
}}
"""

    media_css = """@media (max-width: 992px) {
  .hero-grid,
  .about-grid,
  .footer-grid {
    grid-template-columns: 1fr;
  }

  .product-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .nav-links {
    display: none;
  }

  .hero-title {
    font-size: 28px;
  }

  .product-grid {
    grid-template-columns: 1fr;
  }
}
"""

    apps_js = """document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('#quick-contact-form');
  const statusEl = document.querySelector('#contact-status');
  if (form && statusEl) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      statusEl.textContent = 'Đã ghi nhận thông tin liên hệ mẫu!';
    });
  }
});
"""

    cards_html = []
    for idx, p in enumerate(products[:3]):
        img_src = card3_img if idx == 2 else p.get("image", hero_img)
        cards_html.append(
            f"""        <article class="product-card">
          <img src="{html.escape(img_src)}" alt="{html.escape(p['title'])}">
          <div class="product-card-body">
            <span class="product-cat">{html.escape(p['category'])}</span>
            <h3>{html.escape(p['title'])}</h3>
            <p>{html.escape(p['desc'])}</p>
            <div class="product-price">{html.escape(p['price'])}</div>
          </div>
        </article>"""
        )

    highlights_html = "\n".join(
        f'          <li><img src="assets/images/icon-check.svg" width="20" height="20" alt="Check"><span>{html.escape(item)}</span></li>'
        for item in seed_data.get("highlights", [])
    )

    index_html = f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(project_name)}</title>
  <link rel="stylesheet" href="assets/css/style.css">
  <link rel="stylesheet" href="assets/css/media.css">
</head>
<body>
  <header class="site-header">
    <div class="container header-inner">
      <a class="brand" href="#top">
        <img src="assets/images/logo-mark.svg" width="34" height="34" alt="{html.escape(project_name)}">
        <span>{html.escape(project_name)}</span>
      </a>
      <nav class="nav-links">
        <a href="#products">Sản phẩm & Dịch vụ</a>
        <a href="#about">Giới thiệu</a>
        <a href="#contact">Liên hệ</a>
      </nav>
      <a class="btn-primary" href="#contact">{html.escape(seed_data['hotline'])}</a>
    </div>
  </header>

  <main id="top">
    <section class="hero-section">
      <div class="container">
        <div class="hero-grid">
          <div>
            <span class="hero-badge">{html.escape(seed_data['hero']['badge'])}</span>
            <h1 class="hero-title">{html.escape(seed_data['hero']['title'])}</h1>
            <p class="hero-subtitle">{html.escape(seed_data['hero']['subtitle'])}</p>
            <div class="hero-actions">
              <a class="btn-primary" href="#contact">{html.escape(seed_data['hero']['cta_primary'])}</a>
              <a class="btn-outline" href="#products">{html.escape(seed_data['hero']['cta_secondary'])}</a>
            </div>
            <div class="promo-ribbon">
              <span>Ưu đãi triển khai đồng bộ Figma → Web hoàn thiện</span>
              <strong>Hotline: {html.escape(seed_data['hotline'])}</strong>
            </div>
          </div>
          <div class="hero-media-frame">
            <img src="{html.escape(hero_img)}" alt="Hero showcase">
          </div>
        </div>
      </div>
    </section>

    <section id="products" class="section-block">
      <div class="container">
        <div class="section-heading">
          <h2>Danh mục nổi bật</h2>
          <p>Dữ liệu mẫu được sinh tự động khớp với đặc tả dự án và bộ ảnh WebP từ Asset Pipeline.</p>
        </div>
        <div class="product-grid">
{chr(10).join(cards_html)}
        </div>
      </div>
    </section>

    <section id="about" class="about-section">
      <div class="container about-grid">
        <div>
          <img src="{html.escape(about_img)}" alt="Về chúng tôi" style="border-radius:16px;">
        </div>
        <div>
          <h2>Quy chuẩn thiết kế & kỹ thuật</h2>
          <p>Mỗi section đều được chuẩn hóa theo bộ Design Tokens và kiểm thử đa thiết bị trước khi nghiệm thu.</p>
          <ul class="check-list">
{highlights_html}
          </ul>
        </div>
      </div>
    </section>
  </main>

  <footer id="contact" class="site-footer">
    <div class="container footer-grid">
      <div>
        <h3>{html.escape(project_name)}</h3>
        <p>{html.escape(seed_data['address'])}</p>
        <p>Email: {html.escape(seed_data['email'])}</p>
      </div>
      <div>
        <h4>Liên kết nhanh</h4>
        <p><a href="#products" style="color:#94a3b8;text-decoration:none;">Sản phẩm</a></p>
        <p><a href="#about" style="color:#94a3b8;text-decoration:none;">Về chúng tôi</a></p>
      </div>
      <div>
        <h4>Đăng ký tư vấn</h4>
        <form id="quick-contact-form" class="contact-form">
          <input type="text" name="fullname" placeholder="Họ và tên" required>
          <input type="tel" name="phone" placeholder="Số điện thoại" required>
          <button type="submit" class="btn-primary">Gửi yêu cầu</button>
          <small id="contact-status" style="color:#38bdf8;"></small>
        </form>
      </div>
    </div>
  </footer>

  <script src="assets/js/apps.js"></script>
</body>
</html>
"""

    (preview_dir / "assets" / "css" / "style.css").write_text(style_css, encoding="utf-8")
    (preview_dir / "assets" / "css" / "media.css").write_text(media_css, encoding="utf-8")
    (preview_dir / "assets" / "js" / "apps.js").write_text(apps_js, encoding="utf-8")
    (preview_dir / "data" / "seed.json").write_text(
        json.dumps(seed_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (preview_dir / "index.html").write_text(index_html, encoding="utf-8")
    return preview_dir


def apply_demo_bug_fixes(preview_dir: Path, approved_bugs: list[BugItem]) -> list[str]:
    """
    Selectively fix ONLY the bugs approved by the user on the Bug Board.
    Leaves ignored bugs untouched so re-testing accurately reflects user choices.
    """
    modified_files: list[str] = []
    style_path = preview_dir / "assets" / "css" / "style.css"
    index_path = preview_dir / "index.html"

    for bug in approved_bugs:
        key = f"{bug.id} {bug.selector_or_rule} {bug.title}".lower()

        if "aspect-ratio" in key or bug.id == "bug-css-aspect-ratio":
            if style_path.exists():
                css_text = style_path.read_text(encoding="utf-8")
                updated = re.sub(
                    r"\s*/\*\s*BUG-DEMO:.*?\*/\s*aspect-ratio:\s*[^;]+;",
                    "\n  min-height: 280px;",
                    css_text,
                )
                updated = re.sub(r"\s*aspect-ratio:\s*[^;]+;", "\n  min-height: 280px;", updated)
                if updated != css_text:
                    style_path.write_text(updated, encoding="utf-8")
                    if "assets/css/style.css" not in modified_files:
                        modified_files.append("assets/css/style.css")

        if "overflow" in key or "min-width" in key or bug.id == "bug-mobile-overflow":
            if style_path.exists():
                css_text = style_path.read_text(encoding="utf-8")
                updated = re.sub(
                    r"\s*/\*\s*BUG-DEMO:.*?\*/\s*min-width:\s*520px;",
                    "\n  width: 100%;\n  flex-wrap: wrap;",
                    css_text,
                )
                updated = re.sub(r"\s*min-width:\s*520px;", "\n  width: 100%;\n  flex-wrap: wrap;", updated)
                if updated != css_text:
                    style_path.write_text(updated, encoding="utf-8")
                    if "assets/css/style.css" not in modified_files:
                        modified_files.append("assets/css/style.css")

        if "404" in key or "missing-banner-404" in key or "broken-img" in key:
            if index_path.exists():
                html_text = index_path.read_text(encoding="utf-8")
                updated = html_text.replace(
                    "assets/images/missing-banner-404.webp",
                    "assets/images/product-3.webp",
                )
                if updated != html_text:
                    index_path.write_text(updated, encoding="utf-8")
                    if "index.html" not in modified_files:
                        modified_files.append("index.html")

    return modified_files
