from __future__ import annotations

import io
import json
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from typing import Any

from .figma_parser import is_junk_section_name


def parse_docx_bytes(data: bytes) -> str:
    """Extract paragraphs and tables from a .docx file using pure stdlib (0-token offline)."""
    lines: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        if "word/document.xml" not in zf.namelist():
            raise ValueError("File .docx không hợp lệ (thiếu word/document.xml)")
        xml_bytes = zf.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    body = root.find("w:body", ns)
    if body is None:
        return ""

    for child in body:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            texts = [t.text for t in child.findall(".//w:t", ns) if t.text]
            para = "".join(texts).strip()
            if para:
                lines.append(para)
        elif tag == "tbl":
            for row in child.findall(".//w:tr", ns):
                cells: list[str] = []
                for cell in row.findall("./w:tc", ns):
                    para_texts: list[str] = []
                    for p in cell.findall(".//w:p", ns):
                        p_str = "".join(t.text for t in p.findall(".//w:t", ns) if t.text).strip()
                        if p_str:
                            para_texts.append(p_str)
                    if not para_texts:
                        c_texts = [t.text for t in cell.findall(".//w:t", ns) if t.text]
                        joined = " ".join("".join(c_texts).split())
                    else:
                        joined = " / ".join(" ".join(p.split()) for p in para_texts)
                    cells.append(joined)
                if any(cells):
                    lines.append(" | ".join(cells))
    return "\n".join(lines).strip()


def _col_index_from_ref(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha())
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch.upper()) - ord("A") + 1)
    return max(0, idx - 1)


def parse_xlsx_bytes(data: bytes) -> str:
    """Extract sheets and rows from a .xlsx Excel file using pure stdlib (0-token offline)."""
    sections: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in names:
            ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in ss_root:
                t_parts = [el.text or "" for el in si.iter() if el.tag.endswith("}t") or el.tag == "t"]
                shared_strings.append("".join(t_parts))

        sheet_files = sorted(
            n for n in names if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")
        )
        if not sheet_files:
            raise ValueError("File .xlsx không hợp lệ (không tìm thấy worksheet)")

        for idx, sheet_path in enumerate(sheet_files, start=1):
            s_root = ET.fromstring(zf.read(sheet_path))
            rows_out: list[str] = []
            for row in s_root.iter():
                if not (row.tag.endswith("}row") or row.tag == "row"):
                    continue
                row_vals: dict[int, str] = {}
                max_col = -1
                for cell in row:
                    if not (cell.tag.endswith("}c") or cell.tag == "c"):
                        continue
                    ref = cell.attrib.get("r", "")
                    col_idx = _col_index_from_ref(ref) if ref else (max_col + 1)
                    max_col = max(max_col, col_idx)
                    c_type = cell.attrib.get("t", "")
                    val_text = ""
                    for child in cell:
                        ctag = child.tag.rsplit("}", 1)[-1]
                        if ctag == "v" and child.text is not None:
                            if c_type == "s":
                                s_idx = int(child.text)
                                val_text = shared_strings[s_idx] if s_idx < len(shared_strings) else ""
                            else:
                                val_text = child.text
                        elif ctag == "is":
                            t_parts = [el.text or "" for el in child.iter() if el.tag.rsplit("}", 1)[-1] == "t"]
                            val_text = "".join(t_parts)
                    row_vals[col_idx] = " ".join(val_text.split())

                if max_col >= 0:
                    ordered = [row_vals.get(c, "") for c in range(max_col + 1)]
                    if any(ordered):
                        rows_out.append(" | ".join(ordered))

            if rows_out:
                sections.append(f"## Sheet {idx}\n" + "\n".join(rows_out))

    return "\n\n".join(sections).strip()


def _format_xls_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)
    text = str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""
    parts = [" ".join(line.split()) for line in text.split("\n")]
    parts = [p for p in parts if p]
    return " / ".join(parts)


def parse_xls_bytes(data: bytes) -> str:
    """Extract sheets and rows from a legacy .xls (BIFF8) Excel file using xlrd."""
    try:
        import xlrd  # type: ignore
    except ImportError as exc:
        raise ValueError("Thiếu thư viện xlrd để đọc file .xls") from exc

    try:
        wb = xlrd.open_workbook(file_contents=data)
    except Exception as exc:
        raise ValueError(f"File .xls không hợp lệ: {exc}") from exc

    sections: list[str] = []
    for sh in wb.sheets():
        rows_out: list[str] = []
        for r in range(sh.nrows):
            row_vals = [_format_xls_cell(sh.cell_value(r, c)) for c in range(sh.ncols)]
            while row_vals and row_vals[-1] == "":
                row_vals.pop()
            if any(row_vals):
                rows_out.append(" | ".join(row_vals))
        if rows_out:
            sections.append(f"## {sh.name}\n" + "\n".join(rows_out))
    return "\n\n".join(sections).strip()


def parse_spec_upload(filename: str, data: bytes) -> str:
    lower = (filename or "").lower()
    if lower.endswith(".docx"):
        return parse_docx_bytes(data)
    if lower.endswith(".xlsx"):
        return parse_xlsx_bytes(data)
    if lower.endswith(".xls"):
        return parse_xls_bytes(data)
    if lower.endswith((".txt", ".md", ".csv", ".json")):
        return data.decode("utf-8", errors="ignore").strip()
    raise ValueError("Chỉ hỗ trợ file .docx (Word), .xls / .xlsx (Excel), .txt, .md, .csv")


def _normalize_vn(text: str) -> str:
    text = (text or "").replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return " ".join(stripped.lower().split())


def classify_spec_item(name: str, description: str) -> dict[str, Any]:
    """Classify a spec section into content type, category depth, cardinality, and behavior tags."""
    norm_name = _normalize_vn(name)
    norm_desc = _normalize_vn(description)
    combined = f"{norm_name} {norm_desc}".strip()

    category_levels = 0
    if re.search(r"\b(?:3\s*cap|cap\s*3|ba\s*cap)\b", combined):
        category_levels = 3
    elif re.search(r"\b(?:2\s*cap|cap\s*2|hai\s*cap)\b", combined):
        category_levels = 2
    elif re.search(r"\b(?:1\s*cap|cap\s*1|mot\s*cap)\b", combined):
        category_levels = 1

    content_type = "feature"
    item_cardinality = "none"

    if re.search(r"\b(?:qc|quang\s*cao|quangcao|banner)\b", norm_name):
        content_type = "layout"
        item_cardinality = "multiple"
    elif any(k in norm_name for k in ("header", "hero", "slide", "slider", "footer", "trang chu")):
        content_type = "layout"
        item_cardinality = "none"
    elif any(k in norm_name for k in ("tieu chi", "vi sao", "tai sao")):
        content_type = "feature"
        item_cardinality = "multiple"
    elif any(k in norm_name for k in ("y kien", "cam nhan", "khach hang")):
        content_type = "article_list"
        item_cardinality = "multiple"
    elif any(k in norm_name for k in ("gioi thieu", "ve chung toi", "tuyen dung")) or norm_name.startswith("ve "):
        content_type = "article_single"
        item_cardinality = "single"
    elif re.search(r"\b(?:1|mot)\s+bai\s+viet\b|\bbai\s+viet\s+don\b", combined):
        content_type = "article_single"
        item_cardinality = "single"
    elif (
        re.search(r"\bnhieu\s+(?:bai|bia)\s+viet\b", combined)
        or any(k in combined for k in ("tin tuc", "blog", "uu dai", "dao tao", "cam on"))
    ):
        content_type = "article_list"
        item_cardinality = "multiple"
    elif any(k in norm_name for k in ("san pham", "menu", "bang gia", "goi dich vu", "mon an")):
        content_type = "product"
        item_cardinality = "multiple"
    elif "dich vu" in norm_name:
        if "bai viet" in combined:
            content_type = "article_list"
        else:
            content_type = "product"
        item_cardinality = "multiple"
    elif any(k in combined for k in ("album", "thu vien", "nhieu hinh", "nhieu anh")):
        content_type = "album"
        item_cardinality = "multiple"
    elif any(k in combined for k in ("video", "mp4", "youtube")):
        content_type = "video"
        item_cardinality = "multiple"
    elif any(k in combined for k in ("san pham", "menu", "bang gia", "goi dich vu", "mon an", "gio hang")):
        content_type = "product"
        item_cardinality = "multiple"
    elif "dich vu" in combined:
        if "bai viet" in combined:
            content_type = "article_list"
        else:
            content_type = "product"
        item_cardinality = "multiple"
    elif any(k in combined for k in ("form", "from ", "dat lich", "lien he", "tu van", "dang ky")):
        content_type = "form"
        item_cardinality = "none"
    elif "bai viet" in combined:
        content_type = "article_list"
        item_cardinality = "multiple"

    behavior_tags: list[str] = []
    if re.search(r"\b(?:khong|ko|k)\s+hien\s+gia\b", combined):
        behavior_tags.append("Không hiện giá")
    elif (
        re.search(r"(?:^|[,;\s\-])gia(?:\s*(?:ban|san pham|dich vu|goi))?(?:$|[,;\s.])", combined)
        and "bang gia" not in combined
    ):
        behavior_tags.append("Có hiển thị giá")

    if "dong dau" in combined or "watermark" in combined:
        behavior_tags.append("Đóng dấu logo")
    if any(k in combined for k in ("chay ngang", "slider", "slide", "carousel")):
        behavior_tags.append("Chạy ngang / Slider")
    if "popup" in combined:
        behavior_tags.append("Hiển thị Popup")
    if re.search(r"\b(?:nhap\s*1\s*(?:anh|hinh)|thay\s*doi\s*1\s*(?:anh|hinh))\b", combined):
        behavior_tags.append("Nhập 1 ảnh")
    if "chay theo trang" in combined or "sticky" in combined or "co dinh" in combined:
        behavior_tags.append("Menu cố định khi cuộn")

    refs = re.findall(r"(?:[a-z0-9-]+\.)+(?:com|vn|net|org)\b", (description or "").lower())
    for domain in dict.fromkeys(refs):
        if "nasanivietnam" not in domain and "nasani.vn" not in domain:
            behavior_tags.append(f"Tham khảo: {domain}")

    return {
        "content_type": content_type,
        "category_levels": category_levels,
        "item_cardinality": item_cardinality,
        "behavior_tags": behavior_tags,
    }


_METADATA_KEYS = {
    "ten hop dong": "contract_name",
    "link demo": "demo_url",
    "chuc nang": "package_features",
    "loai website": "package_features",
    "loai web": "package_features",
}

_NOISE_PREFIXES = (
    "cong ty",
    "dia chi",
    "dt:",
    "website :",
    "email:",
    "bang mo ta chi tiet",
    "(bang mo ta nay",
    "thong tin hop dong",
    "thong tin lien he",
    "thong tin quan ly",
    "trang web tuong tu",
    "du lieu chuyen het",
    "nvpt",
    "ten nvkd",
    "nv design",
    "mail - sdt",
    "mail – sdt",
    "mail ql - sdt",
    "mail kd",
    "mail ql",
    "mail tkv",
    "email - sdt",
    "email ql",
    "email pgd",
    "mail pgd",
    "mail - pgd",
    "quan ly",
    "ten quan ly",
    "ten ql",
    "ten tkv",
    "ten pgd",
    "tkv",
    "y kien xac nhan",
    "cam on! than",
    "trang website tham khao",
)

_MENU_KEYWORDS = {
    "trang chu",
    "gioi thieu",
    "ve chung toi",
    "san pham",
    "menu",
    "dich vu",
    "bang gia",
    "tin tuc",
    "blog",
    "bai viet",
    "album",
    "thu vien",
    "hinh anh",
    "video",
    "dao tao",
    "uu dai",
    "khuyen mai",
    "du an",
    "cong trinh",
    "tuyen dung",
    "khach hang",
    "doi tac",
    "lien he",
    "dat lich",
}


def _parse_menu_definition_text(text: str) -> list[tuple[str, str]]:
    """
    Parse inline menu definition cells such as:
    'Trang chủ : chuyển về trang chủ Giới thiệu: Một bài viết Sản phẩm: 2 cấp ...'
    """
    cleaned = re.sub(r"\s*:\s*", ": ", (text or "").strip())
    words = cleaned.split()
    if len(words) < 4:
        return []

    anchors: list[tuple[int, int, str]] = []
    for i, w in enumerate(words):
        if not w.endswith(":"):
            continue
        matched_span: tuple[int, int, str] | None = None
        for span_len in (3, 2, 1):
            start = i - span_len + 1
            if start < 0:
                continue
            raw_phrase = " ".join(words[start : i + 1]).rstrip(":").strip()
            norm_phrase = _normalize_vn(raw_phrase)
            if norm_phrase in _MENU_KEYWORDS:
                matched_span = (start, i + 1, raw_phrase)
                break
        if matched_span:
            anchors.append(matched_span)

    if len(anchors) < 3:
        return []

    parsed: list[tuple[str, str]] = []
    for idx, (start, end, title) in enumerate(anchors):
        next_start = anchors[idx + 1][0] if idx + 1 < len(anchors) else len(words)
        desc = " ".join(words[end:next_start]).strip(" /,-")
        parsed.append((title, desc))
    return parsed

_GLOBAL_ROW_NAMES = (
    "note",
    "ghi chu them",
    "thong ke truy cap",
    "lien ket mang xa hoi",
    "hotline",
)


def _clean_subsection_title(chunk: str, fallback_idx: int) -> str:
    norm = _normalize_vn(chunk)
    if norm.startswith("trang chu"):
        return "Slide Trang chủ"
    # Match section title on diacritic-stripped text while preserving original Vietnamese words
    orig_words = chunk.strip().split()
    norm_words = [_normalize_vn(w.strip(",.:;")) for w in orig_words]
    start = 1 if norm_words and norm_words[0] == "phan" else 0
    stop_markers = {"dang", "nhu", "cho", "the", "hien", "bam", "va", "duoc"}
    picked: list[str] = []
    for i in range(start, min(len(orig_words), start + 6)):
        w_orig = orig_words[i].strip(",.:;")
        w_norm = norm_words[i]
        if not w_orig:
            break
        if w_norm in stop_markers:
            if w_norm == "the" and i + 1 < len(norm_words) and norm_words[i + 1] == "hien":
                break
            if w_norm in {"dang", "nhu", "cho", "hien", "bam"}:
                break
        picked.append(w_orig)
        if orig_words[i].endswith((":", ".", ",")):
            break
    candidate = " ".join(picked).strip(" -:,.")
    if 2 <= len(candidate) <= 36:
        return candidate.title() if candidate.isupper() else candidate
    prefix = chunk.split(":", 1)[0].strip()
    if 2 <= len(prefix) <= 36:
        return prefix.title() if prefix.isupper() else prefix
    return f"Mục giao diện {fallback_idx}"


def _split_composite_subsections(desc: str) -> list[tuple[str, str]]:
    """Split cells like '1. trang chủ: ... / 2. PHẦN GIỚI THIỆU ...' into separate items."""
    parts = re.split(r"(?:^|\s*/\s*|\n)\s*(\d+)\.\s+", desc.strip())
    if len(parts) < 7:
        return []
    result: list[tuple[str, str]] = []
    # parts looks like [preamble, '1', chunk1, '2', chunk2, ...]
    for i in range(1, len(parts) - 1, 2):
        idx_str = parts[i]
        body = parts[i + 1].strip(" /")
        if not body:
            continue
        title = _clean_subsection_title(body, int(idx_str))
        result.append((title, body))
    return result


def parse_structured_spec(spec_text: str) -> dict[str, Any]:
    """
    Parse Nasani .xls / .docx / markdown specification text into:
      - metadata (contract_name, demo_url, package_features)
      - items (per-section requirements with content_type & category_levels)
      - global_features (SEO, watermark, social, notes, coding requirements)
    """
    metadata: dict[str, str] = {}
    items: list[dict[str, Any]] = []
    global_features: list[str] = []

    current_scope = "homepage"
    in_global_section = False
    has_table_rows = False

    def add_global(text: str) -> None:
        for seg in re.split(r"\s*/\s*|\n", text):
            cleaned = seg.strip(" -•\t")
            if not cleaned or set(cleaned) <= {".", "…", " "}:
                continue
            if cleaned not in global_features:
                global_features.append(cleaned)

    def add_item(name: str, desc: str, scope: str, extra_notes: str = "") -> None:
        cls = classify_spec_item(name, desc)
        tags = list(cls["behavior_tags"])
        if extra_notes:
            tags.append(extra_notes)
        items.append(
            {
                "name": name.strip(),
                "scope": scope,
                "content_type": cls["content_type"],
                "category_levels": cls["category_levels"],
                "item_cardinality": cls["item_cardinality"],
                "spec_requirements": desc.strip(),
                "notes": " · ".join(dict.fromkeys(tags)),
            }
        )

    for raw_line in (spec_text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("## "):
            continue
        if set(line) <= {".", "…", " ", "-"}:
            continue

        norm_line = _normalize_vn(line)

        if "yeu cau lap trinh" in norm_line:
            in_global_section = True
            if "|" in line:
                for cell in line.split("|"):
                    c_clean = cell.strip()
                    if c_clean and "yeu cau lap trinh" not in _normalize_vn(c_clean):
                        add_global(c_clean)
            continue
        if "y kien xac nhan" in norm_line:
            in_global_section = False
            continue

        if in_global_section:
            if "|" in line:
                for cell in line.split("|"):
                    c_clean = cell.strip()
                    if c_clean:
                        add_global(c_clean)
            else:
                add_global(line)
            continue

        if "|" in line:
            has_table_rows = True
            cells = [c.strip() for c in line.split("|")]
            non_empty = [c for c in cells if c]
            if not non_empty:
                continue

            first_norm = _normalize_vn(non_empty[0]).rstrip(":")
            if first_norm in _METADATA_KEYS:
                val = " ".join(non_empty[1:]).strip()
                if first_norm == "ten hop dong" and len(non_empty) >= 2:
                    val = non_empty[1]
                metadata[_METADATA_KEYS[first_norm]] = val
                continue

            joined_norm = _normalize_vn(" ".join(non_empty))
            if any(joined_norm.startswith(p) or first_norm.startswith(p) for p in _NOISE_PREFIXES):
                continue
            if "stt" in first_norm and "ten chuc nang" in joined_norm:
                continue
            if first_norm in ("i. giao dien", "giao dien"):
                current_scope = "homepage"
                in_global_section = False
                continue
            if first_norm == "trang trong":
                current_scope = "inner_page"
                in_global_section = False
                continue

            # Distinguish STT + Name + Desc while preserving empty middle cells like `2 | | Trang chủ ... | OK`
            # and empty STT slots like `| | 1. Fanpage ... | OK`, plus `| 4 | MENU ...` and `7 | 8 | MENU ...`.
            first_ne_idx = next((idx for idx, c in enumerate(cells) if c), -1)
            if first_ne_idx >= 0 and re.fullmatch(r"\d+(?:\.\d+)?", cells[first_ne_idx]):
                after_stt_idx = first_ne_idx + 1
                if after_stt_idx < len(cells) and cells[after_stt_idx] and re.fullmatch(r"\d+(?:\.\d+)?", cells[after_stt_idx]):
                    after_stt_idx += 1
                tail = cells[after_stt_idx:]
                sec_name = tail[0] if len(tail) > 0 else ""
                sec_desc = tail[1] if len(tail) > 1 else ""
                fb_list = [c for c in tail[2:] if c and _normalize_vn(c) not in {"ok", "f"}]
            elif len(cells) >= 3 and not cells[0] and not cells[1]:
                # Continuation row without STT, e.g. ` | | 1. Fanpage và Zalo | OK`
                rem = [c for c in cells[2:] if c]
                sec_name = ""
                sec_desc = rem[0] if len(rem) > 0 else ""
                fb_list = [c for c in rem[1:] if c and _normalize_vn(c) not in {"ok", "f"}]
            else:
                sec_name = cells[0]
                sec_desc = cells[1] if len(cells) > 1 else ""
                fb_list = [c for c in cells[2:] if c and _normalize_vn(c) not in {"ok", "f"}]
            feedback = " / ".join(fb_list)

            if not sec_name and not sec_desc:
                continue

            norm_sec = _normalize_vn(sec_name).rstrip(":")
            if any(norm_sec.startswith(p) for p in _NOISE_PREFIXES):
                continue

            # Rows like "TREN DIEN THOAI" or "BANNER CHO MENU" -> global instruction
            if norm_sec == "tren dien thoai":
                if sec_desc:
                    add_global(f"Mobile: {sec_desc}")
                continue
            if "banner cho menu" in norm_sec:
                add_global(f"Banner cho menu: {sec_desc}".strip())
                continue

            # Rows like "MENU GIỚI THIỆU", "MENU SẢN PHẨM", "MENU DỊCH VỤ", ...
            if re.match(r"^menu\s+", norm_sec) and len(norm_sec) > 5:
                clean_menu_name = re.sub(r"^menu\s+", "", sec_name.strip(), flags=re.IGNORECASE).strip()
                clean_menu_name = clean_menu_name.title() if clean_menu_name.isupper() else clean_menu_name
                add_item(clean_menu_name, sec_desc, "menu", feedback)
                norm_desc_low = _normalize_vn(sec_desc)
                # If spec says "... ra ngoài trang chủ" AND does NOT say "không cần lấy dữ liệu...", link homepage too
                if (
                    ("ra ngoai trang chu" in norm_desc_low or "ngoai trang chu" in norm_desc_low)
                    and "khong can lay du lieu" not in norm_desc_low
                ):
                    add_item(clean_menu_name, sec_desc, "homepage", feedback)
                continue

            # Rows like "Cho nhiều Hiệu ứng trình bày. | | Lưu ý: TỐI ƯU HÓA..."
            if norm_sec.startswith("cho nhieu hieu ung") or norm_sec == "luu y":
                add_global(f"{sec_name} {sec_desc}".strip())
                continue

            if norm_sec in _GLOBAL_ROW_NAMES or any(norm_sec.startswith(g) for g in _GLOBAL_ROW_NAMES):
                if sec_desc:
                    add_global(f"{sec_name}: {sec_desc}" if norm_sec not in ("note", "ghi chu them") else sec_desc)
                continue

            if not sec_desc and not feedback:
                continue

            if not sec_name:
                menu_pairs = _parse_menu_definition_text(sec_desc)
                if menu_pairs:
                    for m_title, m_desc in menu_pairs:
                        if _normalize_vn(m_title) == "trang chu" and "trang chu" in _normalize_vn(m_desc):
                            continue
                        add_item(m_title, m_desc, "menu", feedback)
                    continue
                if sec_desc.lstrip().startswith("-"):
                    add_global(sec_desc)
                    continue
                if items:
                    prev = items[-1]
                    prev["spec_requirements"] = f"{prev['spec_requirements']} / {sec_desc}".strip(" /")
                    cls_merged = classify_spec_item(prev["name"], prev["spec_requirements"])
                    if cls_merged["behavior_tags"]:
                        prev["notes"] = " · ".join(
                            dict.fromkeys(
                                ([prev["notes"]] if prev["notes"] else []) + cls_merged["behavior_tags"]
                            )
                        )
                    continue

            if "giao dien chinh" in norm_sec:
                sub_items = _split_composite_subsections(sec_desc)
                if sub_items:
                    for sub_title, sub_body in sub_items:
                        if "con lai nhu demo" in _normalize_vn(sub_body):
                            add_global(sub_body)
                        else:
                            add_item(sub_title, sub_body, "homepage", feedback)
                    continue

            add_item(sec_name or "Mục bổ sung", sec_desc, current_scope, feedback)
            continue

        # Non-table lines
        if any(norm_line.startswith(p) for p in _NOISE_PREFIXES):
            continue

    # Fallback for plain bullet/text specs (no Word/Excel tables)
    if not items and not has_table_rows:
        for raw_line in (spec_text or "").splitlines():
            cleaned = raw_line.strip().lstrip("-•*").strip()
            if not cleaned:
                continue
            parts = re.split(r"[:—–-]\s+", cleaned, maxsplit=1)
            sec_title = parts[0].strip() if len(parts[0].strip()) <= 48 else f"Yêu cầu {len(items) + 1}"
            add_item(sec_title, cleaned, "homepage")

    return {
        "metadata": metadata,
        "items": items,
        "global_features": global_features,
    }


_SYNONYM_GROUPS: list[set[str]] = [
    {"header", "navigation", "nav", "topbar", "banner", "logo"},
    {"hero", "slide", "slider", "carousel", "trang chu"},
    {"about", "gioi thieu", "ve chung toi", "uy tin", "cam ket"},
    {"product", "san pham", "nhom sp", "menu", "dich vu", "bang gia", "goi", "noi bat"},
    {"vi sao", "tieu chi", "tai sao"},
    {"y kien", "cam nhan", "goc nhin tu khach hang", "khach hang"},
    {"dao tao", "training", "khoa hoc"},
    {"album", "thu vien", "hinh anh", "gallery"},
    {"video", "clip", "mp4", "youtube"},
    {"tin tuc", "blog", "bai viet", "uu dai", "news", "cam on"},
    {"footer", "lien he", "dat lich", "tu van", "contact", "form"},
]


def _match_score(figma_name: str, spec_item: dict[str, Any]) -> int:
    f_norm = re.sub(r"[_#-]+", " ", _normalize_vn(figma_name)).strip()
    s_norm = re.sub(r"[_#-]+", " ", _normalize_vn(spec_item.get("name", ""))).strip()
    if not f_norm or not s_norm:
        return 0
    f_is_ad = bool(re.search(r"\b(?:qc|quang\s*cao|quangcao|banner)\b", f_norm))
    s_is_ad = bool(re.search(r"\b(?:qc|quang\s*cao|quangcao|banner)\b", s_norm))
    if f_is_ad != s_is_ad:
        return 0
    if f_norm == s_norm:
        return 100
    if f_norm in s_norm or s_norm in f_norm:
        return 80

    f_tokens = {t for t in re.findall(r"[a-z0-9]+", f_norm) if len(t) >= 2}
    s_tokens = {t for t in re.findall(r"[a-z0-9]+", s_norm) if len(t) >= 2}
    overlap = len(f_tokens & s_tokens)
    score = overlap * 25

    for grp in _SYNONYM_GROUPS:
        f_hit = any(kw in f_norm for kw in grp)
        s_hit = any(kw in s_norm for kw in grp)
        if f_hit and s_hit:
            # Avoid matching generic "Menu" (product catalog) with "Header Navigation" unless "menu" is explicit
            if grp is _SYNONYM_GROUPS[0] and s_norm == "menu" and "menu" not in f_norm:
                continue
            # Avoid matching Figma nav frame "Menu" with "Sản phẩm nổi bật"
            if f_norm in {"menu", "nav", "navigation", "navbar"} and "menu" not in s_norm:
                continue
            score += 40

    if spec_item.get("scope") == "homepage" and score > 0:
        score += 10
    return score


def reconcile_figma_and_spec(tokens_data: dict[str, Any], spec_text: str) -> dict[str, Any]:
    """
    Build per-section specifications focused strictly on:
      1) Menu items (scope="menu")
      2) Major Homepage sections (scope="homepage")
    Following Figma first, then reconciling against the parsed specification file.
    """
    structured = parse_structured_spec(spec_text)
    spec_items: list[dict[str, Any]] = structured["items"]
    used_indices: set[int] = set()
    sections_out: list[dict[str, Any]] = []

    def _emit_section(
        *,
        name: str,
        scope: str,
        source: str,
        figma_name: str,
        content_type: str,
        category_levels: int,
        item_cardinality: str,
        spec_requirements: str,
        notes: str,
    ) -> None:
        sections_out.append(
            {
                "id": f"sec-{len(sections_out) + 1}",
                "order": len(sections_out) + 1,
                "name": name,
                "scope": scope,
                "source": source,
                "figma_section_name": figma_name,
                "content_type": content_type,
                "category_levels": int(category_levels),
                "item_cardinality": item_cardinality,
                "spec_requirements": spec_requirements,
                "notes": notes,
            }
        )

    # ------------------------------------------------------------------
    # GROUP 1: MENU ITEMS
    # ------------------------------------------------------------------
    has_spec_menu = any(item.get("scope") == "menu" for item in spec_items)
    raw_figma_menu = tokens_data.get("menu_items") or []
    use_figma_menu = bool(
        raw_figma_menu
        and (tokens_data.get("source") == "figma_api" or has_spec_menu)
    )

    if use_figma_menu:
        for m_label in raw_figma_menu:
            m_clean = str(m_label or "").strip()
            if not m_clean or _normalize_vn(m_clean) in {"trang chu", "home"}:
                continue
            best_idx = -1
            best_score = 0
            for idx, item in enumerate(spec_items):
                if idx in used_indices:
                    continue
                if has_spec_menu and item.get("scope") != "menu":
                    continue
                sc = _match_score(m_clean, item)
                if sc > best_score:
                    best_score = sc
                    best_idx = idx
            if best_idx >= 0 and best_score >= 35:
                used_indices.add(best_idx)
                matched = spec_items[best_idx]
                _emit_section(
                    name=f"Menu: {m_clean}",
                    scope="menu",
                    source="figma_and_spec",
                    figma_name=m_clean,
                    content_type=matched.get("content_type", "layout"),
                    category_levels=matched.get("category_levels", 0),
                    item_cardinality=matched.get("item_cardinality", "none"),
                    spec_requirements=matched.get("spec_requirements", ""),
                    notes=matched.get("notes", ""),
                )
            else:
                inferred = classify_spec_item(m_clean, "")
                _emit_section(
                    name=f"Menu: {m_clean}",
                    scope="menu",
                    source="figma_only",
                    figma_name=m_clean,
                    content_type=inferred["content_type"],
                    category_levels=inferred["category_levels"],
                    item_cardinality=inferred["item_cardinality"],
                    spec_requirements="",
                    notes="Mục trên Menu Figma chưa có mô tả chi tiết trong đặc tả — cần chốt (1/nhiều bài, sản phẩm, cấp danh mục).",
                )

    for idx, item in enumerate(spec_items):
        if idx in used_indices or item.get("scope") != "menu":
            continue
        used_indices.add(idx)
        _emit_section(
            name=f"Menu: {item['name']}",
            scope="menu",
            source="spec_only",
            figma_name="",
            content_type=item.get("content_type", "feature"),
            category_levels=item.get("category_levels", 0),
            item_cardinality=item.get("item_cardinality", "none"),
            spec_requirements=item.get("spec_requirements", ""),
            notes=item.get("notes", ""),
        )

    # ------------------------------------------------------------------
    # GROUP 2: MAJOR HOMEPAGE SECTIONS (FIGMA FIRST -> SPEC)
    # ------------------------------------------------------------------
    figma_sections = tokens_data.get("sections") or []
    for sec in figma_sections:
        f_name = str(sec.get("name") or "").strip()
        if not f_name or is_junk_section_name(f_name):
            continue

        best_idx = -1
        best_score = 0
        for idx, item in enumerate(spec_items):
            if idx in used_indices:
                continue
            sc = _match_score(f_name, item)
            if sc > best_score:
                best_score = sc
                best_idx = idx

        if best_idx >= 0 and best_score >= 35:
            used_indices.add(best_idx)
            matched = spec_items[best_idx]
            display_name = (
                f"{f_name} ({matched['name']})"
                if _normalize_vn(f_name) != _normalize_vn(matched["name"])
                and _normalize_vn(matched["name"]) not in _normalize_vn(f_name)
                else f_name
            )
            _emit_section(
                name=display_name,
                scope=matched.get("scope", "homepage"),
                source="figma_and_spec",
                figma_name=f_name,
                content_type=matched.get("content_type", "layout"),
                category_levels=matched.get("category_levels", 0),
                item_cardinality=matched.get("item_cardinality", "none"),
                spec_requirements=matched.get("spec_requirements", ""),
                notes=matched.get("notes", ""),
            )
        else:
            inferred = classify_spec_item(f_name, "")
            _emit_section(
                name=f_name,
                scope="homepage",
                source="figma_only",
                figma_name=f_name,
                content_type=inferred["content_type"],
                category_levels=inferred["category_levels"],
                item_cardinality=inferred["item_cardinality"],
                spec_requirements="",
                notes=(
                    "Có trên Figma nhưng chưa thấy mô tả tương ứng trong file đặc tả — "
                    "cần chốt loại dữ liệu (sản phẩm/bài viết, 1 hay nhiều bài, cấp danh mục)."
                ),
            )

    menu_slugs_emitted = {
        _normalize_vn(s["name"].removeprefix("Menu: "))
        for s in sections_out
        if s.get("scope") == "menu"
    }
    strict_figma_homepage = tokens_data.get("source") == "figma_api" and len(figma_sections) >= 3
    for idx, item in enumerate(spec_items):
        if idx in used_indices:
            continue
        item_scope = item.get("scope", "homepage")
        item_slug = _normalize_vn(item["name"])
        # If Figma homepage sections are available, do not invent extra homepage sections
        # (like Dịch vụ / Giới thiệu) that do not appear on the Figma homepage.
        if strict_figma_homepage and item_scope == "homepage":
            continue
        if figma_sections and item_scope == "homepage" and item_slug in menu_slugs_emitted:
            continue
        _emit_section(
            name=item["name"],
            scope=item_scope,
            source="spec_only",
            figma_name="",
            content_type=item.get("content_type", "feature"),
            category_levels=item.get("category_levels", 0),
            item_cardinality=item.get("item_cardinality", "none"),
            spec_requirements=item.get("spec_requirements", ""),
            notes=item.get("notes", ""),
        )

    return {
        "spec_sections": sections_out,
        "spec_metadata": structured["metadata"],
        "spec_global_features": structured["global_features"],
    }


_CONTENT_TYPE_LABELS = {
    "product": "Sản phẩm / Dịch vụ",
    "article_single": "1 bài viết đơn",
    "article_list": "Nhiều bài viết",
    "album": "Album / Thư viện ảnh",
    "video": "Video",
    "form": "Form đặt lịch / Liên hệ",
    "layout": "Bố cục tĩnh",
    "feature": "Tính năng / Cấu hình",
}

_SCOPE_LABELS = {
    "menu": "Mục trên Menu",
    "homepage": "Mục lớn Trang chủ",
    "inner_page": "Trang trong",
    "global": "Toàn trang",
}

_SOURCE_LABELS = {
    "figma_and_spec": "Figma + Đặc tả",
    "figma_only": "Chỉ có trên Figma (cần xác nhận)",
    "spec_only": "Bổ sung từ file Đặc tả",
}


def _as_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    return dict(item)


def render_structured_plan_markdown(
    project_name: str,
    tokens_data: dict[str, Any],
    workspace_ctx: dict[str, Any],
    spec_sections: list[Any],
    spec_metadata: dict[str, str],
    spec_global_features: list[str],
) -> str:
    """Render a section-by-section Figma-first specification plan in Vietnamese Markdown."""
    stats = tokens_data.get("stats") or {}
    colors = tokens_data.get("colors") or []
    color_list = ", ".join(
        f"{c.get('name', 'Color')} ({c.get('hex', '')})" for c in colors[:6]
    ) or "#1d4ed8, #0f766e"
    fonts = ", ".join(tokens_data.get("fonts") or ["Be Vietnam Pro"])
    framework = workspace_ctx.get("framework", "generic")

    meta_lines: list[str] = []
    if spec_metadata.get("contract_name"):
        meta_lines.append(f"- Hợp đồng / Khách hàng: **{spec_metadata['contract_name']}**")
    if spec_metadata.get("demo_url"):
        meta_lines.append(f"- Link Demo tham chiếu: {spec_metadata['demo_url']}")
    if spec_metadata.get("package_features"):
        meta_lines.append(f"- Gói chức năng: {spec_metadata['package_features']}")
    meta_block = ("\n" + "\n".join(meta_lines)) if meta_lines else ""

    section_blocks: list[str] = []
    for idx, raw_sec in enumerate(spec_sections, start=1):
        sec = _as_dict(raw_sec)
        order = sec.get("order") or idx
        source_lbl = _SOURCE_LABELS.get(sec.get("source", "figma_and_spec"), "Figma + Đặc tả")
        if sec.get("figma_section_name"):
            source_lbl += f" (Frame: `{sec['figma_section_name']}`)"
        scope_lbl = _SCOPE_LABELS.get(sec.get("scope", "homepage"), "Trang chủ")
        ctype_lbl = _CONTENT_TYPE_LABELS.get(sec.get("content_type", "layout"), "Bố cục tĩnh")
        cat_lvl = int(sec.get("category_levels", 0))
        cat_lbl = f"Danh mục {cat_lvl} cấp" if cat_lvl > 0 else "Không phân cấp"
        req_txt = (sec.get("spec_requirements") or "").strip() or "_Chưa có mô tả chi tiết trong file đặc tả_"
        notes_txt = (sec.get("notes") or "").strip()

        lines = [
            f"### Mục {order}. {sec.get('name', f'Mục {order}')}",
            f"- **Nguồn đối chiếu**: {source_lbl}",
            f"- **Phạm vi**: {scope_lbl} | **Loại dữ liệu**: {ctype_lbl} | **Cấp danh mục**: {cat_lbl}",
            f"- **Yêu cầu chi tiết**: {req_txt}",
        ]
        if notes_txt:
            lines.append(f"- **Ghi chú kỹ thuật**: {notes_txt}")
        section_blocks.append("\n".join(lines))

    sections_md = "\n\n".join(section_blocks) if section_blocks else "_Chưa trích xuất được mục nào._"

    nasanic_rule = (
        "Tuân thủ CSS Nasanic (CẤM dùng `aspect-ratio`, tách rõ `fonts.css` / `style.css` / `media.css`)"
        if framework == "nasanic"
        else "Tuân thủ HTML5 semantic & Vanilla CSS sạch"
    )
    global_lines = [f"- {g}" for g in spec_global_features] + [
        f"- {nasanic_rule}",
        "- Tối ưu toàn bộ hình ảnh sang `.webp` + SVG icon sắc nét.",
        "- Responsive chuẩn 3 màn hình kiểm thử: Desktop `1440px`, Tablet `768px`, Mobile `375px` (không tràn ngang).",
    ]
    global_md = "\n".join(global_lines)

    return (
        f"# ĐẶC TẢ PHÂN TÍCH DỰ ÁN: {project_name}\n\n"
        f"## 1. Nguồn thiết kế Figma & Thông tin dự án\n"
        f"- Figma File: {tokens_data.get('file_name') or 'Demo Design System'} "
        f"(Nén {stats.get('compression_pct', 0)}% node rác: {stats.get('kept_node_count', 0)}/{stats.get('raw_node_count', 0)} nodes)\n"
        f"- Framework phát hiện: `{framework}`\n"
        f"- Bảng màu Tokens: {color_list}\n"
        f"- Typography: {fonts}{meta_block}\n\n"
        f"## 2. Đặc tả chi tiết theo từng mục (Ưu tiên Figma → đối chiếu Đặc tả)\n\n"
        f"{sections_md}\n\n"
        f"## 3. Chức năng chung & Yêu cầu kỹ thuật / SEO\n"
        f"{global_md}\n\n"
        f"## 4. Kế hoạch triển khai 3 nhân viên\n"
        f"- **Linh (`asset`)**: Cấu hình source `{framework}`, sinh `fonts.css`, nén ảnh WebP & tạo `seed.json` tiếng Việt theo đúng loại dữ liệu/cấp danh mục từng mục.\n"
        f"- **Vy (`dev`)**: Code HTML/Blade, Vanilla CSS, JS & responsive theo đúng từng mục đặc tả đã duyệt.\n"
        f"- **Tuấn (`qa`)**: Chạy Static Lint + Playwright 3 viewports để bắt lỗi và đưa lên Bug Board."
    )


_VALID_CONTENT_TYPES = {
    "product",
    "article_single",
    "article_list",
    "album",
    "video",
    "form",
    "layout",
    "feature",
}
_VALID_SCOPES = {"menu", "homepage", "inner_page", "global"}
_VALID_SOURCES = {"figma_and_spec", "figma_only", "spec_only"}
_VALID_CARDINALITIES = {"single", "multiple", "none"}


def _infer_cardinality_from_type(ctype: str) -> str:
    if ctype == "article_single":
        return "single"
    if ctype in {"product", "article_list", "album", "video"}:
        return "multiple"
    return "none"


def parse_ai_sections_from_reply(
    reply_text: str,
    fallback_sections: list[dict[str, Any]],
    fallback_global: list[str],
) -> tuple[list[dict[str, Any]], list[str], str | None]:
    """
    Extract AI-updated `spec_sections`, `spec_global_features`, and optional
    `leader_plan_markdown` from an LLM reply (JSON fenced block or raw JSON).
    Falls back cleanly to `fallback_sections` if JSON is missing or invalid.
    """
    text = (reply_text or "").strip()
    if not text:
        return fallback_sections, fallback_global, None

    json_candidate = ""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        json_candidate = fenced.group(1)
    elif text.startswith("{") and text.endswith("}"):
        json_candidate = text
    else:
        brace_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if brace_match:
            json_candidate = brace_match.group(1)

    if not json_candidate:
        return fallback_sections, fallback_global, (text if len(text) >= 40 else None)

    try:
        parsed = json.loads(json_candidate)
    except Exception:
        return fallback_sections, fallback_global, (text if len(text) >= 40 else None)

    if not isinstance(parsed, dict):
        return fallback_sections, fallback_global, None

    raw_sections = parsed.get("spec_sections") or parsed.get("sections")
    sections_out: list[dict[str, Any]] = []
    if isinstance(raw_sections, list):
        for idx, raw in enumerate(raw_sections, start=1):
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or "").strip()
            if not name:
                continue
            ctype = str(raw.get("content_type") or "layout").strip()
            if ctype not in _VALID_CONTENT_TYPES:
                ctype = "feature"
            scope = str(raw.get("scope") or "homepage").strip()
            if scope not in _VALID_SCOPES:
                scope = "homepage"
            source = str(raw.get("source") or "figma_and_spec").strip()
            if source not in _VALID_SOURCES:
                source = "figma_and_spec"
            card = str(raw.get("item_cardinality") or "").strip()
            if card not in _VALID_CARDINALITIES:
                card = _infer_cardinality_from_type(ctype)
            try:
                cat_lvl = max(0, min(3, int(raw.get("category_levels", 0))))
            except (TypeError, ValueError):
                cat_lvl = 0

            sections_out.append(
                {
                    "id": str(raw.get("id") or f"sec-{idx}"),
                    "order": idx,
                    "name": name,
                    "scope": scope,
                    "source": source,
                    "figma_section_name": str(raw.get("figma_section_name") or "").strip(),
                    "content_type": ctype,
                    "category_levels": cat_lvl,
                    "item_cardinality": card,
                    "spec_requirements": str(raw.get("spec_requirements") or "").strip(),
                    "notes": str(raw.get("notes") or "").strip(),
                }
            )

    raw_global = parsed.get("spec_global_features") or parsed.get("global_features")
    global_out = fallback_global
    if isinstance(raw_global, list):
        cleaned_g = [str(g).strip() for g in raw_global if str(g).strip()]
        if cleaned_g:
            global_out = cleaned_g

    md_override: str | None = None
    if isinstance(parsed.get("leader_plan_markdown"), str) and len(parsed["leader_plan_markdown"].strip()) >= 40:
        md_override = parsed["leader_plan_markdown"].strip()
    elif fenced:
        outside = (text[: fenced.start()] + text[fenced.end() :]).strip()
        if len(outside) >= 40:
            md_override = outside

    return (sections_out or fallback_sections), global_out, md_override
