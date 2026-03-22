import json
import threading
import http.server

_ALLOWED_ORIGIN_PREFIXES = (
    "chrome-extension://",
    "moz-extension://",
    "edge-extension://",
)


def _origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    return any(origin.startswith(prefix) for prefix in _ALLOWED_ORIGIN_PREFIXES)


def _write_json(handler, status, payload, origin=None):
    handler.send_response(status)
    if origin and _origin_allowed(origin):
        handler.send_header("Access-Control-Allow-Origin", origin)
        handler.send_header("Vary", "Origin")
    handler.send_header("Content-Type", "application/json")
    handler.end_headers()
    handler.wfile.write(json.dumps(payload).encode("utf-8"))


def start_ext_server(queue, workflows_file, read_workflow_urls_fn, token_getter, logger=None):
    class Handler(http.server.BaseHTTPRequestHandler):
        def _unauthorized(self, origin, message="Unauthorized"):
            _write_json(self, 403, {"status": "error", "message": message}, origin)

        def _is_authed(self):
            token = token_getter()
            supplied = self.headers.get("X-Elvar-Token", "")
            return bool(token and supplied and supplied == token)

        def do_OPTIONS(self):
            origin = self.headers.get("Origin", "")
            if not _origin_allowed(origin):
                self.send_response(403)
                self.end_headers()
                return

            self.send_response(200, "ok")
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "X-Elvar-Token, Content-Type")
            self.end_headers()

        def do_GET(self):
            origin = self.headers.get("Origin", "")
            if origin and not _origin_allowed(origin):
                return self._unauthorized(origin, "Disallowed origin")
            if not self._is_authed():
                return self._unauthorized(origin)

            if self.path != "/workflows":
                _write_json(self, 404, {"status": "error", "message": "Not found"}, origin)
                return

            try:
                workflows = read_workflow_urls_fn(workflows_file)
                _write_json(self, 200, {"workflows": workflows}, origin)
            except Exception as exc:
                if logger:
                    logger.exception("GET /workflows failed: %s", exc)
                _write_json(self, 500, {"status": "error", "message": "Internal error"}, origin)

        def do_POST(self):
            origin = self.headers.get("Origin", "")
            if origin and not _origin_allowed(origin):
                return self._unauthorized(origin, "Disallowed origin")
            if not self._is_authed():
                return self._unauthorized(origin)

            try:
                cl = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(cl)
                data = json.loads(raw.decode("utf-8")) if raw else {}
                action = data.get("action", "save_session")

                event = threading.Event()
                result = {"status": "ok"}

                if action == "save_session":
                    queue.put({"kind": "ext_import", "data": data, "event": event, "result": result})
                    event.wait(timeout=5.0)
                elif action == "launch_workflow":
                    queue.put({
                        "kind": "ext_launch",
                        "name": data.get("name"),
                        "incognito": data.get("incognito", False),
                        "new_window": data.get("new_window", False),
                        "specific_urls": data.get("specific_urls"),
                    })
                elif action == "add_to_workflow_dialog":
                    queue.put({"kind": "ext_add_dialog", "url": data.get("url"), "title": data.get("title")})
                elif action == "get_protected_urls":
                    queue.put({
                        "kind": "ext_get_protected",
                        "name": data.get("name"),
                        "password": data.get("password"),
                        "event": event,
                        "result": result,
                    })
                    event.wait(timeout=5.0)
                else:
                    result = {"status": "error", "message": "Unknown action"}

                status = 200 if result.get("status") == "ok" else 500
                _write_json(self, status, result, origin)
            except Exception as exc:
                if logger:
                    logger.exception("POST request failed: %s", exc)
                _write_json(self, 400, {"status": "error", "message": "Bad request"}, origin)

        def log_message(self, _format, *_args):
            return

    class Server(http.server.HTTPServer):
        allow_reuse_address = True

    try:
        with Server(("127.0.0.1", 31337), Handler) as httpd:
            if logger:
                logger.info("Extension API server listening on 127.0.0.1:31337")
            httpd.serve_forever()
    except Exception as exc:
        if logger:
            logger.exception("Extension API server failed: %s", exc)
