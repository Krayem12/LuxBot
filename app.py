#!/usr/bin/env python3
from flask import Flask, request, jsonify
import os
import datetime
import requests
import logging

app = Flask(__name__)

# -----------------------
# Configuration (env)
# -----------------------
TIMEZONE_OFFSET = int(os.getenv("TIMEZONE_OFFSET", "3"))  # +3 hours (Saudi)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")              # e.g. 123:ABC...
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")          # chat id or channel id
EXTERNAL_URL = os.getenv("EXTERNAL_URL", "")              # e.g. https://backend.example.com/sendMessage

# SEND_MODE: "both" / "telegram" / "external" / "none"
SEND_MODE = os.getenv("SEND_MODE", "none").lower()

# Simple access control: if WEBHOOK_TOKEN set, require X-ACCESS-TOKEN header to match
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN")

# -----------------------
# Logging
# -----------------------
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("webhook")

# -----------------------
# Helpers
# -----------------------
def get_sa_time() -> str:
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE_OFFSET)).strftime("%Y-%m-%d %H:%M:%S")

def send_telegram(text: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning(f"[{get_sa_time()}] Telegram not configured (TELEGRAM_TOKEN/TELEGRAM_CHAT_ID missing).")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.error(f"[{get_sa_time()}] Telegram send failed {resp.status_code}: {resp.text}")
        else:
            logger.info(f"[{get_sa_time()}] Sent to Telegram")
    except Exception as e:
        logger.error(f"[{get_sa_time()}] Telegram exception: {e}")

def send_external(text: str) -> None:
    if not EXTERNAL_URL:
        logger.warning(f"[{get_sa_time()}] External URL not configured (EXTERNAL_URL missing).")
        return
    try:
        resp = requests.post(EXTERNAL_URL, data=text.encode("utf-8"), headers={"Content-Type":"text/plain"}, timeout=10)
        if resp.status_code != 200:
            logger.error(f"[{get_sa_time()}] External send failed {resp.status_code}: {resp.text}")
        else:
            logger.info(f"[{get_sa_time()}] Sent to external server")
    except Exception as e:
        logger.error(f"[{get_sa_time()}] External exception: {e}")

def dispatch_message(final_text: str) -> None:
    """Dispatch according to SEND_MODE"""
    if SEND_MODE == "telegram":
        send_telegram(final_text)
    elif SEND_MODE == "external":
        send_external(final_text)
    elif SEND_MODE == "both":
        send_telegram(final_text)
        send_external(final_text)
    else:
        logger.info(f"[{get_sa_time()}] SEND_MODE={SEND_MODE} -> not sending (message logged only)")

def check_auth() -> bool:
    """Return True if request allowed. If WEBHOOK_TOKEN is not set -> allow."""
    if not WEBHOOK_TOKEN:
        return True
    header = request.headers.get("X-ACCESS-TOKEN", "")
    return header == WEBHOOK_TOKEN

# -----------------------
# Webhook endpoint
# -----------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    if not check_auth():
        logger.warning(f"[{get_sa_time()}] Unauthorized request blocked.")
        return jsonify({"status":"error","reason":"unauthorized"}), 401

    # try JSON "message" first, otherwise raw body string
    data = request.get_json(silent=True)
    msg = None
    if data and isinstance(data, dict):
        msg = data.get("message")
        # if no explicit message, try to find any string value
        if not msg:
            for v in data.values():
                if isinstance(v, str) and v.strip():
                    msg = v.strip()
                    break

    if not msg:
        # fallback to raw body text
        raw = request.data.decode("utf-8").strip()
        if raw:
            msg = raw

    if not msg:
        return jsonify({"status":"error","reason":"no message found"}), 400

    sa_time = get_sa_time()
    final_text = f"{msg}\n⏰ {sa_time}"

    # Always log
    logger.info(f"[{sa_time}] Received message: {final_text}")

    # Dispatch according to SEND_MODE
    dispatch_message(final_text)

    return jsonify({"status":"success","message":final_text,"send_mode":SEND_MODE}), 200

# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    # for production use a proper WSGI server (gunicorn/uvicorn)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
