from __future__ import annotations

import io
import zipfile
import xml.etree.ElementTree as ET


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
                    c_texts = [t.text for t in cell.findall(".//w:t", ns) if t.text]
                    cells.append(" ".join("".join(c_texts).split()))
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


def parse_spec_upload(filename: str, data: bytes) -> str:
    lower = (filename or "").lower()
    if lower.endswith(".docx"):
        return parse_docx_bytes(data)
    if lower.endswith(".xlsx"):
        return parse_xlsx_bytes(data)
    if lower.endswith((".txt", ".md", ".csv", ".json")):
        return data.decode("utf-8", errors="ignore").strip()
    raise ValueError("Chỉ hỗ trợ file .docx (Word), .xlsx (Excel), .txt, .md, .csv")
