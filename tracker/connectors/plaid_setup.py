#!/usr/bin/env python3
"""One-time Plaid setup: connect your bank and get a PLAID_ACCESS_TOKEN.

Plaid normally requires you to build a web app to run their "Link" bank
login flow. This script is that web app, shrunk to one file:

    python tracker/connectors/plaid_setup.py --client-id XXX --secret YYY

It opens your browser to Plaid's bank-login window; after you log in to
your bank it prints the permanent access token. Run it on your own
computer (it needs a browser), not in a cloud shell.

Notes:
- Get client_id and secret at https://dashboard.plaid.com -> Developers
  -> Keys. Use the *Production* environment for a real bank ("Sandbox"
  only has fake banks). Pass --env sandbox to test with user_good /
  pass_good first.
- Some large banks (Chase, etc.) use OAuth and require an https redirect
  URI registered in the Plaid dashboard; a plain localhost flow may not
  work for those.
"""

from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

PAGE = """<!doctype html>
<html><head><title>Connect your bank</title>
<script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
</head><body style="font-family:sans-serif;padding:2rem">
<h2>Tracker &mdash; connect your bank</h2>
<p id="status">Opening Plaid Link&hellip;</p>
<script>
const handler = Plaid.create({
  token: "%LINK_TOKEN%",
  onSuccess: (public_token) => {
    fetch("/exchange", {method: "POST", body: public_token})
      .then(() => document.getElementById("status").textContent =
        "Done! Go back to your terminal for the access token. You can close this tab.");
  },
  onExit: (err) => {
    document.getElementById("status").textContent =
      err ? ("Link exited with error: " + JSON.stringify(err)) : "Link closed.";
  },
});
handler.open();
</script></body></html>"""


def plaid_post(host: str, path: str, body: dict) -> dict:
    r = requests.post(f"{host}{path}", json=body, timeout=30)
    if not r.ok:
        raise SystemExit(f"Plaid error {r.status_code}: {r.text}")
    return r.json()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--client-id", required=True)
    ap.add_argument("--secret", required=True)
    ap.add_argument("--env", default="production",
                    choices=["production", "sandbox"])
    ap.add_argument("--port", type=int, default=8455)
    args = ap.parse_args()

    host = f"https://{args.env}.plaid.com"
    creds = {"client_id": args.client_id, "secret": args.secret}

    link = plaid_post(host, "/link/token/create", {
        **creds,
        "client_name": "Daily tracker",
        "user": {"client_user_id": "tracker"},
        "products": ["transactions"],
        "country_codes": ["US"],
        "language": "en",
    })
    page = PAGE.replace("%LINK_TOKEN%", link["link_token"])

    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(page.encode())

        def do_POST(self):
            public_token = self.rfile.read(
                int(self.headers.get("Content-Length", 0))).decode().strip()
            self.send_response(200)
            self.end_headers()
            resp = plaid_post(host, "/item/public_token/exchange",
                              {**creds, "public_token": public_token})
            print("\n=== Success! Add these as GitHub repository secrets ===")
            print(f"PLAID_CLIENT_ID    = {args.client_id}")
            print("PLAID_SECRET       = (the secret you used)")
            print(f"PLAID_ACCESS_TOKEN = {resp['access_token']}")
            if args.env != "production":
                print(f"\n(Also set a repo *variable* PLAID_ENV = {args.env})")
            done.set()

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Opening {url} — log in to your bank there.")
    webbrowser.open(url)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    done.wait()
    server.shutdown()


if __name__ == "__main__":
    main()
