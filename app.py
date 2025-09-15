from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os
from collections import defaultdict
import json
import re
import hashlib

app = Flask(__name__)

# 🔹 إعداد التوقيت السعودي (UTC+3)
TIMEZONE_OFFSET = 3  # +3 ساعات للتوقيت السعودي

# 🔹 عدد الإشارات المطلوبة (ثابت: 3)
REQUIRED_SIGNALS = 3

# 🔹 تخزين الإشارات
signals_store = defaultdict(lambda: {"bullish": {}, "bearish": {}})
global_trend = {}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_to_telegram(message: str):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print("خطأ إرسال تلغرام:", e)

def hash_signal(signal_text: str):
    return hashlib.sha256(signal_text.encode()).hexdigest()

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_data(as_text=True).strip()
    lines = data.split("\n")
    if len(lines) < 2:
        return jsonify({"status": "ignored", "reason": "invalid format"}), 200

    signal_name = lines[0].strip()
    symbol = lines[1].strip()

    # 🔹 التعامل مع إشارات الاتجاه فقط
    if signal_name.lower().startswith("trend catcher"):
        new_trend = None
        if "bullish" in signal_name.lower():
            new_trend = "bullish"
        elif "bearish" in signal_name.lower():
            new_trend = "bearish"

        # تحقق إذا الاتجاه جديد أو تغيّر
        if symbol not in global_trend or global_trend[symbol] != new_trend:
            global_trend[symbol] = new_trend
            send_to_telegram(f"⚠️ تغير الاتجاه لـ {symbol}: {new_trend.upper()}")

        return jsonify({"status": "trend updated"}), 200

    # 🔹 تحديد الاتجاه (صعود/هبوط)
    direction = "bullish" if "bullish" in signal_name.lower() else "bearish"

    # التحقق من وجود اتجاه مسبق
    if symbol not in global_trend:
        return jsonify({"status": "ignored", "reason": "no global trend"}), 200

    if global_trend[symbol] != direction:
        return jsonify({"status": "ignored", "reason": "direction mismatch"}), 200

    # 🔹 حساب الإشارة وتخزينها
    signal_hash = hash_signal(signal_name)
    if signal_hash in signals_store[symbol][direction]:
        return jsonify({"status": "ignored", "reason": "duplicate"}), 200

    signals_store[symbol][direction][signal_hash] = signal_name

    # 🔹 تحقق من وصول العدد المطلوب
    if len(signals_store[symbol][direction]) >= REQUIRED_SIGNALS:
        msg = f"✅ تم تأكيد {REQUIRED_SIGNALS} إشارات {direction.upper()} لـ {symbol}\n"
        msg += "\n".join(signals_store[symbol][direction].values())
        send_to_telegram(msg)
        signals_store[symbol][direction].clear()

    return jsonify({"status": "stored"}), 200

if __name__ == "__main__":
    app.run(port=5000, debug=True)
