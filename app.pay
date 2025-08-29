import os
import requests
from flask import Flask, request

app = Flask(__name__)

# التوكن والـ ID نجيبهم من Environment Variables
TELEGRAM_TOKEN = os.getenv("8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c")
CHAT_ID = os.getenv("624881400")

@app.route('/')
def home():
    return "🚀 Bot is running on Render!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if data.get("condition") == "3 شروط":
        message = f"✅ اكتملت الشروط الثلاثة\n⏰ الوقت: {data.get('time')}\n💵 السعر: {data.get('price')}"
        send_telegram(message)
    return "ok"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg}
    requests.post(url, json=payload)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
