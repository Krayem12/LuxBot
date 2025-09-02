from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# ====== بيانات التليجرام ======
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# ====== دالة إرسال الرسائل ======
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=payload)

# ====== Webhook endpoint ======
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No JSON received"}), 400

        # ====== عداد الطبقات ======
        bullish_count = sum([
            data.get("bullish_confirmation") is True,
            data.get("regular_bullish_hyperwave_signal") is True,
            data.get("bullish_ichoch") is True
        ])

        bearish_count = sum([
            data.get("bearish_confirmation") is True,
            data.get("regular_bearish_hyperwave_signal") is True,
            data.get("bearish_ichoch") is True
        ])

        # ====== تحقق من شرطين أو أكثر ======
        message = ""
        if bullish_count >= 2:
            message = "Call"
        elif bearish_count >= 2:
            message = "Put"

        if message:
            symbol = data.get("symbol", "Unknown")
            send_telegram(f"LuxAlgo Signal: {symbol} -> {message}")

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

# ====== تشغيل السيرفر ======
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
