#!/usr/bin/env python3
"""
nocache_server.py — einfacher Dev-Webserver ohne Caching.

Start:
  python nocache_server.py 8000
oder:
  python nocache_server.py            # default 8000

Dann im Browser:
  http://localhost:8000/
"""

from __future__ import annotations

import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler


class NoCacheHandler(SimpleHTTPRequestHandler):
    # Optional: etwas weniger "lautes" Logging
    # def log_message(self, format, *args):
    #     pass

    def end_headers(self) -> None:
        # Harte No-Cache-Header (wirken auch bei Proxies)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")

        # Hilft manchmal bei CORS/ServiceWorker-Experimente (optional)
        # self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        # self.send_header("Cross-Origin-Embedder-Policy", "require-corp")

        super().end_headers()

    def send_head(self):
        """
        SimpleHTTPRequestHandler sendet sonst gern 304, wenn If-Modified-Since passt.
        Wir neutralisieren das, indem wir Conditional-Header ignorieren.
        """
        # Temporär Conditional Headers entfernen
        saved_ims = self.headers.get("If-Modified-Since")
        saved_inm = self.headers.get("If-None-Match")
        if saved_ims is not None:
            del self.headers["If-Modified-Since"]
        if saved_inm is not None:
            del self.headers["If-None-Match"]

        try:
            return super().send_head()
        finally:
            # Wiederherstellen (nicht zwingend nötig, aber sauber)
            if saved_ims is not None:
                self.headers["If-Modified-Since"] = saved_ims
            if saved_inm is not None:
                self.headers["If-None-Match"] = saved_inm


def main() -> None:
    port = 8000
    if len(sys.argv) >= 2:
        port = int(sys.argv[1])

    server = ThreadingHTTPServer(("0.0.0.0", port), NoCacheHandler)
    print(f"Serving (NO-CACHE) on http://localhost:{port}/  (Ctrl+C to stop)")
    server.serve_forever()


if __name__ == "__main__":
    main()