import requests
from flask import Flask, request

app = Flask(__name__)

# ✅ بيانات التوكن والـ ID للتليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# 🔹 إرسال رسالة للتليجرام
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        r = requests.post(url, json=payload)
        print("📤 Telegram response:", r.text, flush=True)
    except Exception as e:
        print("⚠️ Telegram error:", e, flush=True)

# 🔹 Webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print("📩 Webhook received:", data, flush=True)

    signal = data.get("signal", "")

    # ✅ شرط بسيط: أي إشارة يرسلها TradingView
    if signal.upper() == "CALL":
        message = "📈 إشارة CALL (كول)"
    elif signal.upper() == "PUT":
        message = "📉 إشارة PUT (بوت)"
    else:
        message = f"⚠️ إشارة غير معروفة: {signal}"

    print("✅ Sending message:", message, flush=True)
    send_telegram(message)

    return {"status": "ok"}
