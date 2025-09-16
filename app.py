from flask import Flask, request, jsonify
import datetime
import hashlib
from collections import defaultdict
import re
import requests

app = Flask(__name__)

# ===== إعداد التوقيت السعودي =====
TIMEZONE_OFFSET = 3  # +3 ساعات للتوقيت السعودي

# ===== إعدادات التليجرام =====
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavjhtGmAxRg0TwLPdGxaVx8"
TELEGRAM_CHAT_ID = "6788824696"

# ===== التخزين =====
signals_store = defaultdict(lambda: {"bullish": {}, "bearish": {}})
general_trend = {}         # الاتجاه العام لكل رمز
trend_confirmation = {}    # تأكيد الاتجاه لكل رمز

# ===== إرسال رسالة للتليجرام =====
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"❌ خطأ في إرسال التليجرام: {e}")

# ===== دالة تجيب الوقت السعودي =====
def get_sa_time():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE_OFFSET)).strftime("%Y-%m-%d %H:%M:%S")

# ===== معالجة الإشارات =====
def process_signal(symbol: str, signal_text: str):
    sa_time = get_sa_time()

    # ===== الاتجاه العام (Trend Catcher / Trend Tracer) =====
    trend_catcher = None
    if "Trend Catcher Bullish" in signal_text or "Trend Tracer Bullish" in signal_text:
        trend_catcher = "bullish"
    elif "Trend Catcher Bearish" in signal_text or "Trend Tracer Bearish" in signal_text:
        trend_catcher = "bearish"

    if trend_catcher:
        prev_trend = general_trend.get(symbol)
        if prev_trend != trend_catcher:
            general_trend[symbol] = trend_catcher
            # 🗑️ مسح إشارات الدخول القديمة فقط عند تغير الاتجاه العام
            signals_store[symbol] = {"bullish": {}, "bearish": {}}

            emoji = "🟢📈" if trend_catcher == "bullish" else "🔴📉"
            arabic_trend = "صعود" if trend_catcher == "bullish" else "هبوط"
            message = (
                f"📢 تحديث الاتجاه العام\n"
                f"{emoji} الرمز: {symbol}\n"
                f"📊 الاتجاه الحالي: {arabic_trend}\n"
                f"⏰ الوقت: {sa_time}\n"
                f"⚠️ إشارات الدخول السابقة تم مسحها تلقائيًا"
            )
            send_telegram(message)
            print(f"⚠️ {symbol}: تغير الاتجاه العام {prev_trend} → {trend_catcher}")
        return

    # ===== تأكيد الاتجاه (Trend Crossing Up / Down) =====
    trend_confirm = None
    if "Trend Crossing Up" in signal_text:
        trend_confirm = "bullish"
    elif "Trend Crossing Down" in signal_text:
        trend_confirm = "bearish"

    if trend_confirm:
        if symbol not in general_trend:
            print(f"⏭️ تجاهل تأكيد الاتجاه {signal_text} لـ {symbol} لأنه لم يحدد اتجاه عام بعد")
            return

        if trend_confirm != general_trend[symbol]:
            print(f"⏭️ تجاهل تأكيد الاتجاه {signal_text} لـ {symbol} لأنه يعاكس الاتجاه العام {general_trend[symbol]}")
            return

        prev_confirm = trend_confirmation.get(symbol)
        if prev_confirm != trend_confirm:
            trend_confirmation[symbol] = trend_confirm

            emoji = "🟢✅" if trend_confirm == "bullish" else "🔴✅"
            arabic_trend = "تأكيد صعود" if trend_confirm == "bullish" else "تأكيد هبوط"
            message = (
                f"📢 {arabic_trend}\n"
                f"{emoji} الرمز: {symbol}\n"
                f"⏰ الوقت: {sa_time}"
            )
            send_telegram(message)
            print(f"✅ {symbol}: تم تأكيد الاتجاه {trend_confirm}")
        return

    # ===== إشارات الدخول العادية =====
    direction = None
    if any(word in signal_text for word in ["bullish", "Bullish", "BULLISH"]):
        direction = "bullish"
    elif any(word in signal_text for word in ["bearish", "Bearish", "BEARISH"]):
        direction = "bearish"

    if not direction:
        print(f"⏭️ تجاهل إشارة غير معروفة: {signal_text}")
        return

    if symbol not in general_trend:
        print(f"⏭️ تجاهل إشارة {signal_text} لـ {symbol} لأنه لا يوجد اتجاه عام محدد")
        return

    # تجاهل إذا كانت معاكسة للاتجاه العام
    if direction != general_trend[symbol]:
        print(f"⏭️ تجاهل إشارة {signal_text} لـ {symbol} لأنها تعاكس الاتجاه العام {general_trend[symbol]}")
        return

    # توليد معرف فريد للإشارة لمنع التكرار
    signal_id = hashlib.sha256(signal_text.encode()).hexdigest()

    if signal_id in signals_store[symbol][direction]:
        print(f"⏭️ تجاهل إشارة مكررة: {signal_text}")
        return

    signals_store[symbol][direction][signal_id] = sa_time

    emoji = "🟢" if direction == "bullish" else "🔴"
    arabic_dir = "شراء" if direction == "bullish" else "بيع"
    message = (
        f"📌 إشارة دخول جديدة\n"
        f"{emoji} الرمز: {symbol}\n"
        f"📊 نوع الإشارة: {arabic_dir}\n"
        f"📝 الوصف: {signal_text}\n"
        f"⏰ الوقت: {sa_time}"
    )
    send_telegram(message)
    print(f"✅ خزّنّا إشارة {direction} لـ {symbol}: {signal_text}")


# ===== Webhook لاستقبال الإشارات من TradingView =====
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        # أولاً نحاول نقرأ JSON
        data = request.get_json(silent=True)
        if data and "message" in data:
            raw_message = data["message"].strip()
        else:
            # إذا مو JSON، نقرأه كنص عادي
            raw_message = request.data.decode("utf-8").strip()

        print(f"🌐 طلب وارد: {raw_message}")

        match = re.match(r"(\w+)\s*[:\-]\s*(.+)", raw_message)
        if not match:
            return jsonify({"status": "خطأ", "reason": "صيغة الرسالة غير صحيحة"}), 400

        symbol, signal_text = match.groups()
        process_signal(symbol, signal_text)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"❌ خطأ في المعالجة: {e}")
        return jsonify({"status": "error", "reason": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
