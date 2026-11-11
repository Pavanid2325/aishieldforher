import os
import pickle
import re
import string
import sys

# define tokenizer exactly as in training
re_tok = re.compile(f'([{string.punctuation}])')

def tokenize(s):
    return re_tok.sub(r' \1 ', s).split()

# inject tokenizer into __main__
sys.modules['__main__'].tokenize = tokenize


# now load models
models = pickle.load(open(os.path.join(os.getenv("MODEL_ROOT", "."), "models/nbsvm_models.pkl"),"rb"))
ratios = pickle.load(open(os.path.join(os.getenv("MODEL_ROOT", "."), "models/ratios.pkl"),"rb"))
vectorizer = pickle.load(open(os.path.join(os.getenv("MODEL_ROOT", "."), "models/vectorizer.pkl"),"rb"))

label_cols = [
    "toxic",
    "severe_toxic",
    "obscene",
    "threat",
    "insult",
    "identity_hate"
]


def predict_toxicity(text):

    text_vec = vectorizer.transform([text])

    results = {}

    for label in label_cols:

        r = ratios[label]
        m = models[label]

        text_nb = text_vec.multiply(r)

        prob = m.predict_proba(text_nb)[0][1]

        results[label] = float(prob)

    return results