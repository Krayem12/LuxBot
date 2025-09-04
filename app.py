from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

# 🔹 بيانات التليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# 🔹 إرسال رسالة للتليجرام
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("خطأ أثناء إرسال التليجرام:", e)

# 🔹 إرسال POST خارجي
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

# ✅ أقوى الإشارات لكل مؤشر
STRONG_SIGNALS = {
    "Signals & Overlays": ["bullish_confirmation+", "bearish_confirmation+"],
    "Price Action Concepts": ["bullish_ibos+", "bearish_ibos+"],
    "Oscillator Matrix": ["strong_bullish_confluence", "strong_bearish_confluence"]
}

# تخزين آخر وقت لكل إشارة
signal_store = {}

# ✅ معالجة التنبيهات
def process_alerts(alerts):
    global signal_store
    now = datetime.utcnow()
    
    # إزالة أي إشارات أقدم من 15 دقيقة
    for key in list(signal_store.keys()):
        if now - signal_store[key]["time"] > timedelta(minutes=15):
            del signal_store[key]
    
    # تحديث المتجر بالإشارات الجديدة
    for alert in alerts:
        indicator = alert.get("indicator")
        signal = alert.get("signal")
        if indicator in STRONG_SIGNALS and signal in STRONG_SIGNALS[indicator]:
            signal_store[indicator] = {"signal": signal, "time": now}
    
    # التحقق من وجود إشارتين أو أكثر من مؤشرات مختلفة
    if len(signal_store) >= 2:
        indicators_list = " + ".join([f"{ind}: {signal_store[ind]['signal']}" for ind in signal_store])
        message = f"🚀 Signals Confirmed ({len(signal_store)} Indicators)\n📊 {indicators_list}"
        send_post_request(message, indicators_list)
        send_telegram(message)
        return True
    return False

# ✅ استقبال الويب هوك
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        # التعامل مع JSON حتى لو كان Content-Type غير مضبوط
        if request.is_json:
            data = request.get_json()
        else:
            data = request.get_data(as_text=True)
            import json
            try:
                data = json.loads(data)
            except:
                return jsonify({"status": "invalid_json"}), 400

        print("Received webhook:", data)

        alerts = data.get("alerts", [])
        if alerts:
            triggered = process_alerts(alerts)
            if triggered:
                return jsonify({"status": "alert_sent"}), 200
            else:
                return jsonify({"status": "not_enough_signals"}), 200
        else:
            return jsonify({"status": "no_alerts"}), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
