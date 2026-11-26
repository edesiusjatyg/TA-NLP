"""
POS Tagging dan shallow parsing sederhana untuk Bahasa Indonesia.
Tagger berbasis aturan/dictionary ini sengaja transparan dan bukan model statistik.
Aturan perlu dievaluasi dan dapat diperluas berdasarkan korpus.
"""
import re
from nltk.tokenize import RegexpTokenizer
from nltk.chunk import RegexpParser

TOKENIZER = RegexpTokenizer(r"[A-Za-zÀ-ÿ0-9]+")
QUESTION_WORDS = {"apa", "siapa", "kapan", "dimana", "mengapa", "kenapa", "bagaimana", "berapa"}
PREPOSITIONS = {"di", "ke", "dari", "pada", "dengan", "untuk", "oleh", "dalam"}
CONJUNCTIONS = {"dan", "atau", "tetapi", "karena", "sehingga"}
COMMON_VERBS = {
    "terjadi", "dilakukan", "melakukan", "menyebabkan", "mengakibatkan", "mencegah",
    "menghindari", "melindungi", "menjauhi", "menuju", "evakuasi", "gunakan",
    "menggunakan", "berlindung", "menyelamatkan", "menyiapkan", "mengetahui"
}
COMMON_ADJECTIVES = {"besar", "kecil", "tinggi", "rendah", "kuat", "aman", "rawan", "berbahaya"}

def simple_pos_tag(text):
    tagged = []
    for token in TOKENIZER.tokenize(text.lower()):
        if token in QUESTION_WORDS:
            tag = "WH"
        elif token.isdigit():
            tag = "CD"
        elif token in PREPOSITIONS:
            tag = "IN"
        elif token in CONJUNCTIONS:
            tag = "CC"
        elif token in COMMON_VERBS or re.match(r"^(me|ber|ter|di|pe)\w+", token):
            tag = "VB"
        elif token in COMMON_ADJECTIVES or re.match(r"^(ke|ter)\w+an$", token):
            tag = "JJ"
        elif token.endswith(("nya", "an", "i")):
            tag = "NN"
        else:
            tag = "NN"
        tagged.append((token, tag))
    return tagged

GRAMMAR = r"""
    WH_PHRASE: {<WH><NN|VB|JJ>*}
    NOUN_PHRASE: {<NN><NN|JJ|CD>*}
    VERB_PHRASE: {<VB><NN|JJ|IN>*}
    PREP_PHRASE: {<IN><NN>+}
"""

def shallow_parse(text):
    tagged = simple_pos_tag(text)
    parser = RegexpParser(GRAMMAR)
    tree = parser.parse(tagged)
    return {
        "pos_tags": tagged,
        "chunks": [(subtree.label(), " ".join(word for word, _ in subtree.leaves()))
                   for subtree in tree.subtrees() if subtree.label() != "S"]
    }
