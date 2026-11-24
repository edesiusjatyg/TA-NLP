"""Ekstraksi deterministik, kurasi berbasis koordinat, dan chunking unit utuh.

Tidak memanggil LLM, tidak mengoreksi fakta sumber, tidak membaca kunci QA.
Koordinat recipe hanya sah untuk SHA256 PDF yang dikunci dalam source.json.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from html import escape
from pathlib import Path
from datetime import datetime
import csv
import json
import os
import re
import shutil
import tempfile
import unicodedata
from urllib.parse import quote

import pymupdf
from . import __version__


ROOT = Path(__file__).resolve().parents[2]
HAZARDS = {"GEMPA", "TSUNAMI", "ERUPSI", "BANJIR", "LONGSOR", "PUTING", "KERING", "KARHUTLA", "COVID"}
BLOCKING = {"SOURCE_AMBIGUOUS", "DUBIOUS_SOURCE", "INCOMPLETE_SOURCE"}
PHASES = {"PRA", "SAAT", "PASCA", "UMUM"}
QUALITY_FLAGS = BLOCKING | {"TIME_SENSITIVE", "SOURCE_ATTRIBUTION_REQUIRED", "SOURCE_SENSITIVE",
                           "HISTORICAL_HEALTH_GUIDANCE", "NO_ABSOLUTE_PROTECTION_CLAIM", "HISTORICAL_RECORD"}
OUTPUT_FILES = ("pages_raw.jsonl", "evidence_units.jsonl", "rag_chunks.jsonl", "classic_passages.jsonl",
                "page_inventory.csv", "review_queue.csv", "validation_report.json", "corpus.md", "corpus.txt", "review.html")


def digest(value: bytes | str) -> str:
    return sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Review decisions must never leave a partially written JSON file.
    body = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
        temp_path = Path(f.name)
        try:
            f.write(body)
            f.flush()
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def collect_inputs(pdf: Path, config: Path, curation: Path, budget) -> dict:
    root = config.resolve().parent
    paths = {"source_pdf": pdf, "source_config": config / "source.json", "page_plan": config / "page_plan.json",
             "recipes": curation / "recipes.json", "reviews": curation / "reviews.json"}
    paths.update({"code:" + p.name: p for p in Path(__file__).parent.glob("*.py")})
    if budget.tokenizer_name and Path(budget.tokenizer_name).is_dir():
        paths.update({"tokenizer:" + p.name: p for p in Path(budget.tokenizer_name).iterdir() if p.is_file()})
    return {key: {"path": "src/bnpb_corpus/" + p.name if key.startswith("code:") else os.path.relpath(p.resolve(), root), "sha256": digest(p.read_bytes())}
            for key, p in sorted(paths.items())}


def check_inputs(manifest: dict, root: Path, allow_review_changes=False):
    if not manifest.get("input_files"):
        raise ValueError("Manifest lama tidak mencatat input build; bangun ulang korpus")
    for key, record in manifest["input_files"].items():
        if key == "reviews" and allow_review_changes:
            continue
        # Check the Python code actually running, including installed/editable use.
        path = Path(__file__).parent / key[5:] if key.startswith("code:") else root / record["path"]
        if not path.is_file() or digest(path.read_bytes()) != record["sha256"]:
            raise ValueError(f"Input build berubah atau hilang: {key}. Build ulang sebelum melanjutkan.")
    if manifest["dependencies"]["PyMuPDF"] != pymupdf.VersionBind:
        raise ValueError("Versi PyMuPDF berbeda dari build; gunakan dependensi terkunci atau build ulang")


def check_outputs(out: Path, manifest: dict):
    if set(manifest.get("files", {})) != set(OUTPUT_FILES):
        raise ValueError("Daftar file manifest tidak lengkap atau tidak sesuai schema")
    for name in OUTPUT_FILES:
        record = manifest["files"][name]
        path = out / name
        if not path.is_file() or digest(path.read_bytes()) != record["sha256"] or path.stat().st_size != record["bytes"]:
            raise ValueError(f"Berkas hasil build berubah atau hilang: {name}. Build ulang dari recipe, jangan edit outputs.")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(row[k], ensure_ascii=False) if isinstance(row.get(k), (dict, list)) else row.get(k, "") for k in fields})


def normalize(text: str) -> str:
    """NFKC merapikan ligatur; tidak menghapus negasi, angka, unit, stopwords."""
    text = unicodedata.normalize("NFKC", text).replace("\u00ad", "")
    return re.sub(r"\s+", " ", text).strip()


def inside(rect, box) -> bool:
    x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return rect[0] <= x < rect[2] and rect[1] <= y < rect[3]


def extract(pdf: Path, source: dict) -> list[dict]:
    body = pdf.read_bytes()
    actual = digest(body)
    if actual != source["sha256"]:
        raise ValueError(f"SHA256 PDF tidak cocok. Diharapkan {source['sha256']}; diperoleh {actual}. Recipe tidak dijalankan pada buku lain.")
    pages = []
    with pymupdf.open(stream=body, filetype="pdf") as doc:
        if len(doc) != source["pdf_pages"]:
            raise ValueError("Jumlah halaman PDF berbeda dari sumber yang dikunci")
        for i, page in enumerate(doc, 1):
            lines = []
            # Match the block numbering of get_text('words'): images must not
            # consume block IDs in this text-only representation.
            text_flags = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
            for bi, block in enumerate(page.get_text("dict", flags=text_flags)["blocks"]):
                if block["type"] != 0:
                    continue
                for li, line in enumerate(block["lines"]):
                    raw = "".join(span["text"] for span in line["spans"])
                    if not raw.strip():
                        continue
                    lines.append({"line_id": f"p{i:03d}-b{bi:03d}-l{li:03d}", "block_id": bi,
                                  "bbox": [round(v, 4) for v in line["bbox"]], "raw_text": raw,
                                  "text": normalize(raw), "font_size": round(max(s["size"] for s in line["spans"]), 2)})
            # Words retain the original block/line indices, even for merged table blocks.
            words = [{"bbox": [round(v, 4) for v in w[:4]], "text": w[4],
                      "line_id": f"p{i:03d}-b{w[5]:03d}-l{w[6]:03d}"} for w in page.get_text("words")]
            pages.append({"pdf_page": i, "width": page.rect.width, "height": page.rect.height,
                          "raw_text": page.get_text(sort=False), "lines": lines, "words": words})
    return pages


def select_region(page: dict, rect: list[float]) -> list[dict]:
    selected = defaultdict(list)
    for word in page["words"]:
        if inside(rect, word["bbox"]):
            selected[word["line_id"]].append(word)
    result = []
    for lid, words in selected.items():
        words.sort(key=lambda w: w["bbox"][0])
        result.append({"line_id": lid, "bbox": [min(w["bbox"][0] for w in words), min(w["bbox"][1] for w in words),
                                                   max(w["bbox"][2] for w in words), max(w["bbox"][3] for w in words)],
                       "raw_text": " ".join(w["text"] for w in words)})
    result.sort(key=lambda r: (round(r["bbox"][1], 1), r["bbox"][0]))
    return result


def phase_at(plan: dict, y: float) -> str:
    phase = plan.get("default_phase", "UMUM")
    for start, label in plan.get("phase_boundaries", []):
        if y >= start:
            phase = label
    return phase


def assemble(page: dict, spec: dict) -> tuple[str, list[dict], dict]:
    """Labels added for table serialization are metadata, not book quotations."""
    fragments, pieces, cells = [], [], {}
    for field in spec["parts"]:
        selected = select_region(page, field["rect"])
        if not selected:
            raise ValueError(f"Region kosong pada PDF {page['pdf_page']}: {field['rect']}")
        text = normalize(" ".join(f["raw_text"] for f in selected))
        if field.get("join_url"):
            text = re.sub(r"\s+", "", text)
        fragments.extend(selected)
        if field.get("label"):
            cells[field["label"]] = text
            pieces.append(f"{field['label']}: {text}")
        else:
            pieces.append(text)
    text = "; ".join(pieces) if cells else " ".join(pieces)
    if "text_override" in spec:
        # Explicit checked transcription/repair; source fragments remain unchanged.
        if not isinstance(spec.get("note"), str) or not spec["note"].strip():
            raise ValueError("text_override memerlukan alasan transformasi")
        text = spec["text_override"]
    return normalize(text), fragments, cells


def generic_specs(page: dict, plan: dict) -> list[dict]:
    groups = defaultdict(list)
    for line in page["lines"]:
        text = line["text"]
        y = line["bbox"][1]
        if y >= 415 or text in plan.get("skip_exact_lines", []) or (text in plan.get("skip_lines", []) and line["font_size"] > 10) or text in {"TANGGAP TANGKAS TANGGUH", "MENGHADAPI BENCANA"}:
            continue
        # Only standalone ornamental numerals and exact known headings are removed.
        if re.fullmatch(r"\d+[.)]?", text) or text in {"Prabencana", "Saat Bencana", "Pascabencana", "SIAGA BENCANA", "KESIAPSIAGAAN"}:
            continue
        if any(inside(rect, line["bbox"]) for rect in plan.get("skip_rects", [])):
            continue
        groups[line["block_id"]].append(line)
    specs = []
    for lines in groups.values():
        # Break mixed blocks at phase headings or list starts rather than flattening them.
        lines.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))
        runs = []
        for line in lines:
            if not runs or phase_at(plan, line["bbox"][1]) != phase_at(plan, runs[-1][0]["bbox"][1]) or re.match(r"(?:\d{1,2}[.)]|[•●])\s", line["text"]):
                runs.append([])
            runs[-1].append(line)
        for run in runs:
            specs.append({"text": normalize(" ".join(l["raw_text"] for l in run)), "fragments": run,
                          "phase": phase_at(plan, run[0]["bbox"][1]), "y": run[0]["bbox"][1], "x": run[0]["bbox"][0]})
    specs.sort(key=lambda s: (s["y"], s["x"]))
    return specs


def curate(pages: list[dict], plans: list[dict], recipes: dict, source: dict, reviews: dict) -> list[dict]:
    units = []
    for page, plan in zip(pages, plans, strict=True):
        if page["pdf_page"] != plan["pdf_page"]:
            raise ValueError("Urutan page plan berbeda dari PDF")
        if not plan["include_in_knowledge"]:
            continue
        n = page["pdf_page"]
        specs = recipes.get(str(n), {}).get("units")
        if specs is None:
            specs = generic_specs(page, plan)
        for j, spec in enumerate(specs, 1):
            if "parts" in spec:
                text, fragments, cells = assemble(page, spec)
            else:
                text, fragments, cells = spec["text"], spec["fragments"], {}
            if not text:
                raise ValueError(f"Unit kosong PDF {n} urutan {j}")
            phase = spec.get("phase", plan.get("default_phase", "UMUM"))
            flags = sorted(set(plan.get("quality_flags", []) + spec.get("quality_flags", [])))
            for needle, extra in plan.get("unit_flags_contains", {}).items():
                if needle.casefold() in text.casefold():
                    flags = sorted(set(flags + extra))
            context = spec.get("context", plan.get("context", ""))
            if "context" not in spec:
                for y0, y1, label in plan.get("context_ranges", []):
                    if y0 <= spec.get("y", -1) < y1:
                        context = label
            unit_id = f"BNPB-{source['sha256'][:8]}-p{n:03d}-u{j:03d}-{digest(text)[:8]}"
            content_hash = digest(canonical({"text": text, "phase": phase, "section": plan["section"], "topic": plan["hazard_tags"],
                                             "context": context, "subsection": spec.get("subsection", phase), "flags": flags,
                                             "material_tags": plan.get("material_tags", []), "book_page": plan["book_page"],
                                             "unit_type": spec.get("unit_type", "paragraph_or_list_item"),
                                             "source_sha256": source["sha256"], "pdf_page": n, "table_cells": cells,
                                             "provenance": [{k: f[k] for k in ("line_id", "bbox", "raw_text")} for f in fragments]}))
            review = reviews.get(unit_id, {})
            if not isinstance(review, dict):
                raise ValueError(f"Review harus berupa objek untuk {unit_id}")
            if review and review.get("content_sha256") != content_hash:
                raise ValueError(f"Review kadaluarsa untuk {unit_id}. Review harus sesuai teks dan metadata terbaru.")
            if review:
                if review.get("decision") not in {"approved", "excluded"}:
                    raise ValueError(f"Keputusan review tidak valid untuk {unit_id}")
                if any(not isinstance(review.get(k), str) or not review[k].strip() for k in ("reviewer", "reviewed_at", "note")):
                    raise ValueError(f"Review tidak lengkap untuk {unit_id}")
                try:
                    datetime.fromisoformat(review["reviewed_at"])
                except ValueError as exc:
                    raise ValueError(f"Tanggal review tidak valid untuk {unit_id}") from exc
                accepted = review.get("accepted_flags", [])
                if not isinstance(accepted, list) or any(not isinstance(f, str) for f in accepted) or not set(accepted) <= set(flags):
                    raise ValueError(f"accepted_flags tidak valid untuk {unit_id}")
            unit = {"schema_version": "1.0", "document_id": source["document_id"], "source_sha256": source["sha256"],
                    "evidence_unit_id": unit_id, "content_sha256": content_hash, "language": "id",
                    "pdf_page_start": n, "pdf_page_end": n, "book_page_start": plan["book_page"], "book_page_end": plan["book_page"],
                    "section": plan["section"], "subsection": spec.get("subsection", phase), "hazard_tags": plan["hazard_tags"],
                    "material_tags": plan.get("material_tags", []),
                    "phase_tags": [phase], "unit_type": spec.get("unit_type", "paragraph_or_list_item"),
                    "clean_text": text, "table_cells": cells, "source_fragments": fragments,
                    "annotation_type": "coordinate_recipe" if "parts" in spec else "pdf_block_extraction",
                    "transformation_notes": ["NFKC dan penyatuan spasi serta baris; fakta dan negasi dipertahankan"] + ([spec["note"]] if spec.get("note") else []),
                    "source_quality_flag": flags, "review_status": review.get("decision", "pending_group_review"),
                    "review": review, "unit_order_in_page": j}
            unit["context_label"] = context
            unit["retrieval_text"] = f"{plan['section']} | {unit['subsection']}" + (f" | {context}" if context else "") + "\n" + text
            units.append(unit)
    return units


@dataclass
class Budget:
    max_words: int = 160
    tokenizer_name: str | None = None
    tokenizer_revision: str | None = None
    max_tokens: int = 350
    prefix: str = "passage: "
    local_only: bool = False

    def __post_init__(self):
        if self.max_words < 1 or self.max_tokens < 1:
            raise ValueError("Anggaran harus positif")
        self.tokenizer = None
        self.snapshot = None
        self.tokenizer_versions = None
        self.tokenizer_fingerprint = None
        if self.tokenizer_name:
            import transformers
            import tokenizers
            from transformers import AutoTokenizer
            snapshot_path = Path(self.tokenizer_name) / "snapshot.json"
            if snapshot_path.is_file():
                self.snapshot = read_json(snapshot_path)
                for name, expected in self.snapshot["files_sha256"].items():
                    if digest((snapshot_path.parent / name).read_bytes()) != expected:
                        raise ValueError(f"Tokenizer snapshot berubah: {name}")
            self.tokenizer = AutoTokenizer.from_pretrained(self.tokenizer_name, revision=self.tokenizer_revision,
                                                         local_files_only=self.local_only, trust_remote_code=False)
            self.tokenizer_versions = {"transformers": transformers.__version__, "tokenizers": tokenizers.__version__}
            if not getattr(self.tokenizer, "is_fast", False):
                raise ValueError("Gunakan fast tokenizer agar fingerprint dan hitungan token dapat direproduksi")
            self.tokenizer_fingerprint = digest(canonical({"backend": self.tokenizer.backend_tokenizer.to_str(),
                                                           "model_max_length": self.tokenizer.model_max_length,
                                                           "special_tokens": self.tokenizer.special_tokens_map}))
            if self.max_tokens > self.tokenizer.model_max_length:
                raise ValueError(f"Anggaran {self.max_tokens} melebihi batas tokenizer {self.tokenizer.model_max_length}")

    def measure(self, text: str) -> int:
        if self.tokenizer is not None:
            return len(self.tokenizer.encode(self.prefix + text, add_special_tokens=True, truncation=False))
        return len(text.split())

    @property
    def limit(self):
        return self.max_tokens if self.tokenizer is not None else self.max_words

    def config(self):
        identity = (self.snapshot["model_id"] if self.snapshot else "local-tokenizer" if self.tokenizer_name and Path(self.tokenizer_name).is_dir() else self.tokenizer_name)
        return {"method": "whole_units_same_page_phase_subsection", "overlap_units": 0,
                "measure": "exact_tokenizer" if self.tokenizer is not None else "whitespace_words",
                "limit": self.limit, "tokenizer_name": identity,
                "tokenizer_revision": self.snapshot["revision"] if self.snapshot else self.tokenizer_revision,
                "prefix_counted": self.prefix if self.tokenizer is not None else None,
                "special_tokens_counted": self.tokenizer is not None, "long_unit_policy": "keep_and_flag_never_truncate",
                "tokenizer_snapshot": self.snapshot, "tokenizer_versions": self.tokenizer_versions,
                "tokenizer_fingerprint": self.tokenizer_fingerprint}


def eligible(units: list[dict], release: bool) -> list[dict]:
    active = [u for u in units if u["review_status"] != "excluded"]
    if release:
        pending = [u for u in active if u["review_status"] != "approved"]
        unresolved = [u for u in active if (set(u["source_quality_flag"]) & BLOCKING) - set(u["review"].get("accepted_flags", []))]
        if pending or unresolved:
            raise ValueError(f"Release ditolak: {len(pending)} unit belum disetujui dan {len(unresolved)} unit memiliki flag sumber yang belum ditangani. Lihat review_queue.csv.")
        if not HAZARDS <= {h for u in active for h in u["hazard_tags"]}:
            raise ValueError("Release harus tetap mencakup sembilan topik utama")
    return active


def chunk_units(units: list[dict], budget: Budget) -> list[dict]:
    chunks, current = [], []

    def key(u):
        return (u["pdf_page_start"], tuple(u["hazard_tags"]), tuple(u["material_tags"]), tuple(u["phase_tags"]), u["subsection"], u["context_label"], tuple(u["source_quality_flag"]))

    def text_of(items):
        lead = items[0]
        label = f"{lead['section']} | {lead['subsection']}" + (f" | {lead['context_label']}" if lead["context_label"] else "")
        return label + "\n" + "\n".join(u["clean_text"] for u in items)

    def flush():
        nonlocal current
        if not current:
            return
        text = text_of(current)
        count = budget.measure(text)
        chunks.append({"chunk_id": "chunk-" + digest(canonical([u["evidence_unit_id"] for u in current]) + canonical(budget.config()))[:20],
                       "document_id": current[0]["document_id"], "pdf_page_start": current[0]["pdf_page_start"], "pdf_page_end": current[-1]["pdf_page_end"],
                       "book_page_start": current[0]["book_page_start"], "book_page_end": current[-1]["book_page_end"],
                       "section": current[0]["section"], "subsection": current[0]["subsection"], "hazard_tags": current[0]["hazard_tags"],
                       "material_tags": current[0]["material_tags"],
                       "phase_tags": current[0]["phase_tags"], "evidence_unit_ids": [u["evidence_unit_id"] for u in current],
                       "clean_text": "\n".join(u["clean_text"] for u in current), "retrieval_text": text,
                       "word_count": len(text.split()), "token_count": count if budget.tokenizer else None,
                       "embedding_prefix": budget.prefix, "budget_measure": budget.config()["measure"], "measured_length": count,
                       "exceeds_budget": count > budget.limit, "source_quality_flag": current[0]["source_quality_flag"],
                       "review_status": "approved" if all(u["review_status"] == "approved" for u in current) else "pending_group_review"})
        current = []

    for unit in units:
        if current and (key(unit) != key(current[0]) or budget.measure(text_of(current + [unit])) > budget.limit):
            flush()
        current.append(unit)
    flush()
    return chunks


def validate(pages, plans, units, chunks, source, budget) -> dict:
    errors = []
    if len(pages) != 98 or len(plans) != 98:
        errors.append("Inventaris harus berisi seluruh 98 halaman")
    ids = [u["evidence_unit_id"] for u in units]
    if len(set(ids)) != len(ids):
        errors.append("ID unit duplikat")
    by_id = {u["evidence_unit_id"]: u for u in units}
    page_by_id = {p["pdf_page"]: p for p in pages}
    coverage = Counter(h for u in units if u["review_status"] != "excluded" for h in u["hazard_tags"])
    if not HAZARDS <= coverage.keys():
        errors.append("Ada topik utama tanpa unit aktif")
    for u in units:
        n = u["pdf_page_start"]
        if u["book_page_start"] != n - 2:
            errors.append(f"Pemetaan halaman salah {u['evidence_unit_id']}")
        if not u["clean_text"].strip() or len(u["phase_tags"]) != 1 or not set(u["phase_tags"]) <= PHASES:
            errors.append(f"Isi atau fase tidak valid {u['evidence_unit_id']}")
        if not u["hazard_tags"] or not set(u["hazard_tags"]) <= HAZARDS | {"UMUM"}:
            errors.append(f"Topik tidak valid {u['evidence_unit_id']}")
        if not set(u["source_quality_flag"]) <= QUALITY_FLAGS:
            errors.append(f"Flag kualitas tidak dikenal {u['evidence_unit_id']}")
        source_lines = {l["line_id"] for l in page_by_id[n]["lines"]}
        if not u["source_fragments"] or any(f["line_id"] not in source_lines for f in u["source_fragments"]):
            errors.append(f"Provenance hilang {u['evidence_unit_id']}")
        if "TANGGAP TANGKAS TANGGUH" in u["clean_text"]:
            errors.append(f"Footer ikut terindeks {u['evidence_unit_id']}")
        if u["hazard_tags"] in (["KARHUTLA"], ["COVID"]) and u["phase_tags"] == ["PASCA"]:
            errors.append("Fase PASCA dibuat untuk topik yang tidak memiliki subbagian itu")
    represented = Counter()
    if len({c["chunk_id"] for c in chunks}) != len(chunks):
        errors.append("ID chunk duplikat")
    for c in chunks:
        items = [by_id[i] for i in c["evidence_unit_ids"] if i in by_id]
        if len(items) != len(c["evidence_unit_ids"]) or not items:
            errors.append(f"Chunk menunjuk unit yang hilang {c['chunk_id']}")
            continue
        if c["clean_text"] != "\n".join(u["clean_text"] for u in items):
            errors.append("Teks chunk tidak cocok dengan unit")
        if len({tuple(u["phase_tags"]) for u in items}) != 1 or len({u["pdf_page_start"] for u in items}) != 1:
            errors.append("Chunk melintasi halaman atau fase")
        for field in ("hazard_tags", "material_tags", "source_quality_flag", "subsection"):
            if any(u[field] != items[0][field] for u in items) or c[field] != items[0][field]:
                errors.append(f"Metadata chunk tidak konsisten: {field}")
        if any(u["context_label"] != items[0]["context_label"] for u in items):
            errors.append("Chunk melintasi konteks")
        count = budget.measure(c["retrieval_text"])
        if c["measured_length"] != count or c["exceeds_budget"] != (count > budget.limit):
            errors.append("Pengukuran panjang chunk tidak cocok")
        if c["token_count"] != (count if budget.tokenizer is not None else None):
            errors.append("Hitungan token chunk tidak cocok")
        represented.update(c["evidence_unit_ids"])
    active = {u["evidence_unit_id"] for u in units if u["review_status"] != "excluded"}
    if set(represented) != active or any(n != 1 for n in represented.values()):
        errors.append("Cakupan unit aktif dalam chunk tidak tepat")
    duplicates = [t for t, count in Counter(u["clean_text"] for u in units).items() if count > 1]
    return {"schema_version": "1.0", "structural_status": "passed" if not errors else "failed", "errors": errors,
            "semantic_human_review": "not_implied_by_structural_validation", "source_sha256": source["sha256"],
            "archived_pdf_pages": len(pages), "knowledge_pages": len({u["pdf_page_start"] for u in units}),
            "units_total": len(units), "active_units": len(active), "chunks_total": len(chunks), "units_by_topic": dict(sorted(coverage.items())),
            "units_by_phase": dict(Counter(p for u in units for p in u["phase_tags"])),
            "review_status_counts": dict(Counter(u["review_status"] for u in units)),
            "quality_flag_counts": dict(Counter(f for u in units for f in u["source_quality_flag"])),
            "duplicate_text_count": len(duplicates), "duplicate_policy": "report_only_preserve_distinct_pages_and_contexts",
            "oversized_chunks": [c["chunk_id"] for c in chunks if c["exceeds_budget"]],
            "token_limit_verified": budget.tokenizer is not None, "chunking": budget.config()}


def write_exports(out: Path, pages, plans, units, chunks, source, report, version, inputs, pdf: Path, final_out: Path):
    for row in units + chunks:
        row["corpus_version"] = version
    write_jsonl(out / "pages_raw.jsonl", pages)
    write_jsonl(out / "evidence_units.jsonl", units)
    write_jsonl(out / "rag_chunks.jsonl", chunks)
    active = [u for u in units if u["review_status"] != "excluded"]
    passages = [{k: u[k] for k in ("evidence_unit_id", "corpus_version", "document_id", "clean_text", "retrieval_text", "section", "subsection", "hazard_tags", "material_tags", "phase_tags", "pdf_page_start", "book_page_start", "source_quality_flag", "review_status", "context_label")} for u in active]
    write_jsonl(out / "classic_passages.jsonl", passages)
    counts = Counter(u["pdf_page_start"] for u in units)
    inventory = [dict(p, units_count=counts[p["pdf_page"]]) for p in plans]
    write_csv(out / "page_inventory.csv", inventory, ["pdf_page", "book_page", "section", "hazard_tags", "include_in_knowledge", "page_type", "units_count", "exclusion_reason"])
    write_csv(out / "review_queue.csv", units, ["evidence_unit_id", "content_sha256", "pdf_page_start", "book_page_start", "section", "subsection", "phase_tags", "clean_text", "source_quality_flag", "review_status"])
    write_json(out / "validation_report.json", report)
    pending = any(u["review_status"] != "approved" for u in active)
    status = "development_pending_review" if pending else "reviewed"
    markdown = ["# Korpus Buku Saku BNPB", "", f"Versi data `{version}`", "", f"Status: {status}. Ekspor hanya memuat unit aktif. Metadata bukan kutipan buku. Unit excluded tetap ada pada evidence_units.jsonl dan review.html.", ""]
    html_pages = []
    for plan in plans:
        n = plan["pdf_page"]
        items = [u for u in units if u["pdf_page_start"] == n]
        if not items:
            continue
        if any(u["review_status"] != "excluded" for u in items):
            markdown.extend([f"## PDF {n} — halaman buku {plan['book_page']} — {plan['section']}", ""])
        cards = []
        for u in items:
            if u["review_status"] != "excluded":
                markdown.extend([f"### {u['subsection']} · {u['evidence_unit_id']}", "", f"Metadata: fase={','.join(u['phase_tags'])}; status={u['review_status']}; flag={','.join(u['source_quality_flag']) or 'tidak ada'}." , "", u["clean_text"], ""])
            cards.append(f"<article><h3>{escape(u['subsection'])}</h3><code>{escape(u['evidence_unit_id'])}</code><p class='meta'>{escape(u['review_status'])} | {escape(', '.join(u['source_quality_flag']) or 'tanpa flag')}</p><p>{escape(u['clean_text'])}</p></article>")
        pdf_href = quote(Path(os.path.relpath(pdf.resolve(), final_out.resolve())).as_posix(), safe="/")
        html_pages.append(f"<section><h2>PDF {n} · Buku {plan['book_page']} · {escape(plan['section'])}</h2><a href='{pdf_href}#page={n}'>Buka halaman PDF sumber</a>{''.join(cards)}</section>")
    (out / "corpus.md").write_text("\n".join(markdown), encoding="utf-8")
    (out / "corpus.txt").write_text("\n\n".join(f"[PDF {u['pdf_page_start']} | Buku {u['book_page_start']} | {u['section']} | {u['subsection']} | {u['evidence_unit_id']}]\n{u['clean_text']}" for u in active), encoding="utf-8")
    (out / "review.html").write_text("<!doctype html><html lang='id'><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Review Korpus BNPB</title><style>body{font:17px/1.6 system-ui;max-width:1000px;margin:32px auto;padding:20px;color:#20252b}article{border-bottom:1px solid #ccd3da;padding:14px 0}code{font-size:12px;overflow-wrap:anywhere}.meta{font-size:13px;color:#715408}h2{margin-top:48px}a{color:#174c91}</style><h1>Review Korpus BNPB</h1><p>Periksa teks terhadap PDF asli. Halaman ini tidak memberikan persetujuan otomatis. Catat keputusan melalui CLI review; jangan mengedit hasil build.</p>" + "".join(html_pages) + "</html>", encoding="utf-8")
    manifest = {"corpus_version": version, "source": source, "pipeline_version": __version__, "status": status,
                "dependencies": {"PyMuPDF": pymupdf.VersionBind}, "chunking": report["chunking"], "input_files": inputs, "files": {}}
    manifest["files"] = {name: {"sha256": digest((out / name).read_bytes()), "bytes": (out / name).stat().st_size} for name in sorted(OUTPUT_FILES)}
    write_json(out / "build_manifest.json", manifest)


def build(pdf: Path, out: Path, config: Path, curation: Path, budget: Budget, release=False):
    root = config.resolve().parent
    protected = [pdf.parent, config, curation, root / "src"]
    if budget.tokenizer_name and Path(budget.tokenizer_name).is_dir():
        protected.append(Path(budget.tokenizer_name))
    if out.is_symlink() or any(out.resolve().is_relative_to(p.resolve()) or p.resolve().is_relative_to(out.resolve()) for p in protected):
        raise ValueError("Folder output tidak boleh menimpa atau berada di dalam direktori sumber, config, kurasi, tokenizer, atau kode")
    if out.exists() and (not out.is_dir() or (any(out.iterdir()) and not (out / "build_manifest.json").is_file())):
        raise ValueError("Folder output tidak kosong dan bukan hasil build korpus; pilih folder output lain")
    before = collect_inputs(pdf, config, curation, budget)
    source = read_json(config / "source.json")
    plans = read_json(config / "page_plan.json")
    recipes = read_json(curation / "recipes.json")
    reviews = read_json(curation / "reviews.json")
    pages = extract(pdf, source)
    units = curate(pages, plans, recipes, source, reviews)
    active = eligible(units, release)
    chunks = chunk_units(active, budget)
    report = validate(pages, plans, units, chunks, source, budget)
    if report["errors"]:
        raise ValueError("Validasi gagal: " + "; ".join(report["errors"][:5]))
    if release and (budget.tokenizer is None or report["oversized_chunks"]):
        raise ValueError("Release RAG memerlukan tokenizer asli dan semua chunk berada dalam anggaran. Tidak ada truncation otomatis.")
    inputs = collect_inputs(pdf, config, curation, budget)
    if before != inputs:
        raise ValueError("Input berubah selama build. Hasil lama dipertahankan; ulangi setelah perubahan selesai.")
    version = "bnpb-" + digest(canonical({"inputs": inputs, "budget": budget.config(), "pymupdf": pymupdf.VersionBind, "pipeline_version": __version__}))[:16]
    report["corpus_version"] = version
    # Prepare all files beside the destination, then replace the managed folder.
    # A write error cannot leave a mixture of old and new generated files.
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{out.name}-build-", dir=out.parent) as tmp:
        stage = Path(tmp)
        if out.exists():
            shutil.copytree(out, stage, dirs_exist_ok=True)
        write_exports(stage, pages, plans, units, chunks, source, report, version, inputs, pdf, out)
        check_outputs(stage, read_json(stage / "build_manifest.json"))
        if inputs != collect_inputs(pdf, config, curation, budget):
            raise ValueError("Input berubah selama penulisan build; hasil lama dipertahankan")
        backup = None
        if out.exists():
            backup = Path(tempfile.mkdtemp(prefix=f".{out.name}-backup-", dir=out.parent))
            backup.rmdir()
            out.rename(backup)
        try:
            stage.rename(out)
        except BaseException:
            if backup is not None:
                backup.rename(out)
            raise
        else:
            if backup is not None:
                shutil.rmtree(backup)
    return report
