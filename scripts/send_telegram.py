#!/usr/bin/env python3
"""
Send text from stdin or a file to Telegram.
Usage: cat report.md | python scripts/send_telegram.py
       python scripts/send_telegram.py data/reports/2026-04-17.md
"""
import os
import sys
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
MAX_LEN = 4096


def send(text: str) -> None:
    chunks = [text[i:i + MAX_LEN] for i in range(0, len(text), MAX_LEN)]
    for chunk in chunks:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": chunk,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if not r.ok:
            print(f"Telegram error: {r.status_code} {r.text}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = open(sys.argv[1], encoding="utf-8").read()
    else:
        text = sys.stdin.read()

    if not text.strip():
        print("ERROR: empty message", file=sys.stderr)
        sys.exit(1)

    send(text)
    print("Sent.", file=sys.stderr)
