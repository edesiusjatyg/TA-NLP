import re

INTENT_PATTERNS = [
    ("DEFINITION", [r"\bapa\s+(itu|yang dimaksud)\b", r"\bdefinisi\b", r"\bpengertian\b"]),
    ("CAUSE", [r"\b(mengapa|kenapa|apa penyebab)\b", r"\bpenyebab\b"]),
    ("PREVENTION", [r"\b(mencegah|pencegahan|menghindari)\b"]),
    ("ACTION", [r"\b(apa yang harus dilakukan|bagaimana cara|langkah|tindakan)\b"]),
    ("IMPACT", [r"\b(dampak|akibat|pengaruh)\b"]),
    ("LOCATION", [r"\b(di mana|dimana|ke mana)\b"]),
    ("TIME", [r"\b(kapan|berapa lama)\b"]),
    ("QUANTITY", [r"\b(berapa|jumlah|besar)\b"]),
    ("PERSON_OR_ORG", [r"\b(siapa|lembaga apa|instansi apa)\b"]),
]

ANSWER_TYPE_PATTERNS = [
    ("DEFINITION", [r"\bapa\s+(itu|yang dimaksud)\b", r"\bdefinisi\b", r"\bpengertian\b"]),
    ("PERSON_OR_ORG", [r"\b(siapa|lembaga apa|instansi apa)\b"]),
    ("TIME", [r"\b(kapan|berapa lama)\b"]),
    ("LOCATION", [r"\b(di mana|dimana|ke mana)\b"]),
    ("NUMBER", [r"\b(berapa|jumlah|berapa banyak)\b"]),
    ("CAUSE", [r"\b(mengapa|kenapa|penyebab)\b"]),
    ("PROCEDURE", [r"\b(bagaimana|apa yang harus dilakukan|langkah|cara)\b"]),
]

def classify_question(question):
    q = question.lower().strip()
    intent = "GENERAL"
    answer_type = "DESCRIPTION"
    for label, patterns in INTENT_PATTERNS:
        if any(re.search(p, q) for p in patterns):
            intent = label
            break
    for label, patterns in ANSWER_TYPE_PATTERNS:
        if any(re.search(p, q) for p in patterns):
            answer_type = label
            break
    return {"intent": intent, "answer_type": answer_type}
