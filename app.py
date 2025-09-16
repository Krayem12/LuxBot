from flask import Flask, request, jsonify
import datetime
import requests
import hashlib
from collections import defaultdict
import re

app = Flask(__name__)

# ===== إعداد التوقيت السعودي =====
TIMEZONE_OFFSET = 3  # +3 ساعات للتوقيت السعودي

# ===== إعدادات التليجرام =====
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# ===== إعداد تخزين الإشارات =====
signals_store = defaultdict(lambda: {"bullish": {}, "bearish": {}})
general_trend = {}  # الاتجاه العام لكل رمز
MIN_SIGNALS_TO_CONFIRM = 2  # عدد إشارات الدخول المطلوبة للتأكيد

# ===== تحميل قائمة الأسهم المسموح بها من ملف =====
def load_allowed_stocks(file_path="stocks.txt"):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return set(line.strip().upper() for line in f if line.strip())
    except FileNotFoundError:
        print(f"⚠️ ملف الأسهم {file_path} غير موجود!")
        return set()

ALLOWED_STOCKS = load_allowed_stocks()

# ===== دالة ارسال رسالة للتليجرام =====
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ أرسلنا للتليجرام")
        else:
            print(f"⚠️ فشل ارسال التليجرام ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"⚠️ خطأ أثناء ارسال التليجرام: {e}")

# ===== دالة إنشاء هاش فريد للإشارة =====
def hash_signal(signal_text: str):
    return hashlib.sha256(signal_text.encode()).hexdigest()

# ===== دالة استخراج الرمز مع التحقق من الأسهم المسموح بها =====
def extract_symbol(text: str) -> str:
    match = re.search(r"\b([A-Z]{2,10}\d{0,3})(USDT)?\b", text)
    if match:
        symbol = match.group(0).upper()
        if symbol in ALLOWED_STOCKS:
            return symbol
    return "UNKNOWN"

# ===== دالة معالجة الإشارة =====
def process_signal(signal_text: str):
    signal_text = signal_text.replace("\n", " ").strip()
    symbol = extract_symbol(signal_text)

    sa_time = (datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE_OFFSET)).strftime("%Y-%m-%d %H:%M:%S")

    if symbol == "UNKNOWN":
        print(f"⏭️ تجاهل إشارة لأن الرمز غير موجود ⏰ {sa_time}: {signal_text}")
        return

    # ===== تحديد الاتجاه العام Trend Catcher =====
    trend_catcher = None
    if "Trend Catcher Bullish" in signal_text:
        trend_catcher = "bullish"
    elif "Trend Catcher Bearish" in signal_text:
        trend_catcher = "bearish"

    if trend_catcher:
        prev_trend = general_trend.get(symbol)
        if prev_trend != trend_catcher:
            general_trend[symbol] = trend_catcher
            signals_store[symbol].clear()  # مسح الإشارات السابقة
            print(f"🟢 {symbol}: تغير الاتجاه من {prev_trend or 'N/A'} → {trend_catcher}")
            print(f"🧹 {symbol}: تم مسح إشارات الدخول السابقة")
        return  # اتجاه عام فقط، لا يخزن كإشارة دخول

    # ===== تجاهل أي إشارة دخول قبل استقبال الاتجاه =====
    if symbol not in general_trend:
        print(f"⏭️ تجاهل إشارة دخول لـ {symbol} لأنها وصلت قبل تحديد الاتجاه ⏰ {sa_time}: {signal_text}")
        return

    # ===== تحديد اتجاه الإشارة العادية =====
    direction = None
    if "bullish" in signal_text.lower() or "Oversold Hyper Wave" in signal_text or "upward" in signal_text:
        direction = "bullish"
    elif "bearish" in signal_text.lower() or "Overbought Hyper Wave" in signal_text or "downward" in signal_text:
        direction = "bearish"

    # تجاهل الإشارات المخالفة للاتجاه العام
    if direction != general_trend[symbol]:
        print(f"⏭️ تجاهل إشارة {signal_text} لـ {symbol} لأنها لا تتوافق مع الاتجاه العام {general_trend[symbol]}")
        return

    # ===== هاش فريد للإشارة =====
    signal_hash = hash_signal(signal_text)
    if signal_hash in signals_store[symbol][direction]:
        print(f"⏭️ إشارة مكررة تجاهل ⏰ {sa_time}: {signal_text}")
        return

    # ===== إضافة الإشارة لمخزن الإشارات =====
    signals_store[symbol][direction][signal_hash] = signal_text
    print(f"✅ خزّننا إشارة {direction} لـ {symbol} ⏰ {sa_time}: {signal_text}")

    # ===== تحقق من عدد الإشارات المختلفة بنفس الاتجاه =====
    if len(signals_store[symbol][direction]) >= MIN_SIGNALS_TO_CONFIRM:
        signals_list = list(signals_store[symbol][direction].values())
        total_signals = len(signals_list)
        current_trend = general_trend[symbol]
        arrow_emoji = "📈" if direction == "bullish" else "📉"
        color_emoji = "🔵" if direction == "bullish" else "🔴"

        message = f"{arrow_emoji} {symbol} - {color_emoji} تأكيد إشارة قوية {direction}\n"
        message += f"📊 الاتجاه العام الحالي: {current_trend}\n"
        message += "📌 الإشارات المجمعة:\n"
        for sig in signals_list:
            message += f"• {sig}\n"
        message += f"🔢 عدد الإشارات: {total_signals}\n"
        message += f"{color_emoji} متوقع حركة {direction} من {total_signals} إشارات مختلفة"

        send_telegram(message)
        signals_store[symbol][direction].clear()

# ===== مسار webhook =====
@app.route("/webhook", methods=["POST"])
def webhook():
    signal_text = request.get_data(as_text=True)
    sa_time = (datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE_OFFSET)).strftime("%Y-%m-%d %H:%M:%S")
    print(f"🌐 طلب وارد: POST /webhook")
    print(f"⏰ وقت الاستلام (السعوديه): {sa_time}")
    print(f"📨 بيانات webhook ({len(signal_text)} chars): {signal_text}")
    process_signal(signal_text)
    return jsonify({"status": "ok"}), 200

# ===== تشغيل السيرفر =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
