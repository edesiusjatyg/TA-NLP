from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .question_processor import normalize_tokens

class PassageRetriever:
    def __init__(self, passages):
        if not passages:
            raise ValueError("Korpus tidak memiliki passage yang dapat digunakan.")
        self.passages = passages
        self.vectorizer = TfidfVectorizer(
            tokenizer=lambda text: normalize_tokens(text),
            token_pattern=None,
            lowercase=True,
            ngram_range=(1, 2),
            sublinear_tf=True
        )
        self.matrix = self.vectorizer.fit_transform(
            [p["retrieval_text"] for p in passages]
        )

    def search(self, question, top_k=5):
        query_vector = self.vectorizer.transform([question])
        scores = cosine_similarity(query_vector, self.matrix).ravel()
        ranked = scores.argsort()[::-1][:top_k]
        results = []
        for idx in ranked:
            item = dict(self.passages[idx])
            item["retrieval_score"] = float(scores[idx])
            results.append(item)
        return results
