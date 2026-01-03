from flask import Flask, request, jsonify
import google.generativeai as genai
import os
import requests


app = Flask(__name__)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

MODEL_REGISTRY = {
    "flash": "models/gemini-2.5-flash",
    "pro": "models/gemini-3-flash-preview"
}

@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    prompt = data.get("prompt")
    ai_model_key = data.get("ai_model")

    if not prompt:
        return jsonify({"error": "Missing 'prompt'"}), 400

    if ai_model_key not in MODEL_REGISTRY:
        return jsonify({
            "error": "Invalid 'ai_model'",
            "allowed_values": list(MODEL_REGISTRY.keys())
        }), 400

    try:
        model_name = MODEL_REGISTRY[ai_model_key]
        model = genai.GenerativeModel(model_name)
        result = model.generate_content(prompt)

        return jsonify({
            "model_used": ai_model_key,
            "output": result.text
        }), 200

    except Exception as e:
        if ai_model_key == "pro":
            fallback_model = genai.GenerativeModel(
                "models/gemini-2.5-flash"
            )
            result = fallback_model.generate_content(prompt)
            return jsonify({
                "model_used": "flash_fallback",
                "output": result.text
            }), 200

        return jsonify({"error": "Generation failed"}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/score", methods=["POST"])
def score():
    data = request.get_json(silent=True)

    if not data or "text" not in data:
        return jsonify({"error": "Missing 'text'"}), 400

    text = data["text"]

    try:
        response = requests.post(
            "https://api.sapling.ai/api/v1/aidetect",
            json={
                "key": os.getenv("SAPLING_API_KEY"),
                "text": text
            },
            timeout=10
        )

        response.raise_for_status()
        result = response.json()

        raw_score = result.get("score")

        if raw_score is None:
            return jsonify({"error": "Invalid response from Sapling"}), 502

        ai_score = int(raw_score * 100)

        return jsonify({
            "score": ai_score
        }), 200

    except requests.exceptions.RequestException as e:
        print("Sapling API error:", e)
        return jsonify({"error": "Scoring failed"}), 500
