def process_answer(candidates, threshold=0.08):
    if not candidates:
        return {
            "answer": "Maaf, jawaban tidak ditemukan dalam korpus.",
            "confidence": 0.0,
            "sources": [],
            "found": False
        }
    best = candidates[0]
    if best["score"] < threshold:
        return {
            "answer": "Maaf, jawaban yang cukup relevan tidak ditemukan dalam korpus.",
            "confidence": round(best["score"], 4),
            "sources": [],
            "found": False
        }

    source = best["source"]
    return {
        "answer": best["answer"],
        "confidence": round(best["score"], 4),
        "sources": [{
            "evidence_unit_id": source.get("evidence_unit_id"),
            "section": source.get("section"),
            "pdf_page": source.get("pdf_page_start"),
            "book_page": source.get("book_page_start"),
            "review_status": source.get("review_status"),
            "source_quality_flag": source.get("source_quality_flag", [])
        }],
        "found": True
    }
