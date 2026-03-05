"""Aliyun Function Compute (FC3) HTTP Trigger Handler.

Routes:
  GET  /health  — liveness check
  POST /parse   — upload PDF, extract text + AI key-info
  POST /score   — match cached resume against a job description

FC3 HTTP Trigger Event Structure:
{
    "version": "v1",
    "rawPath": "/parse",
    "httpMethod": "POST",
    "headers": {...},
    "queryStringParameters": {...},
    "body": "...",
    "isBase64Encoded": false
}
"""
import base64
import json
import re
from io import BytesIO
from typing import Any

from cache import get_cache, set_cache
from extractor import extract_key_info
from parser import compute_md5, extract_text_from_pdf
from scorer import score_resume


# ── Response Helpers ──────────────────────────────────────────────────────────

def _json_response(status_code: int, body: Any) -> dict:
    """Create a FC3 HTTP trigger response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }


def _error_response(status_code: int, message: str) -> dict:
    """Create an error response."""
    return _json_response(status_code, {"error": message})


# ── Route Handlers ────────────────────────────────────────────────────────────

def handle_health() -> dict:
    """GET /health - Liveness check."""
    return _json_response(200, {"status": "ok"})


def handle_parse(event: dict) -> dict:
    """POST /parse - Upload PDF and extract key info."""
    # Parse multipart form data
    content_type = event.get("headers", {}).get("content-type", "")
    if not content_type:
        content_type = event.get("headers", {}).get("Content-Type", "")

    if "multipart/form-data" not in content_type.lower():
        return _error_response(400, "Content-Type must be multipart/form-data")

    # Extract boundary from content-type
    boundary_match = re.search(r"boundary=([^\s;]+)", content_type)
    if not boundary_match:
        return _error_response(400, "Invalid multipart form data: missing boundary")

    boundary = boundary_match.group(1).strip('"')

    # Get body
    body = event.get("body", "")
    is_base64 = event.get("isBase64Encoded", False)

    if is_base64:
        body_bytes = base64.b64decode(body)
    else:
        body_bytes = body.encode("utf-8") if isinstance(body, str) else body

    # Parse multipart data
    file_bytes = _extract_file_from_multipart(body_bytes, boundary)
    if file_bytes is None:
        return _error_response(400, "No file provided in multipart form data")

    # Validate PDF
    if not file_bytes.startswith(b"%PDF"):
        return _error_response(400, "Only PDF files are supported")

    file_hash = compute_md5(file_bytes)

    # Check cache
    cached = get_cache(file_hash)
    if cached:
        return _json_response(200, {**cached, "file_hash": file_hash, "cache_hit": True})

    # Extract text
    raw_text = extract_text_from_pdf(file_bytes)
    if not raw_text:
        return _error_response(422, "Could not extract text from PDF (may be a scanned image)")

    # AI extraction
    extracted = extract_key_info(raw_text)

    data = {"raw_text": raw_text, "extracted": extracted}
    set_cache(file_hash, data)

    return _json_response(200, {**data, "file_hash": file_hash, "cache_hit": False})


def _extract_file_from_multipart(body_bytes: bytes, boundary: str) -> bytes | None:
    """Extract file content from multipart form data."""
    boundary_bytes = f"--{boundary}".encode("utf-8")
    parts = body_bytes.split(boundary_bytes)

    for part in parts[1:]:  # Skip first empty part
        if part.strip() in (b"", b"--", b"--\r\n"):
            continue

        # Split headers and content
        header_end = part.find(b"\r\n\r\n")
        if header_end == -1:
            continue

        headers = part[:header_end].decode("utf-8", errors="ignore")
        content = part[header_end + 4:]

        # Remove trailing CRLF or --
        if content.endswith(b"\r\n"):
            content = content[:-2]

        # Check if this part contains a file
        if "filename=" in headers:
            return content

    return None


def handle_score(event: dict) -> dict:
    """POST /score - Match resume against job description."""
    # Parse JSON body
    body = event.get("body", "")
    is_base64 = event.get("isBase64Encoded", False)

    if is_base64:
        body = base64.b64decode(body).decode("utf-8")

    try:
        data = json.loads(body) if body else {}
    except json.JSONDecodeError:
        return _error_response(400, "Invalid JSON body")

    file_hash = data.get("file_hash", "").strip()
    job_description = data.get("job_description", "").strip()

    if not file_hash:
        return _error_response(400, "file_hash is required")
    if not job_description:
        return _error_response(400, "job_description is required")

    cached = get_cache(file_hash)
    if not cached:
        return _error_response(404, "Resume not found. Please upload and parse the resume first.")

    result = score_resume(cached["raw_text"], job_description)
    return _json_response(200, result)


# ── Main Handler ──────────────────────────────────────────────────────────────

def handler(event: dict | bytes, context: Any) -> dict:
    """FC3 HTTP trigger entry point.

    Args:
        event: HTTP trigger event (dict) or raw bytes (event function invocation)
        context: FC context (not used in this implementation)

    Returns:
        HTTP response dict with statusCode, headers, body
    """
    # Handle bytes event (direct invocation / test function)
    if isinstance(event, bytes):
        try:
            event = json.loads(event.decode("utf-8"))
        except json.JSONDecodeError:
            return _error_response(400, "Invalid JSON event data")

    # Ensure event is a dict
    if not isinstance(event, dict):
        return _error_response(400, f"Expected dict or bytes, got {type(event).__name__}")

    # Debug: log the event structure (check FC logs)
    print(f"[DEBUG] Received event keys: {list(event.keys())}")
    print(f"[DEBUG] Event: {json.dumps(event, default=str)[:2000]}")

    # Handle CORS preflight
    # FC3 may put httpMethod in different locations
    http_method = (
        event.get("httpMethod") or
        event.get("requestContext", {}).get("http", {}).get("method") or
        "GET"
    ).upper()
    print(f"[DEBUG] HTTP method: {http_method}")

    if http_method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            },
            "body": "",
        }

    # Route request
    # FC3 may use rawPath or path in different locations
    path = (
        event.get("rawPath") or
        event.get("path") or
        event.get("requestContext", {}).get("http", {}).get("path") or
        "/"
    )
    print(f"[DEBUG] Path: {path}")

    # Remove trailing slash for matching
    path = path.rstrip("/") or "/"

    try:
        if path == "/health" and http_method == "GET":
            return handle_health()

        if path == "/parse" and http_method == "POST":
            return handle_parse(event)

        if path == "/score" and http_method == "POST":
            return handle_score(event)

        # 404 for unknown routes
        return _error_response(404, f"Not Found: {path}")

    except Exception as e:
        # Log error for debugging
        import traceback
        traceback.print_exc()
        return _error_response(500, f"Internal Server Error: {str(e)}")


# ── Local Development ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    """Run a simple HTTP server for local development."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import sys

    class LocalHandler(BaseHTTPRequestHandler):
        def _handle(self, method: str):
            # Read body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b""

            # Build FC event
            event = {
                "httpMethod": method,
                "rawPath": self.path.split("?")[0],
                "headers": dict(self.headers),
                "body": body.decode("utf-8") if body else "",
                "isBase64Encoded": False,
            }

            # Handle request
            response = handler(event, None)

            # Send response
            self.send_response(response["statusCode"])
            for key, value in response.get("headers", {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(response["body"].encode("utf-8") if isinstance(response["body"], str) else response["body"])

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def do_OPTIONS(self):
            self._handle("OPTIONS")

        def log_message(self, format, *args):
            print(f"[{self.log_date_time_string()}] {format % args}")

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    print(f"Starting local development server on http://0.0.0.0:{port}")
    print("Routes: GET /health, POST /parse, POST /score")

    server = HTTPServer(("0.0.0.0", port), LocalHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
