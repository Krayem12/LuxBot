from flask import Flask, request
import requests
from collections import deque

app = Flask(__name__)

# التوكن والـ Chat ID للبوت
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# سجل الإشارات الأخيرة لتجنب الإرسال المكرر
recent_signals = deque(maxlen=10)
SIGNAL_THRESHOLD = 15  # عدد الإشارات المطلوبة قبل الإرسال

# كل الإشارات المدعومة وفق آخر تحديث LuxAlgo
LUXALGO_SIGNALS = [
    # Signals & Overlays
    "bullish_confirmation_any", "bearish_confirmation_any",
    "bullish_contrarian_any", "bearish_contrarian_any",
    "exit_buy", "exit_sell",
    "bullish_smart_trail", "bearish_smart_trail",
    "switch_bullish_smart_trail", "switch_bearish_smart_trail",
    "price_above_rzr1", "price_below_rzs1",
    "price_co_rzr1", "price_cu_rzs1",
    "bullish_catcher", "bearish_catcher",
    "switch_bullish_catcher", "switch_bearish_catcher",
    "bullish_tracer", "bearish_tracer",
    "switch_bullish_tracer", "switch_bearish_tracer",
    "bullish_neo", "bearish_neo",
    "switch_bullish_neo", "switch_bearish_neo",
    "trend_strength_trending", "trend_strength_ranging",

    # Price Action Concepts
    "bullish_ichoch", "bearish_ichoch",
    "bullish_ichoch+", "bearish_ichoch+",
    "bullish_ibos", "bearish_ibos",
    "bullish_schoch", "bearish_schoch",
    "bullish_schoch+", "bearish_schoch+",
    "bullish_sbos", "bearish_sbos",
    "bullish_ob", "bearish_ob",
    "bullish_bb", "bearish_bb",
    "bullish_ob_mitigated", "bearish_ob_mitigated",
    "bullish_ob_within", "bearish_ob_within",
    "bullish_ob_entered", "bearish_ob_entered",
    "bullish_ob_exit", "bearish_ob_exit",
    "bullish_imbalance", "bearish_imbalance",
    "bullish_imbalance_mitigated", "bearish_imbalance_mitigated",
    "bullish_imbalance_within", "bearish_imbalance_within",
    "bullish_imbalance_entered", "bearish_imbalance_entered",
    "bullish_imbalance_exit", "bearish_imbalance_exit",
    "bullish_trendline_new", "bearish_trendline_new",
    "bullish_trendline_update", "bearish_trendline_update",
    "bullish_trendline_break", "bearish_trendline_break",
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
    "strong_bullish_confluence", "strong_bearish_confluence",
    "custom_alert_step", "custom_alert_or"
]

@app.route("/send", methods=["POST"])
def send_alert():
    data = request.json

    # اجمع الإشارات النشطة
    active_signals = [sig for sig in LUXALGO_SIGNALS if str(data.get(sig)) == "True"]

    if active_signals:
        recent_signals.extend(active_signals)

        # تحقق من عدد الإشارات المختلفة
        unique_signals = set(recent_signals)
        if len(unique_signals) >= SIGNAL_THRESHOLD:
            message = "🔔 إشعار LuxAlgo ذكي 🔔\n\n"
            message += "\n".join(unique_signals)

            # إرسال التنبيه للتليقرام
            requests.get(TELEGRAM_URL, params={"chat_id": CHAT_ID, "text": message})
            recent_signals.clear()  # مسح الإشارات بعد الإرسال

    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

