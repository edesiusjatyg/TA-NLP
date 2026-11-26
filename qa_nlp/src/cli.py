from pathlib import Path
from .qa_pipeline import QuestionAnsweringSystem

def print_result(result):
    print("\n" + "=" * 68)
    print("JAWABAN")
    print("=" * 68)
    print(result["answer"])
    print(f"\nSkor internal: {result['confidence']:.4f}")
    print("(Skor ini bukan probabilitas kebenaran.)")

    if result["sources"]:
        print("\nSUMBER")
        for source in result["sources"]:
            print(f"- Bagian: {source.get('section')}")
            print(f"  Halaman PDF: {source.get('pdf_page')}")
            print(f"  Halaman buku: {source.get('book_page')}")
            print(f"  Status review: {source.get('review_status')}")

    print("\nKLASIFIKASI PERTANYAAN")
    print(f"- Intent: {result['classification']['intent']}")
    print(f"- Answer type: {result['classification']['answer_type']}")

    print("\nPASSAGE TERATAS")
    for i, passage in enumerate(result["retrieved_passages"][:3], start=1):
        print(f"\n{i}. Skor: {passage['retrieval_score']:.4f}")
        print(f"   Bagian: {passage.get('section')}")
        print(f"   {passage['clean_text'][:500]}")

def main():
    project_root = Path(__file__).resolve().parents[2]
    corpus_path = project_root / "corpus" / "output" / "classic_passages.jsonl"

    print("=" * 68)
    print("QUESTION ANSWERING SEDERHANA - KORPUS BNPB")
    print("Sistem ekstraktif tanpa Large Language Model (LLM)")
    print("=" * 68)

    if not corpus_path.exists():
        print(f"\nERROR: File korpus tidak ditemukan: {corpus_path}")
        print("Periksa kembali lokasi folder corpus/output.")
        return

    pending = input(
        "\nIzinkan passage berstatus pending untuk eksplorasi? (y/n) [y]: "
    ).strip().lower()
    allow_pending = pending != "n"

    try:
        system = QuestionAnsweringSystem(
            corpus_path,
            allow_pending=allow_pending
        )
    except Exception as exc:
        print(f"\nGagal memuat sistem: {exc}")
        return

    pending_count = sum(
        p.get("review_status") != "approved"
        for p in system.passages
    )
    print(f"\nJumlah passage dimuat: {len(system.passages)}")
    if pending_count:
        print(
            f"PERINGATAN: {pending_count} passage belum berstatus approved. "
            "Hasil hanya untuk pengembangan, bukan evaluasi final."
        )

    print("\nKetik pertanyaan untuk mencari jawaban.")
    print("Ketik 'keluar' untuk mengakhiri program.")

    while True:
        print("\n" + "-" * 68)
        question = input("Pertanyaan: ").strip()

        if question.lower() in {"keluar", "exit", "quit"}:
            print("Program selesai.")
            break

        if not question:
            print("Pertanyaan tidak boleh kosong.")
            continue

        try:
            result = system.ask(question, top_k=5)
            print_result(result)
        except Exception as exc:
            print(f"Terjadi kesalahan saat memproses pertanyaan: {exc}")

if __name__ == "__main__":
    main()
