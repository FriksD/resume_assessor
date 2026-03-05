"""阿里云函数计算 FC3 HTTP 触发器入口。

路由:
  GET  /health  - 健康检查
  POST /parse   - 上传PDF，提取文本和关键信息
  POST /score   - 匹配简历与职位描述
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


# ── 响应辅助函数 ──────────────────────────────────────────────────────────

def _json_response(status_code: int, body: Any) -> dict:
    """构建 FC3 HTTP 触发器响应。"""
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
    """构建错误响应。"""
    return _json_response(status_code, {"error": message})


# ── 路由处理 ────────────────────────────────────────────────────────────

def handle_health() -> dict:
    """健康检查。"""
    return _json_response(200, {"status": "ok"})


def handle_parse(event: dict) -> dict:
    """上传PDF并提取关键信息。"""
    content_type = event.get("headers", {}).get("content-type", "")
    if not content_type:
        content_type = event.get("headers", {}).get("Content-Type", "")

    if "multipart/form-data" not in content_type.lower():
        return _error_response(400, "Content-Type must be multipart/form-data")

    boundary_match = re.search(r"boundary=([^\s;]+)", content_type)
    if not boundary_match:
        return _error_response(400, "Invalid multipart form data: missing boundary")

    boundary = boundary_match.group(1).strip('"')

    body = event.get("body", "")
    is_base64 = event.get("isBase64Encoded", False)

    if is_base64:
        body_bytes = base64.b64decode(body)
    else:
        body_bytes = body.encode("utf-8") if isinstance(body, str) else body

    file_bytes = _extract_file_from_multipart(body_bytes, boundary)
    if file_bytes is None:
        return _error_response(400, "No file provided in multipart form data")

    if not file_bytes.startswith(b"%PDF"):
        return _error_response(400, "Only PDF files are supported")

    file_hash = compute_md5(file_bytes)

    cached = get_cache(file_hash)
    if cached:
        return _json_response(200, {**cached, "file_hash": file_hash, "cache_hit": True})

    raw_text = extract_text_from_pdf(file_bytes)
    if not raw_text:
        return _error_response(422, "Could not extract text from PDF (may be a scanned image)")

    extracted = extract_key_info(raw_text)

    data = {"raw_text": raw_text, "extracted": extracted}
    set_cache(file_hash, data)

    return _json_response(200, {**data, "file_hash": file_hash, "cache_hit": False})


def _extract_file_from_multipart(body_bytes: bytes, boundary: str) -> bytes | None:
    """从 multipart 表单数据中提取文件内容。"""
    boundary_bytes = f"--{boundary}".encode("utf-8")
    parts = body_bytes.split(boundary_bytes)

    for part in parts[1:]:
        if part.strip() in (b"", b"--", b"--\r\n"):
            continue

        header_end = part.find(b"\r\n\r\n")
        if header_end == -1:
            continue

        headers = part[:header_end].decode("utf-8", errors="ignore")
        content = part[header_end + 4:]

        if content.endswith(b"\r\n"):
            content = content[:-2]

        if "filename=" in headers:
            return content

    return None


def handle_score(event: dict) -> dict:
    """匹配简历与职位描述。"""
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


# ── 阿里云FC3主入口 ──────────────────────────────────────────────────────────────

def handler(event: dict | bytes, context: Any) -> dict:
    """FC3 HTTP 触发器入口函数。"""
    if isinstance(event, bytes):
        try:
            event = json.loads(event.decode("utf-8"))
        except json.JSONDecodeError:
            return _error_response(400, "Invalid JSON event data")

    if not isinstance(event, dict):
        return _error_response(400, f"Expected dict or bytes, got {type(event).__name__}")

    print(f"[DEBUG] Received event keys: {list(event.keys())}")
    print(f"[DEBUG] Event: {json.dumps(event, default=str)[:2000]}")

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

    path = (
        event.get("rawPath") or
        event.get("path") or
        event.get("requestContext", {}).get("http", {}).get("path") or
        "/"
    )
    print(f"[DEBUG] Path: {path}")

    path = path.rstrip("/") or "/"

    try:
        if path == "/health" and http_method == "GET":
            return handle_health()

        if path == "/parse" and http_method == "POST":
            return handle_parse(event)

        if path == "/score" and http_method == "POST":
            return handle_score(event)

        return _error_response(404, f"Not Found: {path}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        return _error_response(500, f"Internal Server Error: {str(e)}")


# ── 本地调试 ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    """本地开发服务器。"""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import sys

    class LocalHandler(BaseHTTPRequestHandler):
        def _handle(self, method: str):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b""

            event = {
                "httpMethod": method,
                "rawPath": self.path.split("?")[0],
                "headers": dict(self.headers),
                "body": body.decode("utf-8") if body else "",
                "isBase64Encoded": False,
            }

            response = handler(event, None)

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
