import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# Telegram
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# مؤشرات LOXALGO الثلاثة (Signals & Overlays + Price Action + Oscillator Matrix)
signal_keys = [
    # Signals & Overlays
    "bullish_confirmation", "bullish_confirmation+", "bullish_confirmation_any", "bullish_confirmation_turn+",
    "bearish_confirmation", "bearish_confirmation+", "bearish_confirmation_any", "bearish_confirmation_turn+",
    "bullish_contrarian", "bullish_contrarian+", "bullish_contrarian_any",
    "bearish_contrarian", "bearish_contrarian+", "bearish_contrarian_any",
    "exit_buy", "exit_sell",
    "bullish_smart_trail", "bearish_smart_trail", "switch_bullish_smart_trail", "switch_bearish_smart_trail",
    "price_above_rzr1", "price_below_rzs1", "price_co_rzr1", "price_cu_rzs1",
    "bullish_catcher", "bearish_catcher", "switch_bullish_catcher", "switch_bearish_catcher",
    "bullish_tracer", "bearish_tracer", "switch_bullish_tracer", "switch_bearish_tracer",
    "bullish_neo", "bearish_neo", "switch_bullish_neo", "switch_bearish_neo",
    "trend_strength_trending", "trend_strength_ranging",

    # Price Action Concepts
    "bullish_ichoch", "bullish_ichoch+", "bullish_ibos",
    "bearish_ichoch", "bearish_ichoch+", "bearish_ibos",
    "bullish_schoch", "bullish_schoch+", "bullish_sbos",
    "bearish_schoch", "bearish_schoch+", "bearish_sbos",
    "bullish_ob", "bearish_ob", "bullish_bb", "bearish_bb",
    "bullish_ob_mitigated", "bearish_ob_mitigated",
    "bullish_ob_within", "bearish_ob_within",
    "bullish_ob_entered", "bearish_ob_entered",
    "bullish_ob_exit", "bearish_ob_exit",
    "bullish_imbalance", "bearish_imbalance",
    "bullish_imbalance_mitigated", "bearish_imbalance_mitigated",
    "bullish_imbalance_within", "bearish_imbalance_within",
    "bullish_imbalance_entered", "bearish_imbalance_entered",
    "bullish_imbalance_exit", "bearish_imbalance_exit",
    "bullish_trendline_new", "bullish_trendline_update", "bullish_trendline_break",
    "bearish_trendline_new", "bearish_trendline_update", "bearish_trendline_break",
    "bullish_grab", "bearish_grab",
    "premium", "discount",

    # Oscillator Matrix
    "regular_bullish_hyperwave_signal", "regular_bearish_hyperwave_signal",
    "oversold_bullish_hyperwave_signal", "overbought_bearish_hyperwave_signal",
    "hyperwave_co_80", "hyperwave_cu_20", "hyperwave_co_50", "hyperwave_cu_50",
    "hyperwave_above_80", "hyperwave_below_20", "hyperwave_above_50", "hyperwave_below_50",
    "moneyflow_co_50", "moneyflow_cu_50", "moneyflow_above_50", "moneyflow_below_50",
    "new_bullish_overflow", "new_bearish_overflow",
    "bullish_overflow", "bearish_overflow",
    "reversal_up-", "reversal_up+", "reversal_down-", "reversal_down+",
    "reversal_any_up", "reversal_any_down",
    "bullish_divergence", "bearish_divergence",
    "weak_bullish_confluence", "weak_bearish_confluence",
    "strong_bullish_confluence", "strong_bearish_confluence"
]

# لتخزين الإشارات المؤقتة
temp_signals = []
start_time = None
last_bar_sent = None
TIME_LIMIT = timedelta(minutes=15)  # ربع ساعة

@app.route('/', methods=['POST'])
def webhook():
    global temp_signals, start_time, last_bar_sent

    data = request.get_json()
    if not data:
        return jsonify({"status": "no data received"}), 400

    bar_index = data.get("barindex")
    if not bar_index:
        return jsonify({"status": "bar index missing"}), 400

    # تجاهل نفس البار
    if bar_index == last_bar_sent:
        return jsonify({"status": "alert already sent for this bar"}), 200

    # جلب الإشارات المفعلة في هذا البار
    active_signals = [key for key in signal_keys if data.get(key) in [True, 1]]

    # إذا هناك إشارات
    if active_signals:
        now = datetime.utcnow()
        if start_time is None:
            start_time = now  # بدء المؤقت

        # إضافة الإشارات للقائمة المؤقتة مع البار الحالي
        temp_signals.extend(active_signals)

        # التحقق إذا تحققنا من 3 إشارات أو أكثر خلال ربع الساعة
        unique_signals = set(temp_signals)
        if len(unique_signals) >= 3:
            message = f"📊 إشارات LOXALGO:\nرمز: {data.get('symbol')}\nبار: {bar_index}\nإشارات مفعلة: {', '.join(unique_signals)}"
            requests.get(TELEGRAM_URL, params={"chat_id": CHAT_ID, "text": message})

            # إعادة ضبط بعد الإرسال
            temp_signals = []
            start_time = None
            last_bar_sent = bar_index
            return jsonify({"status": "alert sent"}), 200

        # تحقق من انتهاء المهلة (15 دقيقة)
        if now - start_time > TIME_LIMIT:
            temp_signals = []
            start_time = None
            return jsonify({"status": "time limit exceeded, reset signals"}), 200

    return jsonify({"status": f"{len(temp_signals)} signals collected, not sent yet"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
