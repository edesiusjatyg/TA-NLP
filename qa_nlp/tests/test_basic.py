from src.question_classifier import classify_question
from src.question_processor import preprocess_question
from src.linguistic_analysis import shallow_parse

def test_question_preprocessing():
    result = preprocess_question("Apa yang harus dilakukan saat gempa bumi?")
    assert result["original"]

def test_classification():
    result = classify_question("Apa yang harus dilakukan saat gempa bumi?")
    assert result["intent"] == "ACTION"
    assert result["answer_type"] == "PROCEDURE"

def test_shallow_parse():
    result = shallow_parse("Bagaimana cara mencegah banjir?")
    assert "pos_tags" in result
    assert "chunks" in result
