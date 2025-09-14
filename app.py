from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os
from collections import defaultdict
import json
import re
import hashlib
import time
import threading
import logging
import random

# ---------------------- إعداد اللوج ----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------- إعداد التليجرام ----------------------
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

def send_telegram_alert(symbol: str, signal: str, timestamp: datetime):
    """إرسال تنبيه إلى التليجرام بشكل منسق مع رموز مميزة"""
    signal_lower = signal.lower()

    if "bullish" in signal_lower:
        prefix = "🟢⬆️ إشارة صعودية"
    elif "bearish" in signal_lower:
        prefix = "🔴⬇️ إشارة هبوطية"
    else:
        prefix = "🚨 إشارة جديدة"

    message = (
        f"{prefix}\n"
        f"الرمز: {symbol}\n"
        f"الإشارة: {signal}\n"
        f"التوقيت: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    try:
        resp = requests.post(
            TELEGRAM_URL,
            data={"chat_id": CHAT_ID, "text": message}
        )
        if resp.status_code == 200:
            log.info(f"📤 تم إرسال تنبيه للتليجرام: {message}")
        else:
            log.warning(f"⚠️ فشل إرسال التليجرام: {resp.status_code} - {resp.text}")
    except Exception as e:
        log.exception(f"❌ خطأ أثناء إرسال التنبيه للتليجرام: {e}")

# ---------------------- إعداد التطبيق ----------------------
app = Flask(__name__)

TIMEZONE_OFFSET = 3  # +3 للتوقيت السعودي
REQUIRED_SIGNALS = 2
WINDOW_MINUTES = 3

# تخزين الإشارات
signal_mapping = defaultdict(dict)      # hash -> {signal, symbol, first_seen}
duplicate_signals = {}                  # hash -> last_seen

# ---------------------- وظائف المساعدة ----------------------
def normalize_message(msg: str) -> str:
    return re.sub(r"\s+", " ", msg.strip().lower())

def hash_signal(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()

def cleanup_signals():
    """تنظيف الإشارات القديمة"""
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=WINDOW_MINUTES)
    removed = []

    for h, meta in list(signal_mapping.items()):
        if meta.get("first_seen") and meta["first_seen"] < cutoff:
            removed.append(h)
            del signal_mapping[h]

    for h, last_seen in list(duplicate_signals.items()):
        if last_seen < cutoff:
            removed.append(h)
            del duplicate_signals[h]

    if removed:
        log.info(f"🧹 تنظيف: تم إزالة {len(removed)} إشارات منتهية")

# ---------------------- خيط التنظيف ----------------------
def cleanup_worker(interval_seconds=30):
    log.info(f"🧰 بدء cleanup_worker بمعدل كل {interval_seconds} ثانية")
    while True:
        try:
            cleanup_signals()
        except Exception as e:
            log.exception(f"خطأ في cleanup_worker: {e}")
        time.sleep(interval_seconds)

# ---------------------- نقطة الاستقبال ----------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        raw_data = request.get_data(as_text=True)
        log.info(f"🌐 طلب وارد: POST /webhook - Content-Type: {request.content_type}")
        log.info(f"📨 بيانات webhook ({len(raw_data)} chars): {raw_data}")

        # استخراج النصوص
        parts = raw_data.strip().split("\n")
        if len(parts) < 2:
            return jsonify({"status": "error", "msg": "invalid payload"}), 400

        signal_text = normalize_message(parts[0])
        symbol = parts[1].strip().upper()
        now = datetime.utcnow()

        log.info(f"🔍 معالجة: {signal_text}\n {symbol}")

        content_hash = hash_signal(signal_text + symbol)

        # تحقق من التكرار
        if content_hash in duplicate_signals:
            first_seen = signal_mapping.get(content_hash, {}).get("first_seen")
            last_seen = duplicate_signals.get(content_hash)
            age = (now - last_seen).total_seconds() if last_seen else None
            log.info(
                f"⏭️ إشارة مكررة (hash): {content_hash} "
                f"- first_seen={first_seen} - last_seen={last_seen} - age_s={age} - سيتم تجاهلها"
            )
            return jsonify({"status": "duplicate"}), 200

        # تخزين الإشارة
        signal_mapping[content_hash] = {
            "signal": signal_text,
            "symbol": symbol,
            "first_seen": now,
        }
        duplicate_signals[content_hash] = now

        log.info(f"✅ خزّننا إشارة {signal_text} لـ {symbol} (hash={content_hash})")

        # إرسال للتليجرام
        send_telegram_alert(symbol, signal_text, now)

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        log.exception(f"❌ خطأ في /webhook: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 500

# ---------------------- نقطة الدخول ----------------------
if __name__ == '__main__':
    # تشغيل عامل التنظيف بالخلفية
    threading.Thread(target=cleanup_worker, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
