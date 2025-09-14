import os
import re
import time
import json
import hashlib
import logging
import threading
from datetime import datetime, timedelta
from collections import defaultdict

import requests
from flask import Flask, request, jsonify

# ---------------------- إعدادات عامة ----------------------
RESET_TIMEOUT = 15 * 60  # 15 دقيقة
CLEANUP_INTERVAL = 30    # كل 30 ثانية
DUPLICATE_WINDOW_SECONDS = 90  # نافذة التكرار (مثلاً 90 ثانية)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")

# ---------------------- تسجيل (Logging) ----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------- Flask ----------------------
app = Flask(__name__)

# ---------------------- هياكل البيانات ----------------------
signal_memory = defaultdict(lambda: {"signals": [], "timestamp": datetime.utcnow()})
duplicate_signals = {}  # content_hash -> last_seen
signal_mapping = {}     # content_hash -> {symbol, signal, first_seen}
request_cache = {}

state_lock = threading.RLock()

# ---------------------- أدوات ----------------------
def compute_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

def send_telegram_message(message: str) -> bool:
    if not TELEGRAM_TOKEN or not CHAT_ID:
        log.warning("⚠️ لم يتم ضبط TELEGRAM_TOKEN أو CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                log.info("📤 تم إرسال الإشارة إلى Telegram بنجاح")
                return True
            else:
                log.error(f"❌ فشل إرسال Telegram: {data}")
        else:
            log.error(f"❌ فشل إرسال Telegram - status={resp.status_code}, body={resp.text}")
    except Exception as e:
        log.exception(f"❌ خطأ في الاتصال بـ Telegram: {e}")
    return False

def cleanup_signals():
    now = datetime.utcnow()
    with state_lock:
        for symbol in list(signal_memory.keys()):
            if (now - signal_memory[symbol]["timestamp"]).total_seconds() > RESET_TIMEOUT:
                log.info(f"🧹 تصفير إشارات {symbol}")
                del signal_memory[symbol]
        for h in list(duplicate_signals.keys()):
            if (now - duplicate_signals[h]).total_seconds() > RESET_TIMEOUT:
                log.info(f"🧹 إزالة hash قديم {h}")
                duplicate_signals.pop(h, None)
                signal_mapping.pop(h, None)

# ---------------------- خيط التنظيف الخلفي ----------------------
def cleanup_worker(interval_seconds=CLEANUP_INTERVAL):
    log.info(f"🧰 بدء cleanup_worker بمعدل كل {interval_seconds}s")
    while True:
        try:
            cleanup_signals()
        except Exception as e:
            log.exception(f"خطأ في cleanup_worker: {e}")
        time.sleep(interval_seconds)

threading.Thread(target=cleanup_worker, daemon=True).start()

# ---------------------- نقاط النهاية ----------------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "signals": {k: v["signals"] for k, v in signal_memory.items()},
        "duplicates": len(duplicate_signals),
    })

@app.route("/debug", methods=["GET"])
def debug_state():
    with state_lock:
        return jsonify({
            "signal_memory": {k: {"signals": v["signals"], "timestamp": v["timestamp"].isoformat()} for k,v in signal_memory.items()},
            "duplicate_signals": {h: str(ts) for h, ts in duplicate_signals.items()},
            "signal_mapping": signal_mapping,
        })

@app.route("/webhook", methods=["POST"])
def webhook():
    content_type = request.headers.get("Content-Type", "").lower()
    log.info(f"🌐 طلب وارد: POST /webhook - Content-Type: {content_type}")

    try:
        if "application/json" in content_type:
            data = request.json
            raw_message = json.dumps(data, ensure_ascii=False)
        else:
            raw_message = request.data.decode("utf-8", errors="ignore")
    except Exception as e:
        log.exception("❌ فشل قراءة البيانات")
        return ("Bad Request", 400)

    log.info(f"📨 بيانات webhook ({len(raw_message)} chars): {raw_message}")

    now = datetime.utcnow()
    with state_lock:
        content_hash = compute_hash(raw_message)
        if content_hash in duplicate_signals:
            first_seen = signal_mapping.get(content_hash, {}).get('first_seen')
            last_seen = duplicate_signals.get(content_hash)
            age = (now - last_seen).total_seconds() if last_seen else None
            if age is not None and age < DUPLICATE_WINDOW_SECONDS:
                log.info(f"⏭️ إشارة مكررة (hash): {content_hash} - first_seen={first_seen} - last_seen={last_seen} - age_s={age} - سيتم تجاهلها")
                return ("Duplicate", 200)

        # تحديث السجلات
        duplicate_signals[content_hash] = now
        if content_hash not in signal_mapping:
            signal_mapping[content_hash] = {"first_seen": now, "raw": raw_message}

    # 🟢 إرسال إلى Telegram
    success = send_telegram_message(raw_message)
    if not success:
        log.warning("⚠️ لم يتم إرسال الرسالة إلى Telegram")

    return ("OK", 200)

# ---------------------- نقطة الدخول ----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
