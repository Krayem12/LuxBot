from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# 🔹 بيانات التليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# ✅ إرسال رسالة للتليجرام
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        r = requests.post(url, json=payload)
        print("📤 Payload to Telegram:", payload)
        print("📥 Telegram response:", r.status_code, r.text)
    except Exception as e:
        print("❌ خطأ أثناء إرسال التليجرام:", e)

# ✅ إرسال POST خارجي
def send_post_request(message, indicators):
    url = "https://backend-thrumming-moon-2807.fly.dev/sendMessage"
    payload = {
        "type": message,
        "extras": {
            "indicators": indicators
        }
    }
    try:
        r = requests.post(url, json=payload)
        print("📤 Payload to external POST:", payload)
        print("📥 Response:", r.status_code, r.text)
    except Exception as e:
        print("❌ خطأ أثناء إرسال POST:", e)

# ✅ مسار الترحيب
@app.route("/", methods=["GET"])
def home():
    return "🟢 LuxAlgo Webhook Bot is running!"

# ✅ استقبال الويب هوك
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=False, silent=True)
        
        if not data:
            data_text = request.data.decode("utf-8")
            print("✅ Received raw webhook:", data_text)
            send_telegram(f"📊 Raw alert:\n{data_text}")
            return jsonify({"status": "raw_alert_sent"}), 200

        print("✅ Received webhook JSON:", data)
        alerts = data.get("alerts", [])

        if not alerts:
            return jsonify({"status": "no_alerts"}), 400

        # معالجة كل التنبيهات
        for alert in alerts:
            indicator = alert.get("indicator", "N/A")
           # signal = alert.get("signal", "N/A")
            message = alert.get("message", "N/A")
            ticker = alert.get("ticker", "N/A")
            open_price = alert.get("open", "N/A")
            high = alert.get("high", "N/A")
            low = alert.get("low", "N/A")
            close = alert.get("close", "N/A")
            volume = alert.get("volume", "N/A")
            barcolor = alert.get("barcolor", "N/A")
            bar_index = alert.get("bar_index", "N/A")
            hour = alert.get("hour", "N/A")
            minute = alert.get("minute", "N/A")

            telegram_message = (
                f"🚨 Signal Alert\n"
                f"🔹 Ticker: {ticker}\n"
                f"🔹 Indicator: {indicator}\n"
                f"🔹 Signal: {signal}\n"
                f"🔹 Message: {message}\n"
                f"🔹 OHLC: {open_price}/{high}/{low}/{close}\n"
                f"🔹 Volume: {volume}\n"
                f"🔹 Barcolor: {barcolor}\n"
                f"🔹 Bar Index: {bar_index} | Time: {hour}:{minute}"
            )

            # إرسال للـ POST الخارجي
            send_post_request(telegram_message, indicator)

            # إرسال للتليجرام
            send_telegram(telegram_message)

        return jsonify({"status": "alerts_sent"}), 200

    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

# ✅ تشغيل التطبيق مع المنفذ المرن
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
