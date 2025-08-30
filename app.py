from flask import Flask, request
import requests

app = Flask(__name__)

# بيانات التوكن والتليجرام
BOT_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    print("Sending to Telegram:", payload)
    try:
        response = requests.post(url, json=payload)
        print("Telegram response:", response.text)
    except Exception as e:
        print("Error sending message:", e)

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
    except:
        data = None

    if not data:
        text = request.data.decode("utf-8")
        send_telegram(f"📩 إشعار نصي من TradingView: {text}")
        return {"status": "ok"}, 200

    # قراءة البيانات القادمة من TradingView
    signal = str(data.get("signal", "")).lower()
    open_price = data.get("open")
    close_price = data.get("close")

    # تحديد نوع الشمعة
    if open_price is not None and close_price is not None:
        if close_price > open_price:
            candle_type = "📈 صاعدة"
        elif close_price < open_price:
            candle_type = "📉 هابطة"
        else:
            candle_type = "➖ محايدة"
    else:
        candle_type = "❓ غير معروف"

    # رسالة البداية
    msg = "<b>🔔 LuxAlgo Alert</b>\n\n"
    msg += f"🕯 نوع الشمعة: {candle_type}\n"

    # مطابقة الإشارات مع LuxAlgo
    mapping = {
        "bullish": "✅ إشارة: صعود (Bullish)",
        "buy": "✅ إشارة: شراء",
        "bearish": "❌ إشارة: هبوط (Bearish)",
        "sell": "❌ إشارة: بيع",
        "exit_long": "📤 خروج من صفقة شراء",
        "exit_short": "📤 خروج من صفقة بيع",
        "confirmation_bullish": "🟢 تأكيد: صعود",
        "confirmation_bearish": "🔴 تأكيد: هبوط",
        "overbought": "🔴 حالة: Overbought",
        "oversold": "🟢 حالة: Oversold",
        "breakout": "⚡️ كسر مستوى (Breakout)",
        "liquidity_grab": "💧 سحب سيولة",
        "bos": "📊 Break of Structure",
        "choch": "🔄 Change of Character"
    }

    if signal in mapping:
        msg += mapping[signal] + "\n"

    # إضافة الأسعار لو موجودة
    if open_price is not None and close_price is not None:
        msg += f"\n💵 Open: {open_price}\n💵 Close: {close_price}"

    send_telegram(msg)
    return {"status": "success"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
