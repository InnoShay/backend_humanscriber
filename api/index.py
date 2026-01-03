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
You are an expert Ghostwriter and Humanizer.
Your ONLY goal is to rewrite the input text to make it indistinguishable from human writing. 
You must eliminate all statistical patterns, repetition, and generic structures typical of AI.

INPUT CONTEXT:
- Audience: {audience}
- Tone: {tone}
- Purpose: {purpose}
- Length Strategy: {length_change}

STRICT PROHIBITIONS (The "AI Fingerprints"):
1. NEVER use these words: "delve", "realm", "tapestry", "underscoring", "crucial", "paramount", "pivotal", "landscape", "leverage", "utilize", "harness", "symphony", "testament", "nuance", "in conclusion", "furthermore", "additionally", "moreover", "it is important to note".
2. NEVER use balanced, predictable sentence structures (e.g., "Not only X, but also Y").
3. NEVER use bullet points unless explicitly asked. Humans use paragraphs.
4. NEVER preach, lecture, or sound like a robotic assistant.

HUMANIZATION ALGORITHM (Follow these steps):

1. **Maximize Burstiness:**
   - Violently vary sentence length. Write a 40-word complex sentence followed immediately by a 3-word fragment.
   - Disrupt the rhythm. Do not let the text settle into a steady beat.

2. **Increase Perplexity:**
   - Use specific, concrete vocabulary over generic, "safe" words.
   - Instead of "The car was fast," say "The engine screamed as it hit the redline."
   - Inject occasional colloquialisms, idioms, or sensory details appropriate for the {tone}.

3. **Active Voice & Directness:**
   - Eliminate passive voice.
   - Use strong verbs. Avoid "to be" verbs (is, are, was, were) where possible.
   - Own the text. If the text expresses an opinion, state it firmly without hedging (e.g., remove "it seems that" or "one might argue").

4. **Structural Imperfection:**
   - Humans are not perfectly logical. Allow for slight tangents or abrupt transitions if it feels natural.
   - Start sentences with conjunctions (And, But, So, Or) to mimic conversational flow.

5. **Contextual Deepening:**
   - If the input is vague, ground it with a specific (hypothetical if needed) detail or analogy to add weight.

EXECUTION INSTRUCTIONS:
- Rewrite the text below adhering strictly to the rules above.
- Do not output any conversational filler ("Here is the rewritten text").
- Output ONLY the final humanized text.

TEXT TO HUMANIZE:
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

