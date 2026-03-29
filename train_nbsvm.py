import pandas as pd
import numpy as np
import re
import string
import pickle

from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer


# ------------------------------
# Load dataset
# ------------------------------

train = pd.read_csv("C:\\Users\\hp\\Desktop\\aishield4for\\aishieldforher\\jigsaw-toxic-comment-classification-challenge\\train.csv")

COMMENT = "comment_text"

train[COMMENT] = train[COMMENT].fillna("unknown")

print("Dataset loaded:", train.shape)

# ------------------------------
# Labels
# ------------------------------

label_cols = [
    "toxic",
    "severe_toxic",
    "obscene",
    "threat",
    "insult",
    "identity_hate"
]

# ------------------------------
# Tokenization
# ------------------------------

re_tok = re.compile(f'([{string.punctuation}])')

def tokenize(s):
    return re_tok.sub(r' \1 ', s).split()

# ------------------------------
# TF-IDF Vectorizer
# ------------------------------

vec = TfidfVectorizer(
    ngram_range=(1,2),
    tokenizer=tokenize,
    token_pattern=None,
    min_df=3,
    max_df=0.9,
    strip_accents="unicode",
    use_idf=True,
    smooth_idf=True,
    sublinear_tf=True
)

print("Vectorizing text...")

trn_term_doc = vec.fit_transform(train[COMMENT])

# ------------------------------
# Naive Bayes Feature Equation
# ------------------------------

def pr(y_i, y, x):
    p = x[y==y_i].sum(0)
    return (p+1) / ((y==y_i).sum()+1)


def get_mdl(y, x):

    y = y.values

    r = np.log(pr(1,y,x) / pr(0,y,x))

    model = LogisticRegression(
        C=4,
        dual=True,
        solver="liblinear",
        max_iter=1000
    )

    x_nb = x.multiply(r)

    return model.fit(x_nb, y), r


# ------------------------------
# Train model for each label
# ------------------------------

models = {}
ratios = {}

for label in label_cols:

    print("Training:", label)

    m, r = get_mdl(train[label], trn_term_doc)

    models[label] = m
    ratios[label] = r


# ------------------------------
# Save models
# ------------------------------

pickle.dump(models, open("models/nbsvm_models.pkl","wb"))
pickle.dump(ratios, open("models/ratios.pkl","wb"))
pickle.dump(vec, open("models/vectorizer.pkl","wb"))

print("Models saved successfully")