"""Local development server. Run: python -m rag.server

This is a single-user prototype, not a public multi-user or payment server.
"""
import argparse
import json
import mimetypes
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .ingest import ROOT
from .retrieve import inventory, search, source_page
from .tutor import ProviderError, configured, generate
from .workshops import catalog, get_workshop

GENERATION_SLOTS = threading.BoundedSemaphore(2)
STATIC_FILES = {"index.html", "styles.css", "content.js", "app.js", "knowledge.html", "knowledge.css", "knowledge.js", "learning.html", "learning.css", "learning.js"}


class Handler(BaseHTTPRequestHandler):
    server_version = "EnterView/0.2"

    def log_message(self, format, *args):
        # Avoid logging student questions, answers, or API credentials.
        pass

    def send_bytes(self, status, data, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_json(self, status, value):
        self.send_bytes(status, json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def trusted_request(self):
        host = self.headers.get("Host", "")
        expected = {f"localhost:{self.server.server_port}", f"127.0.0.1:{self.server.server_port}"}
        if host not in expected:
            self.send_json(403, {"error": "Use this server through localhost or 127.0.0.1."})
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{h}" for h in expected}:
            self.send_json(403, {"error": "Cross-origin requests are not accepted."})
            return False
        return True

    def do_GET(self):
        if not self.trusted_request():
            return
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        params = parse_qs(parsed.query)
        try:
            if path == "/favicon.ico":
                return self.send_bytes(204, b"", "image/x-icon")
            if path == "/api/status":
                info = inventory()
                return self.send_json(200, {"ready": True, "tutor_configured": configured(), "totals": info["totals"], "retrieval": info["retrieval"], "built_at": info["built_at"]})
            if path == "/api/library":
                info = inventory()
                return self.send_json(200, info)
            if path == "/api/workshops":
                return self.send_json(200, {"workshops": catalog()})
            if path.startswith("/api/workshops/"):
                item = get_workshop(path.removeprefix("/api/workshops/"))
                return self.send_json(200 if item else 404, item or {"error": "Workshop not found."})
            if path == "/api/search":
                query = params.get("q", [""])[0]
                doc_ids = params.get("document")
                return self.send_json(200, {"results": search(query, doc_ids=doc_ids, track=params.get("track", [None])[0])})
            match = re.fullmatch(r"/api/pages/([a-f0-9]{16})/(\d+)", path)
            if match:
                page = source_page(match[1], int(match[2]))
                return self.send_json(200 if page else 404, page or {"error": "Page not found."})
            relative = path.lstrip("/") or "learning.html"
            file = (ROOT / relative).resolve()
            allowed_pdf = file.is_relative_to((ROOT / "docs").resolve()) and file.suffix.lower() == ".pdf"
            if not (relative in STATIC_FILES or allowed_pdf) or not file.is_relative_to(ROOT) or not file.is_file():
                return self.send_json(404, {"error": "Not found."})
            mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            if mime.startswith("text/") or file.suffix == ".js":
                mime += "; charset=utf-8"
            self.send_bytes(200, file.read_bytes(), mime)
        except FileNotFoundError as error:
            self.send_json(503, {"error": str(error)})
        except ValueError as error:
            self.send_json(400, {"error": str(error)})

    def do_POST(self):
        if not self.trusted_request():
            return
        if self.path != "/api/tutor":
            return self.send_json(404, {"error": "Not found."})
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.send_json(415, {"error": "Use application/json."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 48000:
                return self.send_json(413, {"error": "Request is empty or too large."})
            body = json.loads(self.rfile.read(length))
            query = body.get("query", "")
            answer = body.get("answer", "")
            history = body.get("history", [])
            docs = body.get("documents")
            track = body.get("track")
            mode = body.get("mode", "explain")
            workshop_id = body.get("workshop_id")
            allowed_pages = None
            if workshop_id is not None:
                if not isinstance(workshop_id, str) or len(workshop_id) > 100:
                    raise ValueError("Invalid workshop.")
                workshop = get_workshop(workshop_id)
                if not workshop:
                    raise ValueError("Workshop not found.")
                allowed_pages = workshop["allowed_pages"]
            if not isinstance(query, str) or not 2 <= len(query.strip()) <= 2000:
                raise ValueError("Enter a question of 2–2,000 characters.")
            if not isinstance(answer, str) or len(answer) > 10000:
                raise ValueError("Answer must be text of at most 10,000 characters.")
            if not isinstance(history, list) or len(history) > 6 or any(not isinstance(m, dict) or not isinstance(m.get("content"), str) or len(m["content"]) > 2500 for m in history):
                raise ValueError("Conversation history is invalid or too long.")
            if docs is not None and (not isinstance(docs, list) or len(docs) > 100 or any(not isinstance(d, str) or not re.fullmatch(r"[a-f0-9]{16}", d) for d in docs)):
                raise ValueError("Invalid source selection.")
            if track is not None and not isinstance(track, str):
                raise ValueError("Invalid track.")
            if not isinstance(mode, str):
                raise ValueError("Invalid mode.")
            if not GENERATION_SLOTS.acquire(blocking=False):
                return self.send_json(429, {"error": "Two tutor requests are already running. Please wait."})
            try:
                result = generate(query.strip(), mode=mode, doc_ids=docs, track=track, history=history, answer=answer, allowed_pages=allowed_pages)
            finally:
                GENERATION_SLOTS.release()
            self.send_json(200, result)
        except (ValueError, TypeError, AttributeError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error) if isinstance(error, ValueError) else "Invalid request body."})
        except ProviderError as error:
            self.send_json(502, {"error": str(error)})
        except FileNotFoundError as error:
            self.send_json(503, {"error": str(error)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    inventory()  # Fail early with an actionable message if indexing has not run.
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    print(f"EnterView: http://127.0.0.1:{args.port}/", flush=True)
    print(f"Hosted tutor: {'configured' if configured() else 'not configured; cited search is available'}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
