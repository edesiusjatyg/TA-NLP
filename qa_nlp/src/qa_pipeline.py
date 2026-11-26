from pathlib import Path
from .corpus_processor import prepare_passages
from .question_processor import preprocess_question
from .question_classifier import classify_question
from .linguistic_analysis import shallow_parse
from .retriever import PassageRetriever
from .answer_extractor import extract_candidates
from .answer_processor import process_answer

class QuestionAnsweringSystem:
    def __init__(self, corpus_path, allow_pending=True):
        self.passages, self.skipped = prepare_passages(corpus_path, allow_pending)
        self.retriever = PassageRetriever(self.passages)

    def ask(self, question, top_k=5):
        processed = preprocess_question(question)
        classification = classify_question(question)
        linguistic = shallow_parse(question)
        retrieved = self.retriever.search(question, top_k=top_k)
        candidates = extract_candidates(
            question, retrieved, classification["answer_type"]
        )
        result = process_answer(candidates)
        result.update({
            "question": question,
            "question_processing": processed,
            "classification": classification,
            "linguistic_analysis": linguistic,
            "retrieved_passages": retrieved,
            "answer_candidates": candidates
        })
        return result
