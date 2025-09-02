from flask import Flask, request
import requests

# تعريف التطبيق
app = Flask(__name__)

# بيانات التليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# آخر وقت شمعه
last_bar_time = None

# إرسال رسالة للتليجرام
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        print("Telegram send error:", e)

# Webhook endpoint
@app.route("/webhook", methods=["POST"])
def webhook():
    global last_bar_time

    if request.is_json:
        data = request.get_json()
    else:
        return {"status": "error", "message": "Content-Type must be application/json"}, 415

    signal = data.get("signal")
    price = data.get("price")
    bar_time = data.get("time")
    layers_confirmed = data.get("layers_confirmed", 0)

    # تحويل layers_confirmed إلى رقم
    try:
        layers_confirmed = int(layers_confirmed)
    except (ValueError, TypeError):
        layers_confirmed = 0

    # تحقق من تحقق شرطين أو أكثر
    if layers_confirmed < 2:
        return {"status": "skipped_not_enough_layers"}, 200

    # تجاهل إشعارات نفس الشمعة
    if bar_time == last_bar_time:
        return {"status": "skipped_duplicate"}, 200
    last_bar_time = bar_time

    # تحويل النص العربي
    signal_text = "كول" if signal == "CALL" else "بوت" if signal == "PUT" else signal
    message = f"📊 إشارة {signal_text}\nالسعر: {price}\nالوقت: {bar_time}"
    send_telegram(message)

    return {"status": "ok"}, 200

# تشغيل التطبيق (للاختبار محلي)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
