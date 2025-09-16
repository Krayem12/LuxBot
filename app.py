from flask import Flask, request, jsonify
import datetime
import hashlib
from collections import defaultdict
import re
import requests
import logging

app = Flask(__name__)

# ===== إعداد التوقيت السعودي =====
TIMEZONE_OFFSET = 3  # +3 ساعات للتوقيت السعودي

# ===== إعدادات التليجرام =====
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavjhtGmAxRg0TwLPdGxaVx8"
TELEGRAM_CHAT_ID = "6788824696"

# ===== التخزين (⚠️ ملاحظة: هذا تخزين بالذاكرة فقط - غير مشترك بين workers) =====
signals_store = defaultdict(lambda: {"bullish": {}, "bearish": {}})
used_signals = defaultdict(lambda: {"bullish": [], "bearish": []})  # تخزين (النص + الوقت)
alerts_count = defaultdict(lambda: {"bullish": 0, "bearish": 0})    # عداد التنبيهات
general_trend = {}  # الاتجاه العام لكل رمز

# ===== Logging محسّن =====
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ===== إرسال رسالة للتليجرام =====
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.error(f"❌ Telegram send failed {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال التليجرام: {e}")

# ===== دالة تجيب الوقت السعودي =====
def get_sa_time():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE_OFFSET)).strftime("%Y-%m-%d %H:%M:%S")

# ===== معالجة الإشارات =====
def process_signal(symbol: str, signal_text: str):
    sa_time = get_sa_time()

    # ===== الاتجاه العام (Trend Catcher فقط) =====
    trend_catcher = None
    if "Trend Catcher Bullish" in signal_text:
        trend_catcher = "bullish"
    elif "Trend Catcher Bearish" in signal_text:
        trend_catcher = "bearish"

    if trend_catcher:
        prev_trend = general_trend.get(symbol)
        if prev_trend != trend_catcher:
            general_trend[symbol] = trend_catcher
            # 🗑️ مسح إشارات الدخول القديمة فقط عند تغير الاتجاه العام
            signals_store[symbol] = {"bullish": {}, "bearish": {}}
            used_signals[symbol] = {"bullish": [], "bearish": []}
            alerts_count[symbol] = {"bullish": 0, "bearish": 0}

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
            logger.info(f"⚠️ {symbol}: تغير الاتجاه العام {prev_trend} → {trend_catcher}")
        return

    # ===== تأكيد الاتجاه (Trend Crossing) =====
    if "Trend Crossing Up" in signal_text:
        if general_trend.get(symbol) == "bullish":
            emoji = "🟢📈"
            message = (
                f"📢 تم تأكيد الاتجاه الى صعود قوي\n"
                f"{emoji} الرمز: {symbol}\n"
                f"⏰ الوقت: {sa_time}"
            )
            send_telegram(message)
            logger.info(f"✅ {symbol}: تم تأكيد الاتجاه صعود قوي")
        return

    if "Trend Crossing Down" in signal_text:
        if general_trend.get(symbol) == "bearish":
            emoji = "🔴📉"
            message = (
                f"📢 تم تأكيد الاتجاه الى هبوط قوي\n"
                f"{emoji} الرمز: {symbol}\n"
                f"⏰ الوقت: {sa_time}"
            )
            send_telegram(message)
            logger.info(f"✅ {symbol}: تم تأكيد الاتجاه هبوط قوي")
        return

    # ===== إشارات الدخول العادية =====
    direction = None
    if re.search(r"\bbullish\b", signal_text, re.I):
        direction = "bullish"
    elif re.search(r"\bbearish\b", signal_text, re.I):
        direction = "bearish"

    if not direction:
        logger.info(f"⏭️ تجاهل إشارة غير معروفة: {signal_text}")
        return

    if symbol not in general_trend:
        logger.info(f"⏭️ تجاهل إشارة {signal_text} لـ {symbol} لأنه لا يوجد اتجاه عام محدد")
        return

    # تجاهل إذا كانت معاكسة للاتجاه العام
    if direction != general_trend[symbol]:
        logger.info(f"⏭️ تجاهل إشارة {signal_text} لـ {symbol} لأنها تعاكس الاتجاه العام {general_trend[symbol]}")
        return

    # توليد معرف فريد للإشارة
    signal_id = hashlib.sha256(signal_text.encode()).hexdigest()
    if signal_id in signals_store[symbol][direction]:
        logger.info(f"⏭️ تجاهل إشارة مكررة: {signal_text}")
        return

    # حفظ الإشارة
    signals_store[symbol][direction][signal_id] = sa_time

    # إذا الإشارة جديدة كليًا (ما استخدمت في أي تنبيه سابق)
    if not any(sig["text"] == signal_text for sig in used_signals[symbol][direction]):
        used_signals[symbol][direction].append({"text": signal_text, "time": sa_time})

    total_new_signals = len(used_signals[symbol][direction])
    logger.info(f"📌 {symbol}: إشارات {direction} المخزنة = {total_new_signals}")

    # إذا صار عندنا إشارتين جديدتين مختلفتين منذ آخر تنبيه → يرسل تنبيه دخول
    if total_new_signals % 2 == 0 and total_new_signals > 0:
        alerts_count[symbol][direction] += 1
        last_two = used_signals[symbol][direction][-2:]  # آخر إشارتين مختلفتين
        emoji = "🟢" if direction == "bullish" else "🔴"
        arabic_dir = "شراء" if direction == "bullish" else "بيع"

        signals_details = "\n".join(
            [f"- {sig['text']} (⏰ {sig['time']})" for sig in last_two]
        )

        message = (
            f"📌 إشارة دخول جديدة (تنبيه رقم {alerts_count[symbol][direction]})\n"
            f"{emoji} الرمز: {symbol}\n"
            f"📊 نوع الإشارة: {arabic_dir}\n"
            f"📝 الإشارتان المستخدمتان:\n{signals_details}\n"
            f"📊 إجمالي الإشارات المختلفة المخزنة: {total_new_signals}\n"
            f"📢 إجمالي عدد التنبيهات المرسلة: {alerts_count[symbol][direction]}\n"
            f"⏰ وقت التنبيه: {sa_time}"
        )
        send_telegram(message)
        logger.info(f"✅ {symbol}: تم إرسال تنبيه دخول #{alerts_count[symbol][direction]} باعتماد إشارتين جديدتين")


# ===== Webhook لاستقبال الإشارات من TradingView =====
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        # أولاً نحاول نقرأ JSON
        data = request.get_json(silent=True)
        raw_message = None
        if data:
            if "message" in data:
                raw_message = data["message"].strip()
            else:
                # fallback: أول قيمة نصية
                for v in data.values():
                    if isinstance(v, str) and v.strip():
                        raw_message = v.strip()
                        break
        if not raw_message:
            raw_message = request.data.decode("utf-8").strip()

        logger.info(f"🌐 طلب وارد: {raw_message}")

        # محاولة regex لقبول رموز مع أحرف خاصة
        match = re.match(r"^(.+?)\s*[:\-]\s*(.+)$", raw_message)
        if match:
            symbol, signal_text = match.groups()
        else:
            # fallback: نعتبر آخر سطر هو الرمز
            parts = [p.strip() for p in raw_message.splitlines() if p.strip()]
            if len(parts) >= 2:
                symbol = parts[-1]
                signal_text = " ".join(parts[:-1])
            else:
                return jsonify({"status": "خطأ", "reason": "صيغة الرسالة غير صحيحة"}), 400

        process_signal(symbol.strip(), signal_text.strip())

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"❌ خطأ في المعالجة: {e}")
        return jsonify({"status": "error", "reason": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
