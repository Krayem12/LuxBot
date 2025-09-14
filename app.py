from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import hashlib
import threading
import time
import logging
from collections import defaultdict
import re

# ---------------------- إعداد اللوج ----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------- إعداد التليجرام ----------------------
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

def send_telegram_message(message: str):
    try:
        resp = requests.post(TELEGRAM_URL, data={"chat_id": CHAT_ID, "text": message})
        if resp.status_code == 200:
            log.info(f"📤 تم إرسال تنبيه للتليجرام: {message}")
        else:
            log.warning(f"⚠️ فشل إرسال التليجرام: {resp.status_code} - {resp.text}")
    except Exception as e:
        log.exception(f"❌ خطأ أثناء إرسال التنبيه للتليجرام: {e}")

# ---------------------- إعداد التطبيق ----------------------
app = Flask(__name__)

TIMEZONE_OFFSET = 3
REQUIRED_SIGNALS = 2  # عدد الإشارات المختلفة المطلوبة لإرسال التنبيه
RESET_TIMEOUT = 15 * 60  # 15 دقيقة
CHECK_INTERVAL = 30  # فحص كل 30 ثانية

# تخزين الإشارات
signal_memory = defaultdict(lambda: {"bullish": {}, "bearish": {}})
last_reset_time = datetime.utcnow()

# ---------------------- وظائف المساعدة ----------------------
def normalize_message(msg: str) -> str:
    return re.sub(r"\s+", " ", msg.strip())

def hash_signal(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()

def classify_direction(signal: str) -> str:
    lower = signal.lower()
    if any(word in lower for word in ["bullish", "buy", "long", "call", "up"]):
        return "bullish"
    elif any(word in lower for word in ["bearish", "sell", "short", "put", "down"]):
        return "bearish"
    else:
        return "bullish"  # بشكل افتراضي نعتبرها صعودية

# ---------------------- معالجة الإشارات ----------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        raw_data = request.get_data(as_text=True)
        parts = raw_data.strip().split("\n")
        if len(parts) < 2:
            return jsonify({"status": "error", "msg": "invalid payload"}), 400

        signal_text = normalize_message(parts[0])
        symbol = parts[1].strip().upper()
        direction = classify_direction(signal_text)

        signal_hash = hash_signal(signal_text + symbol)

        # تجاهل التكرارات
        if signal_hash in signal_memory[symbol][direction]:
            log.info(f"⏭️ إشارة مكررة تجاهل: {signal_text} لـ {symbol}")
            return jsonify({"status": "duplicate"}), 200

        signal_memory[symbol][direction][signal_hash] = {
            "signal": signal_text,
            "timestamp": datetime.utcnow()
        }

        log.info(f"✅ خزّننا إشارة {direction} لـ {symbol}: {signal_text}")
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        log.exception(f"❌ خطأ في /webhook: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 500

# ---------------------- عامل إرسال الإشارات المجمعة ----------------------
def alert_worker():
    global last_reset_time
    while True:
        now = datetime.utcnow()
        for symbol, directions in signal_memory.items():
            for direction, signals in directions.items():
                if len(signals) >= REQUIRED_SIGNALS:
                    # تجميع الإشارات المختلفة
                    messages = [meta["signal"] for meta in signals.values()]
                    formatted = "\n".join(f"• {m}" for m in messages)

                    prefix = "🟢⬆️ تأكيد صعودي" if direction == "bullish" else "🔴⬇️ تأكيد هبوطي"
                    telegram_msg = (
                        f"{prefix}\n"
                        f"الرمز: {symbol}\n"
                        f"الإشارات المختلفة:\n{formatted}\n"
                        f"⏰ التوقيت السعودي: {(now + timedelta(hours=TIMEZONE_OFFSET)).strftime('%Y-%m-%d %H:%M:%S')}"
                    )

                    send_telegram_message(telegram_msg)

                    # 🔄 تصفير الإشارات بعد الإرسال
                    signal_memory[symbol][direction] = {}

        # 🔁 التصفير بعد 15 دقيقة بدون إشارات جديدة
        if (now - last_reset_time).total_seconds() > RESET_TIMEOUT:
            for symbol in signal_memory:
                signal_memory[symbol]["bullish"] = {}
                signal_memory[symbol]["bearish"] = {}
            last_reset_time = now
            log.info("⏰ تصفير الإشارات بعد 15 دقيقة بدون إشارات جديدة")

        time.sleep(CHECK_INTERVAL)

# ---------------------- نقطة الدخول ----------------------
if __name__ == '__main__':
    threading.Thread(target=alert_worker, daemon=True).start()
    log.info("🟢 خادم webhook نشط وجاهز لاستقبال الإشارات...")
    app.run(host="0.0.0.0", port=5000)
