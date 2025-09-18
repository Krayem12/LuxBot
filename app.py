from flask import Flask, request, jsonify
import datetime
import hashlib
from collections import defaultdict
import re
import requests
import logging
import os  # لإدارة متغيرات البيئة

app = Flask(__name__)

# ===== إعداد التوقيت السعودي =====
TIMEZONE_OFFSET = 3  # +3 ساعات للتوقيت السعودي

# ===== بيانات التليجرام (من Environment Variables) =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("❌ تأكد من ضبط TELEGRAM_TOKEN و TELEGRAM_CHAT_ID في متغيرات البيئة")

# ===== رابط الخادم الخارجي =====
EXTERNAL_URL = "https://backend-thrumming-moon-2807.fly.dev/sendMessage"

# ===== التخزين بالذاكرة =====
signals_store = defaultdict(lambda: {"bullish": {}, "bearish": {}})
used_signals = defaultdict(lambda: {"bullish": [], "bearish": []})
alerts_count = defaultdict(lambda: {"bullish": 0, "bearish": 0})
general_trend = {}

# ===== Logging =====
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ===== دالة ترجع الوقت السعودي =====
def get_sa_time():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE_OFFSET)).strftime("%Y-%m-%d %H:%M:%S")

# ===== إرسال رسالة للتليجرام =====
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.error(f"[{get_sa_time()}] ❌ Telegram send failed {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"[{get_sa_time()}] ❌ خطأ في إرسال التليجرام: {e}")

# ===== إرسال نفس النص للخادم الخارجي =====
def send_external(message: str):
    try:
        resp = requests.post(
            EXTERNAL_URL,
            data=message.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
            timeout=10
        )
        if resp.status_code != 200:
            logger.error(f"[{get_sa_time()}] ❌ External send failed {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"[{get_sa_time()}] ❌ خطأ في إرسال للخادم الخارجي: {e}")

# ===== دالة إرسال مزدوج (تليجرام + خارجي) =====
def send_message(message: str):
    send_telegram(message)
    send_external(message)

# ===== معالجة الإشارات =====
def process_signal(symbol: str, signal_text: str):
    sa_time = get_sa_time()

    # ===== Price Explosion Alerts (Balanced / Aggressive / Conservative) =====
    pe_match = None
    pe_label = None

    # Balanced
    if "CALL SPX500" in signal_text:
        pe_match, pe_label = "CALL", "Balanced"
    elif "PUT SPX500" in signal_text:
        pe_match, pe_label = "PUT", "Balanced"

    # Aggressive
    elif "CALL2 SPX500" in signal_text:
        pe_match, pe_label = "CALL", "Aggressive"
    elif "PUT2 SPX500" in signal_text:
        pe_match, pe_label = "PUT", "Aggressive"

    # Conservative
    elif "CALL3 SPX500" in signal_text:
        pe_match, pe_label = "CALL", "Conservative"
    elif "PUT3 SPX500" in signal_text:
        pe_match, pe_label = "PUT", "Conservative"

    if pe_match:
        # الاتجاه المتوقع من Price Explosion
        expected_trend = "bullish" if pe_match == "CALL" else "bearish"

        # تحقق من الاتجاه الداخلي
        if expected_trend.lower() not in signal_text.lower():
            logger.info(f"[{sa_time}] ⚡ تجاهل Price Explosion {pe_match} لـ {symbol} لأنه لا يطابق الاتجاه الداخلي ({expected_trend})")
            return

        # تحقق من Trend Catcher (الاتجاه العام)
        current_trend = general_trend.get(symbol)
        if current_trend != expected_trend:
            reason = "لا يوجد اتجاه عام محدد" if not current_trend else f"Trend Catcher {current_trend} يختلف عن {expected_trend}"
            logger.info(f"[{sa_time}] ⚡ تجاهل Price Explosion {pe_match} لـ {symbol} {reason}")
            return

        # تحقق من Trend Tracer (لازم يكون بنفس الاتجاه)
        tracer_expected = f"Trend Tracer {expected_trend.capitalize()}"
        if tracer_expected not in signal_text:
            logger.info(f"[{sa_time}] ⚡ تجاهل Price Explosion {pe_match} لـ {symbol} لأنه لا يوجد {tracer_expected}")
            return

        # حاول استخراج السعر بعد @
        price_match = re.search(r"@[\s]*([0-9]*\.?[0-9]+)", signal_text)
        price_text = price_match.group(1) if price_match else "N/A"

        emoji = "📈" if pe_match == "CALL" else "📉"

        # صياغة الرسالة حسب نوع الاستراتيجية
        if pe_label == "Balanced":
            label_text = "🚀 Price Explosion (انفجار سعري) — Balanced"
        elif pe_label == "Aggressive":
            label_text = "🚀 Price Explosion (2 انفجار سعري) — Aggressive"
        elif pe_label == "Conservative":
            label_text = "🚀 Price Explosion (3 انفجار سعري) — Conservative"
        else:
            label_text = f"🚀 Price Explosion (انفجار سعري) — {pe_label}"

        message = (
            f"{label_text}\n"
            f"{emoji} {pe_match} — {symbol}\n"
            f"💰 Price: {price_text}\n"
            f"📊 Confirmed with: Trend Catcher ✅ + Trend Tracer ✅\n"
            f"⏰ Time: {sa_time}"
        )
        send_message(message)
        logger.info(f"[{sa_time}] ✅ {symbol}: {pe_label} Price Explosion {pe_match} confirmed with Trend Catcher + Tracer sent with price {price_text}")
        return

    # ===== الاتجاه العام (Trend Catcher) =====
    trend_catcher = None
    if "Trend Catcher Bullish" in signal_text:
        trend_catcher = "bullish"
    elif "Trend Catcher Bearish" in signal_text:
        trend_catcher = "bearish"

    if trend_catcher:
        prev_trend = general_trend.get(symbol)
        if prev_trend != trend_catcher:
            general_trend[symbol] = trend_catcher
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
            send_message(message)
            logger.info(f"[{sa_time}] ⚠️ {symbol}: تغير الاتجاه العام {prev_trend} → {trend_catcher}")
        return

    # ===== تأكيد الاتجاه (Trend Crossing) =====
    if "Trend Crossing Up" in signal_text:
        if general_trend.get(symbol) == "bullish":
            message = (
                f"📢 تم تأكيد الاتجاه الى صعود قوي\n"
                f"🟢📈 الرمز: {symbol}\n"
                f"⏰ الوقت: {sa_time}"
            )
            send_message(message)
            logger.info(f"[{sa_time}] ✅ {symbol}: تم تأكيد الاتجاه صعود قوي")
        else:
            reason = "لأنه لا يوجد اتجاه عام محدد" if symbol not in general_trend else f"لأنه يعاكس الاتجاه العام {general_trend[symbol]}"
            logger.info(f"[{sa_time}] ⏭️ تجاهل تأكيد الاتجاه {signal_text} لـ {symbol} {reason}")
        return

    if "Trend Crossing Down" in signal_text:
        if general_trend.get(symbol) == "bearish":
            message = (
                f"📢 تم تأكيد الاتجاه الى هبوط قوي\n"
                f"🔴📉 الرمز: {symbol}\n"
                f"⏰ الوقت: {sa_time}"
            )
            send_message(message)
            logger.info(f"[{sa_time}] ✅ {symbol}: تم تأكيد الاتجاه هبوط قوي")
        else:
            reason = "لأنه لا يوجد اتجاه عام محدد" if symbol not in general_trend else f"لأنه يعاكس الاتجاه العام {general_trend[symbol]}"
            logger.info(f"[{sa_time}] ⏭️ تجاهل تأكيد الاتجاه {signal_text} لـ {symbol} {reason}")
        return

    # ===== إشارات الدخول العادية =====
    direction = None
    if re.search(r"\bbullish\b", signal_text, re.I) or re.search(r"\bupward\b", signal_text, re.I):
        direction = "bullish"
    elif re.search(r"\bbearish\b", signal_text, re.I) or re.search(r"\bdownward\b", signal_text, re.I):
        direction = "bearish"

    if not direction:
        logger.info(f"[{sa_time}] ⏭️ تجاهل إشارة غير معروفة: {signal_text}")
        return

    if symbol not in general_trend:
        logger.info(f"[{sa_time}] ⏭️ تجاهل إشارة {signal_text} لـ {symbol} لأنه لا يوجد اتجاه عام محدد")
        return

    if direction != general_trend[symbol]:
        logger.info(f"[{sa_time}] ⏭️ تجاهل إشارة {signal_text} لـ {symbol} لأنها تعاكس الاتجاه العام {general_trend[symbol]}")
        return

    signal_id = hashlib.sha256(signal_text.encode()).hexdigest()
    if signal_id in signals_store[symbol][direction]:
        logger.info(f"[{sa_time}] ⏭️ تجاهل إشارة مكررة: {signal_text}")
        return

    signals_store[symbol][direction][signal_id] = sa_time

    if not any(sig["text"] == signal_text for sig in used_signals[symbol][direction]):
        used_signals[symbol][direction].append({"text": signal_text, "time": sa_time})

    total_new_signals = len(used_signals[symbol][direction])
    logger.info(f"[{sa_time}] 📌 {symbol}: إشارات {direction} المخزنة = {total_new_signals}")

    if total_new_signals % 2 == 0 and total_new_signals > 0:
        alerts_count[symbol][direction] += 1
        last_two = used_signals[symbol][direction][-2:]
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
        send_message(message)
        logger.info(f"[{sa_time}] ✅ {symbol}: تم إرسال تنبيه دخول #{alerts_count[symbol][direction]} باعتماد إشارتين جديدتين")

# ===== Webhook =====
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(silent=True)
        raw_message = None
        if data:
            if "message" in data:
                raw_message = data["message"].strip()
            else:
                for v in data.values():
                    if isinstance(v, str) and v.strip():
                        raw_message = v.strip()
                        break
        if not raw_message:
            raw_message = request.data.decode("utf-8").strip()

        logger.info(f"[{get_sa_time()}] 🌐 طلب وارد: {raw_message}")

        match = re.match(r"^(.+?)\s*[:\-]\s*(.+)$", raw_message)
        if match:
            symbol, signal_text = match.groups()
        else:
            parts = [p.strip() for p in raw_message.splitlines() if p.strip()]
            if len(parts) >= 2:
                symbol = parts[-1]
                signal_text = " ".join(parts[:-1])
            else:
                return jsonify({"status": "خطأ", "reason": "صيغة الرسالة غير صحيحة"}), 400

        process_signal(symbol.strip(), signal_text.strip())
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"[{get_sa_time()}] ❌ خطأ في المعالجة: {e}")
        return jsonify({"status": "error", "reason": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
