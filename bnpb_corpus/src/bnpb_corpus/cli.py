from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import json
import sys
import urllib.request

from .core import (ROOT, Budget, build, check_inputs, check_outputs, digest, read_json, read_jsonl, write_json)


def parser():
    p = argparse.ArgumentParser(description="Build dan audit korpus bersama QA BNPB; tanpa GPU atau LLM")
    default_root = ROOT
    if not (default_root / "configs/source.json").is_file():
        default_root = next((path for path in (Path.cwd(), *Path.cwd().parents) if (path / "configs/source.json").is_file()), ROOT)
    p.add_argument("--root", type=Path, default=default_root, help="Root paket proyek")
    sub = p.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="Ekstrak PDF, terapkan kurasi, buat JSONL/MD/TXT/HTML")
    b.add_argument("--pdf", type=Path)
    b.add_argument("--out", type=Path)
    b.add_argument("--max-words", type=int, default=160)
    b.add_argument("--tokenizer", help="Model ID atau direktori tokenizer embedding; opsional untuk build awal")
    b.add_argument("--tokenizer-revision", help="Commit tokenizer untuk reproduksi")
    b.add_argument("--max-tokens", type=int, default=350, help="Termasuk prefix passage dan special tokens jika tokenizer dipakai")
    b.add_argument("--local-only", action="store_true")
    b.add_argument("--release", action="store_true", help="Wajib review kelompok lengkap dan token budget tepat")
    for name in ("stats", "verify"):
        a = sub.add_parser(name)
        a.add_argument("--out", type=Path)
    a = sub.add_parser("inspect", help="Lihat unit berdasarkan ID, teks, atau halaman")
    a.add_argument("--page", type=int)
    a.add_argument("--contains", default="")
    a.add_argument("--unit-id", default="")
    a.add_argument("--out", type=Path)
    a = sub.add_parser("render-pages", help="Render halaman sumber untuk review visual")
    a.add_argument("--pages", required=True, help="Contoh 29,30,67,69 atau 16-19")
    a.add_argument("--dpi", type=int, default=150)
    a.add_argument("--out", type=Path)
    a = sub.add_parser("review", help="Catat keputusan manusia atas satu unit; build ulang setelahnya")
    a.add_argument("--unit-id", required=True)
    a.add_argument("--decision", choices=["approved", "excluded"], required=True)
    a.add_argument("--reviewer", required=True)
    a.add_argument("--note", required=True)
    a.add_argument("--accept-flags", default="", help="Flag yang sudah dibaca dan diputuskan perlakuannya, pisahkan koma")
    a.add_argument("--out", type=Path)
    sub.add_parser("fetch-source", help="Unduh URL resmi yang dikunci dan periksa SHA256")
    return p


def resolve(root, path, default):
    value = path if path is not None else Path(default)
    return value if value.is_absolute() else root / value


def run(args):
    root = args.root.resolve()
    out = resolve(root, getattr(args, "out", None), "outputs")
    if args.command == "build":
        tokenizer = args.tokenizer
        # Local paths are relative to the selected project, not the terminal's cwd.
        if tokenizer:
            candidate = Path(tokenizer).expanduser()
            if candidate.is_absolute() or (root / candidate).exists() or tokenizer.startswith(("./", "../", "data/")):
                candidate = candidate if candidate.is_absolute() else root / candidate
                if not candidate.is_dir():
                    raise ValueError(f"Direktori tokenizer tidak ditemukan: {candidate}")
                tokenizer = str(candidate.resolve())
        report = build(resolve(root, args.pdf, "data/raw/buku_saku_bnpb.pdf"), out, root / "configs", root / "data/curation",
                       Budget(max_words=args.max_words, tokenizer_name=tokenizer, tokenizer_revision=args.tokenizer_revision,
                              max_tokens=args.max_tokens, local_only=args.local_only), args.release)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.command == "stats":
        print(json.dumps(read_json(out / "validation_report.json"), ensure_ascii=False, indent=2))
    elif args.command == "verify":
        manifest = read_json(out / "build_manifest.json")
        check_inputs(manifest, root)
        check_outputs(out, manifest)
        units = read_jsonl(out / "evidence_units.jsonl")
        chunks = read_jsonl(out / "rag_chunks.jsonl")
        ids = {u["evidence_unit_id"] for u in units}
        if any(i not in ids for c in chunks for i in c["evidence_unit_ids"]):
            raise ValueError("Chunk menunjuk ID yang tidak ada")
        print(f"OK: {len(manifest['files'])} checksum, {len(units)} unit, {len(chunks)} chunk. Ini validasi integritas, bukan penilaian kebenaran manual.")
    elif args.command == "inspect":
        if args.page is not None and not 1 <= args.page <= 98:
            raise ValueError("Nomor halaman harus 1 sampai 98")
        units = read_jsonl(out / "evidence_units.jsonl")
        matches = [u for u in units if (args.page is None or u["pdf_page_start"] == args.page)
                   and args.contains.casefold() in u["clean_text"].casefold()
                   and (not args.unit_id or u["evidence_unit_id"] == args.unit_id)]
        for unit in matches:
            print(json.dumps(unit, ensure_ascii=False, indent=2))
        if not matches:
            raise ValueError("Unit tidak ditemukan")
    elif args.command == "render-pages":
        import pymupdf
        source = read_json(root / "configs/source.json")
        if digest((root / "data/raw/buku_saku_bnpb.pdf").read_bytes()) != source["sha256"]:
            raise ValueError("PDF sumber berubah; render dibatalkan agar review tidak memakai buku lain")
        if not 50 <= args.dpi <= 600:
            raise ValueError("DPI harus 50 sampai 600")
        numbers = set()
        for part in args.pages.split(","):
            ends = [int(x) for x in part.strip().split("-")]
            if len(ends) == 1:
                numbers.add(ends[0])
            elif len(ends) == 2 and ends[0] <= ends[1]:
                numbers.update(range(ends[0], ends[1] + 1))
            else:
                raise ValueError("Format rentang halaman tidak valid")
        destination = resolve(root, args.out, "review_images")
        destination.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(root / "data/raw/buku_saku_bnpb.pdf") as doc:
            if any(n < 1 or n > len(doc) for n in numbers):
                raise ValueError("Nomor halaman di luar PDF")
            for n in sorted(numbers):
                doc[n - 1].get_pixmap(dpi=args.dpi).save(destination / f"pdf-{n:03d}.png")
        print(f"Dirender {len(numbers)} halaman ke {destination}")
    elif args.command == "review":
        if not args.reviewer.strip() or not args.note.strip():
            raise ValueError("Nama reviewer dan catatan wajib diisi")
        units = read_jsonl(out / "evidence_units.jsonl")
        unit = next((u for u in units if u["evidence_unit_id"] == args.unit_id), None)
        if unit is None:
            raise ValueError("ID tidak ditemukan; jalankan inspect terlebih dahulu")
        # Do not apply a decision to output whose source or recipes have changed.
        saved = read_json(out / "build_manifest.json")
        check_inputs(saved, root, allow_review_changes=True)
        check_outputs(out, saved)
        flags = [s.strip() for s in args.accept_flags.split(",") if s.strip()]
        if not set(flags) <= set(unit["source_quality_flag"]):
            raise ValueError("accept-flags harus berasal dari flag unit tersebut")
        path = root / "data/curation/reviews.json"
        reviews = read_json(path)
        reviews[args.unit_id] = {"content_sha256": unit["content_sha256"], "decision": args.decision,
                                "reviewer": args.reviewer.strip(), "note": args.note.strip(), "accepted_flags": flags,
                                "reviewed_at": datetime.now(timezone.utc).isoformat()}
        write_json(path, reviews)
        print("Keputusan dicatat. Jalankan build ulang agar keputusan masuk ke hasil dan versi korpus.")
    elif args.command == "fetch-source":
        source = read_json(root / "configs/source.json")
        path = root / "data/raw/buku_saku_bnpb.pdf"
        if path.exists():
            if digest(path.read_bytes()) != source["sha256"]:
                raise ValueError("File lokal berbeda; tidak ditimpa. Periksa versi sumber.")
            print("PDF lokal sudah cocok SHA256; tidak perlu mengunduh.")
            return
        request = urllib.request.Request(source["url"], headers={"User-Agent": "BNPB-Corpus-Research/0.1"})
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read(25_000_001)
        if len(body) > 25_000_000 or digest(body) != source["sha256"]:
            raise ValueError("Unduhan tidak cocok dengan salinan sumber; file tidak disimpan")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        print("PDF resmi disimpan dan SHA256 cocok.")


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        run(args)
    except (OSError, ValueError, KeyError, ImportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
