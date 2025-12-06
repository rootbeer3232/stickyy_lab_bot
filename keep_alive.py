import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Healthcheck endpoint
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            # Anything else = 404
            self.send_response(404)
            self.end_headers()

    def do_HEAD(self):
        # UptimeRobot uses HEAD requests for HTTP monitors
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    # Stop the default noisy logging
    def log_message(self, format, *args):
        return


def run_server():
    # Use the platform PORT if set, otherwise default to 8080
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"[keep_alive] HTTP health server running on port {port}, path /health")
    server.serve_forever()


def keep_alive():
    thread = Thread(target=run_server)
    thread.daemon = True
    thread.start()
