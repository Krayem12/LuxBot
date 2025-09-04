from flask import Flask, request, jsonify
import requests
import time
from datetime import datetime, timedelta

app = Flask(__name__)

# 🔹 بيانات التليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# ⏱ مدة التجميع (15 دقيقة)
COLLECTION_INTERVAL = timedelta(minutes=15)

# ✅ إرسال رسالة للتليجرام
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("خطأ أثناء إرسال التليجرام:", e)

# إرسال POST خارجي
def send_post_request(message, indicators):
    url = "https://backend-thrumming-moon-2807.fly.dev/sendMessage"
    payload = {
        "type": message,
        "extras": {
            "indicators": indicators
        }
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("خطأ أثناء إرسال POST:", e)

# 🔹 تخزين الإشارات المجمعة
collected_signals = []
collection_start_time = None

# ✅ معالجة التنبيهات
def process_alerts(alerts):
    global collected_signals, collection_start_time
    current_time = datetime.utcnow()

    # بدء الفترة إذا لم تبدأ
    if collection_start_time is None or current_time - collection_start_time > COLLECTION_INTERVAL:
        collected_signals = []
        collection_start_time = current_time

    # إشارات قوية من كل مؤشر
    signals_mapping = {
        "Signals & Overlays": ["bullish_confirmation+", "bearish_confirmation+", "bullish_ichoch+"],
        "Price Action Concepts": ["bullish_ibos", "bearish_ibos", "bullish_sbos"],
        "Oscillator Matrix": ["strong_bullish_confluence", "strong_bearish_confluence", "regular_bullish_hyperwave_signal"]
    }

    for alert in alerts:
        indicator = alert.get("indicator")
        signal = alert.get("signal")
        if indicator in signals_mapping and signal in signals_mapping[indicator]:
            # تجنب تكرار نفس المؤشر
            if not any(s['indicator'] == indicator for s in collected_signals):
                collected_signals.append({"indicator": indicator, "signal": signal, "time": current_time})

    # تحقق من شرط الإرسال: إشارتان أو أكثر من مؤشرات مختلفة
    unique_indicators = set(s['indicator'] for s in collected_signals)
    if len(unique_indicators) >= 2:
        indicators_list = " + ".join(unique_indicators)
        telegram_message = f"🚀 Strong Signals Detected ({len(unique_indicators)} Confirmed)\nIndicators: {indicators_list}"
        send_post_request(telegram_message, indicators_list)
        send_telegram(telegram_message)
        # إعادة تعيين بعد الإرسال
        collected_signals = []
        collection_start_time = None
        return True

    return False

# ✅ استقبال الويب هوك
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("⚠️ Received raw webhook:", data)

        alerts = data.get("alerts", [])
        if alerts:
            triggered = process_alerts(alerts)
            if triggered:
                return jsonify({"status": "alert_sent"}), 200
            else:
                return jsonify({"status": "not_enough_signals"}), 200
        else:
            return jsonify({"status": "no_alerts"}), 400

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
