import time
from datetime import datetime, timedelta
from flask import Flask, request, render_template_string
import threading
import requests

app = Flask(__name__)

# 🔹 بيانات التوكن والـ ID للتليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# 🔹 النوافذ الزمنية
CONDITION_WINDOW = timedelta(minutes=5)
REPORT_INTERVAL = 900  # 15 دقيقة للتقرير الدوري

# 🔹 جميع الإشارات المهمة من آخر تحديث LuxAlgo
TRACKED_SIGNALS = [
    "bullish_confirmation", "bearish_confirmation",
    "bullish_contrarian", "bearish_contrarian",
    "regular_bullish_hyperwave_signal", "regular_bearish_hyperwave_signal",
    "oversold_bullish_hyperwave_signal", "overbought_bearish_hyperwave_signal",
    "strong_bullish_confluence", "strong_bearish_confluence",
    "weak_bullish_confluence", "weak_bearish_confluence",
    "bullish_ob", "bearish_ob",
    "bullish_bb", "bearish_bb",
    "bullish_ibos", "bearish_ibos",
    "bullish_sbos", "bearish_sbos"
]

PLACEHOLDER_FIELDS = [
    "open", "high", "low", "close", "hl2", "ohlc4", "hlc3", "hlcc4",
    "volume", "range", "tr",
    "barindex", "last_barindex", "second", "minute", "hour", "dayofweek",
    "dayofmonth", "weekofyear", "month", "year", "unix_ts", "timeframe",
    "custom_alert_step", "custom_alert_or", "step", "barssince_step", "invalidated",
    "external1", "external2", "external3", "external4", "external5"
]

# 🔹 تخزين جميع الإشارات
condition_tracker = {}

# 🔹 إرسال رسالة للتليجرام
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("خطأ في إرسال الرسالة:", e)

# 🔹 التحقق من شروط الإشارة (قابلة للتخصيص)
def check_conditions(signal, placeholders):
    strength = placeholders.get("strength", 0)
    close = placeholders.get("close", 0)
    hl2 = placeholders.get("hl2", 0)
    
    bullish_conditions = [
        signal in ["bullish_confirmation", "bullish_contrarian", "strong_bullish_confluence"],
        strength >= 50,
        close > hl2
    ]
    
    bearish_conditions = [
        signal in ["bearish_confirmation", "bearish_contrarian", "strong_bearish_confluence"],
        strength >= 50,
        close < hl2
    ]
    
    return all(bullish_conditions), all(bearish_conditions)

# 🔹 استقبال الـ webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data or "signal" not in data or "indicator" not in data:
        return {"status": "error", "msg": "بيانات غير صحيحة"}, 400

    signal_name = data["signal"]
    indicator_name = data["indicator"]
    timestamp = datetime.utcnow()
    
    placeholders = {k: data.get(k, 0) for k in PLACEHOLDER_FIELDS}
    placeholders["strength"] = data.get("strength", 0)

    if signal_name not in TRACKED_SIGNALS:
        return {"status": "ignored"}

    if indicator_name not in condition_tracker:
        condition_tracker[indicator_name] = []

    # إضافة الإشارة الجديدة
    condition_tracker[indicator_name].append({
        "timestamp": timestamp,
        "signal": signal_name,
        "placeholders": placeholders,
        "sent": False
    })

    # تنظيف الإشارات القديمة
    cutoff = datetime.utcnow() - CONDITION_WINDOW
    for ind in condition_tracker:
        condition_tracker[ind] = [
            s for s in condition_tracker[ind] if s["timestamp"] > cutoff
        ]

    # التحقق من إشارات عالية التأكيد
    check_high_confidence_signals()

    return {"status": "ok"}

# 🔹 التحقق من إشارات عالية التأكيد (ثلاثة مؤشرات متوافقة)
def check_high_confidence_signals():
    now = datetime.utcnow()
    valid_signals = []
    for indicator, signals in condition_tracker.items():
        for s in signals:
            if not s["sent"] and now - s["timestamp"] <= CONDITION_WINDOW:
                bullish, bearish = check_conditions(s["signal"], s["placeholders"])
                valid_signals.append({
                    "indicator": indicator,
                    "signal": s["signal"],
                    "type": "bullish" if bullish else "bearish" if bearish else None,
                    "timestamp": s["timestamp"],
                    "ref": s
                })
    for signal_type in ["bullish", "bearish"]:
        matches = [s for s in valid_signals if s["type"] == signal_type]
        if len(matches) >= 3:
            indicators_list = ", ".join([s["indicator"] for s in matches[:3]])
            message = f"🔥 تنبيه قوي {signal_type.upper()} على المؤشرات: {indicators_list}!\n"
            message += "\n".join([f"{s['indicator']} -> {s['signal']} ⏱ {s['timestamp'].strftime('%H:%M:%S')}" for s in matches[:3]])
            send_telegram_alert(message)
            for s in matches[:3]:
                s["ref"]["sent"] = True

# 🔹 تقرير دوري كل 15 دقيقة
def periodic_report():
    while True:
        time.sleep(REPORT_INTERVAL)
        now = datetime.utcnow()
        message_lines = ["🚨 <b>LuxAlgo Signals Report (آخر 15 دقيقة)</b>"]
        for indicator, signals in condition_tracker.items():
            recent = [s for s in signals if now - s["timestamp"] <= CONDITION_WINDOW]
            if recent:
                message_lines.append(f"\n📊 <b>{indicator}</b>")
                for s in recent:
                    ph_text = ", ".join([f"{k}: {v}" for k, v in s["placeholders"].items()])
                    message_lines.append(f" • {s['signal']} ⏱ {s['timestamp'].strftime('%H:%M:%S')} [{ph_text}]")
        if len(message_lines) > 1:
            send_telegram_alert("\n".join(message_lines))

# 🔹 واجهة ويب لعرض الإشارات
@app.route('/')
def dashboard():
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>LuxAlgo Dashboard</title>
        <meta http-equiv="refresh" content="10">
        <style>
            body { font-family: Arial, sans-serif; background: #f0f0f0; padding: 20px; }
            table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #4CAF50; color: white; }
            tr:nth-child(even){background-color: #f2f2f2;}
            .bullish { color: green; font-weight: bold; }
            .bearish { color: red; font-weight: bold; }
            .sent { background-color: #d3d3d3; }
        </style>
    </head>
    <body>
        <h1>LuxAlgo Dashboard</h1>
        {% for indicator, signals in condition_tracker.items() %}
            <h2>{{ indicator }}</h2>
            <table>
                <tr>
                    <th>Signal</th>
                    <th>Type</th>
                    <th>Time</th>
                    <th>Sent</th>
                    <th>Placeholders</th>
                </tr>
                {% for s in signals %}
                    <tr class="{{ 'sent' if s.sent else '' }}">
                        <td>{{ s.signal }}</td>
                        <td class="{{ s.type }}">{{ s.type or 'N/A' }}</td>
                        <td>{{ s.timestamp.strftime('%H:%M:%S') }}</td>
                        <td>{{ s.sent }}</td>
                        <td>{{ s.placeholders }}</td>
                    </tr>
                {% endfor %}
            </table>
        {% endfor %}
    </body>
    </html>
    """
    # تحويل condition_tracker إلى قائمة من الكائنات للوصول في Jinja2
    tracker_copy = {}
    for k, v in condition_tracker.items():
        tracker_copy[k] = []
        for s in v:
            tracker_copy[k].append(type('obj', (object,), s))
    return render_template_string(html_template, condition_tracker=tracker_copy)

if __name__ == '__main__':
    # تشغيل تقرير دوري
    report_thread = threading.Thread(target=periodic_report, daemon=True)
    report_thread.start()
    app.run(host="0.0.0.0", port=5000)
