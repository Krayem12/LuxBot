from flask import Flask, request
import requests

app = Flask(__name__)

# 🔹 بيانات التليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# 🔹 تخزين آخر شمعة لتجنب التكرار
last_bar_time = None

# 🔹 إرسال رسالة للتليجرام
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            print(f"خطأ في إرسال التليجرام: {response.text}")
    except Exception as e:
        print(f"حدث خطأ: {e}")

# 🔹 استقبال POST من TradingView
@app.route("/webhook", methods=["POST"])
def webhook():
    global last_bar_time
    data = request.json

    # بيانات الإشعار من TradingView Custom Script
    signal = data.get("signal")          # CALL أو PUT
    price = data.get("price")
    bar_time = data.get("time")          # وقت الشمعة
    layers_confirmed = data.get("layers_confirmed", 0)  # عدد الطبقات المتحققة

    # تحقق من تحقق شرطين أو أكثر
    if layers_confirmed < 2:
        return {"status": "skipped_not_enough_layers"}, 200

    # تجاهل إشعارات نفس الشمعة
    if bar_time == last_bar_time:
        return {"status": "skipped_duplicate"}, 200
    last_bar_time = bar_time

    # تحويل CALL/PUT إلى كول/بوت
    signal_text = "كول" if signal == "CALL" else "بوت" if signal == "PUT" else signal

    message = f"📊 إشارة {signal_text}\nالسعر: {price}\nالوقت: {bar_time}"
    send_telegram(message)

    return {"status": "ok"}, 200

# 🔹 تشغيل السيرفر
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
