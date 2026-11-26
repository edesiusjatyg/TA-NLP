import re
from nltk.tokenize import RegexpTokenizer
from .question_processor import normalize_tokens
from .linguistic_analysis import simple_pos_tag

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

def split_sentences(text):
    return [s.strip() for s in SENTENCE_SPLIT.split(text) if len(s.strip()) >= 20]

def answer_type_match(sentence, answer_type):
    s = sentence.lower()
    if answer_type == "NUMBER":
        return bool(re.search(r"\d", s))
    if answer_type == "TIME":
        return bool(re.search(r"\b(pukul|hari|tanggal|bulan|tahun|menit|jam|detik)\b|\d", s))
    if answer_type == "LOCATION":
        return bool(re.search(r"\b(di|ke|dari|wilayah|provinsi|kabupaten|kota)\b", s))
    if answer_type == "PERSON_OR_ORG":
        return bool(re.search(r"\b(bnpb|bpbd|bmkg|pemerintah|dinas|kementerian|petugas)\b", s))
    if answer_type == "PROCEDURE":
        return bool(re.search(r"\b(lakukan|gunakan|hindari|jauhi|segera|pastikan|siapkan|menuju|berlindung)\b", s))
    if answer_type == "CAUSE":
        return bool(re.search(r"\b(karena|disebabkan|akibat|dipicu|menyebabkan)\b", s))
    return True

def extract_candidates(question, passages, answer_type, top_n=8):
    q_tokens = set(normalize_tokens(question))
    candidates = []
    seen = set()
    for passage in passages:
        for sentence in split_sentences(passage["clean_text"]):
            key = sentence.lower()
            if key in seen:
                continue
            seen.add(key)
            s_tokens = set(normalize_tokens(sentence))
            overlap = len(q_tokens & s_tokens) / max(1, len(q_tokens))
            type_bonus = 0.15 if answer_type_match(sentence, answer_type) else 0.0
            # Sentence scoring: lexical overlap + kecocokan tipe jawaban.
            score = 0.75 * overlap + type_bonus + 0.10 * passage["retrieval_score"]
            if score <= 0:
                continue
            candidates.append({
                "answer": sentence,
                "score": float(score),
                "retrieval_score": passage["retrieval_score"],
                "source": passage
            })
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:top_n]
