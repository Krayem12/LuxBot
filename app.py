from flask import Flask, request, jsonify
import requests
import time

app = Flask(__name__)

TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# تخزين الإشارات مؤقتًا
signal_memory = []

# مدة الاحتفاظ بالإشارات بالثواني (15 دقيقة)
TIME_WINDOW = 15 * 60

# أقوى إشارات لكل مؤشر
STRONG_SIGNALS = {
    "Signals & Overlays": ["bullish_confirmation+", "bearish_confirmation+"],
    "Price Action Concepts": ["bullish_ibos", "bearish_ibos", "bullish_sbos", "bearish_sbos"],
    "Oscillator Matrix": ["strong_bullish_confluence", "strong_bearish_confluence", "regular_bullish_hyperwave_signal", "regular_bearish_hyperwave_signal"]
}

# إرسال رسالة للتليجرام
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
    payload = {"type": message, "extras": {"indicators": indicators}}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("خطأ أثناء إرسال POST:", e)

# معالجة الإشارات
def process_alerts(alerts):
    global signal_memory
    now = time.time()
    
    # إزالة الإشارات القديمة
    signal_memory = [s for s in signal_memory if now - s["time"] <= TIME_WINDOW]

    new_signals = []
    for alert in alerts:
        indicator = alert.get("indicator")
        signal_name = alert.get("signal")
        # تحقق إذا الإشارة من أقوى الإشارات
        if indicator in STRONG_SIGNALS and signal_name in STRONG_SIGNALS[indicator]:
            new_signals.append({"indicator": indicator, "signal": signal_name, "time": now})
    
    # إضافة الإشارات الجديدة للذاكرة
    signal_memory.extend(new_signals)

    # التحقق من وجود إشارتين أو أكثر من مؤشرات مختلفة
    indicators_triggered = list({s["indicator"] for s in signal_memory})
    if len(indicators_triggered) >= 2:
        indicators_list = " + ".join(indicators_triggered)
        telegram_message = f"🚀 Confirmed Signals ({len(indicators_triggered)} indicators)\n📊 {indicators_list}"
        send_post_request(telegram_message, indicators_list)
        send_telegram(telegram_message)
        # بعد الإرسال نصفر الذاكرة لتبدأ العد من جديد
        signal_memory = []
        return True
    return False

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(silent=True)
        if not data:
            raw = request.data.decode("utf-8").strip()
            import json
            data = json.loads(raw) if raw.startswith("{") and raw.endswith("}") else {}
        
        alerts = data.get("alerts", [])
        if alerts:
            triggered = process_alerts(alerts)
            return jsonify({"status": "alert_sent" if triggered else "not_enough_signals"}), 200
        return jsonify({"status": "no_alerts"}), 200
    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
