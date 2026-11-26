import re
from nltk.tokenize import RegexpTokenizer
from nltk.corpus import stopwords

try:
    from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
    _stemmer = StemmerFactory().create_stemmer()
except Exception:
    _stemmer = None

TOKENIZER = RegexpTokenizer(r"[A-Za-zÀ-ÿ0-9]+")
FALLBACK_STOPWORDS = {
    "apa", "yang", "di", "ke", "dari", "dan", "atau", "untuk", "pada",
    "saat", "ketika", "dengan", "dalam", "adalah", "itu", "ini", "agar",
    "bagaimana", "mengapa", "kenapa", "siapa", "kapan", "dimana", "di mana",
    "berapa", "harus", "dapat", "bisa", "oleh", "sebuah", "tersebut"
}

def tokenize(text):
    return TOKENIZER.tokenize((text or "").lower())

def get_stopwords():
    try:
        return set(stopwords.words("indonesian")) | FALLBACK_STOPWORDS
    except LookupError:
        return FALLBACK_STOPWORDS

def normalize_tokens(text, remove_stopwords=True, stemming=True):
    tokens = tokenize(text)
    if remove_stopwords:
        stops = get_stopwords()
        tokens = [t for t in tokens if t not in stops]
    if stemming and _stemmer:
        tokens = [_stemmer.stem(t) for t in tokens]
    return tokens

def preprocess_question(question):
    if not question or not question.strip():
        raise ValueError("Pertanyaan tidak boleh kosong.")
    tokens = normalize_tokens(question)
    return {
        "original": question.strip(),
        "tokens": tokens,
        "normalized": " ".join(tokens)
    }
