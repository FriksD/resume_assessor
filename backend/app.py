"""Flask application entry point.

Routes:
  GET  /health  — liveness check
  POST /parse   — upload PDF, extract text + AI key-info
  POST /score   — match cached resume against a job description

Aliyun FC HTTP trigger entry point: handler(environ, start_response)
"""
from flask import Flask, jsonify, request
from flask_cors import CORS

from cache import get_cache, set_cache
from extractor import extract_key_info
from parser import compute_md5, extract_text_from_pdf
from scorer import score_resume

app = Flask(__name__)
CORS(app)  # Allow all origins (GitHub Pages → FC)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return jsonify({"status": "ok"})


# ── Parse ─────────────────────────────────────────────────────────────────────

@app.post("/parse")
def parse():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported"}), 400

    file_bytes = file.read()
    file_hash = compute_md5(file_bytes)

    # Return cached result if available
    cached = get_cache(file_hash)
    if cached:
        return jsonify({**cached, "file_hash": file_hash, "cache_hit": True})

    # Extract text
    raw_text = extract_text_from_pdf(file_bytes)
    if not raw_text:
        return jsonify({"error": "Could not extract text from PDF (may be a scanned image)"}), 422

    # AI extraction
    extracted = extract_key_info(raw_text)

    data = {"raw_text": raw_text, "extracted": extracted}
    set_cache(file_hash, data)

    return jsonify({**data, "file_hash": file_hash, "cache_hit": False})


# ── Score ─────────────────────────────────────────────────────────────────────

@app.post("/score")
def score():
    body = request.get_json(silent=True) or {}
    file_hash = body.get("file_hash", "").strip()
    job_description = body.get("job_description", "").strip()

    if not file_hash:
        return jsonify({"error": "file_hash is required"}), 400
    if not job_description:
        return jsonify({"error": "job_description is required"}), 400

    cached = get_cache(file_hash)
    if not cached:
        return jsonify({"error": "Resume not found. Please upload and parse the resume first."}), 404

    result = score_resume(cached["raw_text"], job_description)
    return jsonify(result)


# ── Aliyun FC entry point ─────────────────────────────────────────────────────

def handler(environ, start_response):
    """WSGI-compatible handler for Aliyun Function Compute HTTP trigger."""
    # Handle CORS preflight requests
    if environ.get('REQUEST_METHOD') == 'OPTIONS':
        headers = [
            ('Content-Type', 'text/plain'),
            ('Access-Control-Allow-Origin', '*'),
            ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
            ('Access-Control-Allow-Headers', 'Content-Type'),
        ]
        start_response('200 OK', headers)
        return [b'']

    # Custom start_response to inject CORS headers
    def cors_start_response(status, headers, exc_info=None):
        headers.append(('Access-Control-Allow-Origin', '*'))
        headers.append(('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'))
        headers.append(('Access-Control-Allow-Headers', 'Content-Type'))
        return start_response(status, headers, exc_info)

    return app.wsgi_app(environ, cors_start_response)


if __name__ == "__main__":
    # Local development only
    app.run(host="0.0.0.0", port=5000, debug=True)
