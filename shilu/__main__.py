"""Single-user loopback web app. Run: python3 -m shilu."""
import argparse
import io
import json
import os
import secrets
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .core import Conflict, Store, article, markdown, scan
from .config import load_env, public_model_config


class Server(ThreadingHTTPServer):
    def __init__(self, address, store):
        super().__init__(address, Handler)
        self.store = store
        self.token = secrets.token_urlsafe(32)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Do not log transcript content or session tokens.

    def reply(self, data, status=200, kind="application/json; charset=utf-8", filename=None):
        if not isinstance(data, bytes):
            data = (json.dumps(data, ensure_ascii=False) if kind.startswith("application/json") else data).encode()
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if filename:
            self.send_header("Content-Disposition", 'attachment; filename="%s"' % filename)
        self.end_headers()
        self.wfile.write(data)

    def allowed(self):
        port = self.server.server_port
        hosts = {"127.0.0.1:%s" % port, "localhost:%s" % port}
        if self.headers.get("Host") not in hosts:
            self.reply({"error": "Local access only"}, 403)
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://" + h for h in hosts}:
            self.reply({"error": "Cross-origin request rejected"}, 403)
            return False
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            self.reply({"error": "Cross-site request rejected"}, 403)
            return False
        return True

    def do_GET(self):
        if not self.allowed():
            return
        path = urlparse(self.path).path
        if path in ("/", "/app.js", "/style.css"):
            name = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}[path]
            kind = {"/": "text/html", "/app.js": "text/javascript", "/style.css": "text/css"}[path]
            return self.reply((Path(__file__).parent / "static" / name).read_bytes(), kind=kind + "; charset=utf-8")
        if path == "/api/session":
            return self.reply({"token": self.server.token, **public_model_config()})
        if self.headers.get("X-Shilu-Token") != self.server.token:
            return self.reply({"error": "Reload to establish a local session"}, 403)
        if path == "/api/projects":
            return self.reply({"items": [{k: p[k] for k in ("id", "revision", "config", "updated_at", "review")}
                                         for p in self.server.store.list()]})
        parts = path.strip("/").split("/")
        try:
            if len(parts) == 3 and parts[:2] == ["api", "projects"]:
                p = self.server.store.get(parts[2])
                return self.reply({"project": p, "scan": scan(p["human"] or (p["engine"] or {}).get("sections", []))})
        except KeyError:
            pass
        self.reply({"error": "Not found"}, 404)

    def do_POST(self):
        if not self.allowed():
            return
        if self.headers.get("X-Shilu-Token") != self.server.token:
            return self.reply({"error": "Reload to establish a local session"}, 403)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 16 * 1024 * 1024:
                return self.reply({"error": "Request size must be below 16 MB"}, 413)
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("Expected JSON")
            b = json.loads(self.rfile.read(size))
            if not isinstance(b, dict):
                raise ValueError("Expected JSON object")
            store = self.server.store
            path = urlparse(self.path).path
            if path == "/api/projects":
                return self.reply({"project": store.create(b["config"], b["transcript"])}, 201)
            if path == "/api/import":
                p = b["project"]
                return self.reply({"project": store.create(p["config"], p["transcript"], imported=p)}, 201)
            parts = path.strip("/").split("/")
            if len(parts) != 4 or parts[:2] != ["api", "projects"]:
                return self.reply({"error": "Not found"}, 404)
            pid, action = parts[2:]
            rev = b["revision"]
            if action == "save":
                p = store.save(pid, rev, b["config"], b["sections"])
            elif action == "generate":
                p = store.draft(pid, rev, b["mode"])
            elif action == "review":
                if b.get("confirmed") is not True:
                    raise ValueError("请确认已逐节核对原稿与脱敏")
                p = store.review(pid, rev, b["reviewer"])
            elif action == "backup":
                p = store.get(pid)
                if p["revision"] != rev:
                    raise Conflict("稿件已更新，请重新载入")
                return self.reply(p, filename="shilu-project.json")
            elif action == "preview":
                p = store.get(pid)
                return self.reply(article(p), kind="text/html; charset=utf-8")
            elif action == "export":
                p = store.export(pid, rev)
                out = io.BytesIO()
                with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
                    z.writestr("index.html", article(p))
                    z.writestr("article.md", markdown(p))
                    # Public delivery contains only edited text, never source transcripts or reviewer identity.
                    z.writestr("article.json", json.dumps({"schema_version": 1,
                        "title": p["config"]["title"], "author": p["config"]["author"],
                        "date": p["config"]["date"], "occasion": p["config"]["occasion"],
                        "sections": [{"title": s["title"], "body": s["body"]} for s in p["human"]]}, ensure_ascii=False, indent=2))
                return self.reply(out.getvalue(), kind="application/zip", filename="shilu-article.zip")
            else:
                return self.reply({"error": "Unknown action"}, 404)
            self.reply({"project": p, "scan": scan(p["human"] or (p["engine"] or {}).get("sections", []))})
        except Conflict as e:
            self.reply({"error": str(e)}, 409)
        except (ValueError, KeyError, TypeError) as e:
            self.reply({"error": str(e)}, 400)
        except Exception:
            self.reply({"error": "操作失败，原有内容保留。请检查配置后重试。"}, 500)


def main():
    parser = argparse.ArgumentParser(description="Shilu Studio — local speech recap workbench")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", default=os.environ.get("SHILU_DATA_DIR", "./workspace"))
    parser.add_argument("--env-file", default=os.environ.get("SHILU_ENV_FILE", ".env"))
    args = parser.parse_args()
    load_env(args.env_file)
    server = Server(("127.0.0.1", args.port), Store(Path(args.data_dir) / "shilu.sqlite3"))
    print("Shilu Studio: http://127.0.0.1:%d" % server.server_port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
