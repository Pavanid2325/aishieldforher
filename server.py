from flask import Flask, request, jsonify
from toxicity_predict import predict_toxicity
import toxicity_predict

app = Flask(__name__)

def compute_threat_score(scores):
    return (
        0.4 * scores["threat"] +
        0.2 * scores["toxic"] +
        0.15 * scores["insult"] +
        0.15 * scores["obscene"] +
        0.1 * scores["severe_toxic"]
    )

@app.route("/predict", methods=["POST"])
def predict():
    data = request.json
    text = data["text"]

    scores = toxicity_predict.predict_toxicity(text)
    threat_score = compute_threat_score(scores)

    print("Received from Android:", text)
    print("Threat Score:", threat_score)

    return jsonify({"threat_score": threat_score})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)