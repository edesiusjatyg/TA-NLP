import json
from pathlib import Path

def load_jsonl(path):
    """Membaca JSONL baris demi baris dan mempertahankan metadata sumber."""
    records = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL tidak valid pada baris {line_no}: {exc}") from exc
            if (row.get("clean_text") or row.get("text") or "").strip():
                records.append(row)
    return records

def prepare_passages(path, allow_pending=True):
    """
    Menyiapkan passage untuk QA.
    allow_pending=True hanya untuk pengembangan. Evaluasi final sebaiknya
    menggunakan korpus yang telah direview dan dibekukan.
    """
    rows = load_jsonl(path)
    prepared = []
    skipped = {"empty": 0, "unreviewed": 0, "quality_flag": 0}

    for row in rows:
        text = (row.get("clean_text") or row.get("text") or "").strip()
        if not text:
            skipped["empty"] += 1
            continue

        status = row.get("review_status", "unknown")
        if not allow_pending and status != "approved":
            skipped["unreviewed"] += 1
            continue

        source_meta = row.get("source") if isinstance(row.get("source"), dict) else {}
        flags = row.get("source_quality_flag") or row.get("flags") or []
        hazard_tags = row.get("hazard_tags") or ([row["topic"]] if row.get("topic") else [])
        phase_tags = row.get("phase_tags") or ([row["phase"]] if row.get("phase") else [])
        material_tags = row.get("material_tags") or ([row["material"]] if row.get("material") else [])

        # Flag sumber tetap dipertahankan dan ditampilkan; tidak dihapus diam-diam.
        prepared.append({
            "evidence_unit_id": row.get("evidence_unit_id") or row.get("id"),
            "clean_text": text,
            "retrieval_text": (row.get("retrieval_text") or text).strip(),
            "section": row.get("section", ""),
            "subsection": row.get("subsection", ""),
            "hazard_tags": hazard_tags,
            "phase_tags": phase_tags,
            "material_tags": material_tags,
            "pdf_page_start": row.get("pdf_page_start") or source_meta.get("pdf_page"),
            "book_page_start": row.get("book_page_start") or source_meta.get("book_page"),
            "review_status": status,
            "source_quality_flag": flags,
            "corpus_version": row.get("corpus_version", "")
        })
    return prepared, skipped
