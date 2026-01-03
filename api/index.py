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

def build_editor_prompt(content, audience, tone, purpose, length_change):
    return f"""
You are a professional human editor.

Edit the text below according to these rules:

GLOBAL RULES:
- Preserve the original meaning exactly
- Do not add new facts or opinions
- Do not remove important details
- Do not mention AI, rewriting, or editing
- Do not use generic filler phrases

EDITING GOALS:
- Improve clarity and readability
- Improve sentence flow and transitions
- Vary sentence length naturally
- Reduce stiffness and repetition
- Use precise, concrete language

STYLE CONTEXT:
Audience: {audience}
Tone: {tone}
Purpose: {purpose}
Length change: {length_change}

TEXT TO EDIT:
{content}
""".strip()

@app.route("/humanize", methods=["POST"])
def humanize():
    data = request.get_json(silent=True)

    if not data or "content" not in data:
        return jsonify({"error": "Missing 'content'"}), 400

    content = data["content"]

    audience = data.get("audience", "general")
    tone = data.get("tone", "neutral")
    purpose = data.get("purpose", "explain")
    length_change = data.get("constraints", {}).get("length_change", "minimal")

    ai_model_key = data.get("ai_model", "flash")

    MODEL_REGISTRY = {
        "flash": "models/gemini-2.5-flash",
        "pro": "models/gemini-3-pro-preview"
    }

    if ai_model_key not in MODEL_REGISTRY:
        return jsonify({
            "error": "Invalid 'ai_model'",
            "allowed_values": list(MODEL_REGISTRY.keys())
        }), 400

    try:
        prompt = build_editor_prompt(
            content=content,
            audience=audience,
            tone=tone,
            purpose=purpose,
            length_change=length_change
        )

        model = genai.GenerativeModel(MODEL_REGISTRY[ai_model_key])
        result = model.generate_content(prompt)

        return jsonify({
            "content": result.text
        }), 200

    except Exception as e:
        print("Humanize error:", e)

        if ai_model_key == "pro":
            fallback_model = genai.GenerativeModel(
                "models/gemini-2.5-flash"
            )
            result = fallback_model.generate_content(prompt)
            return jsonify({
                "content": result.text
            }), 200

        return jsonify({"error": "Humanization failed"}), 500

