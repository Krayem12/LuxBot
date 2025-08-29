from flask import Flask, request
import requests

app = Flask(__name__)

# بيانات البوت
BOT_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(url, json=payload)
        print(response.text)
    except Exception as e:
        print("Error sending message:", e)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json or {}

    # قراءة بيانات الشمعة
    open_price = data.get("open")
    close_price = data.get("close")

    if open_price is not None and close_price is not None:
        if close_price > open_price:
            candle_type = "صاعدة"
        elif close_price < open_price:
            candle_type = "هابطة"
        else:
            candle_type = "محايدة"
    else:
        candle_type = "غير معروف"

    message = f"✅ إشعار من TradingView: أغلق شمعة {candle_type}!"
    send_telegram(message)
    return {"status": "success"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
