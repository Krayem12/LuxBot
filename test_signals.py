import requests
import time

WEBHOOK_URL = "http://127.0.0.1:5000/webhook"

# إشارات الاختبار بالترتيب
signals = [
    {"message": "SPX500: Trend Catcher Bullish"},        # اتجاه عام
    {"message": "SPX500: Trend Crossing Up"},            # تأكيد الاتجاه
    {"message": "SPX500: Strong bullish confluence"}     # إشارة دخول عادية
]

for sig in signals:
    print(f"🔹 إرسال: {sig['message']}")
    resp = requests.post(WEBHOOK_URL, json=sig)
    print(f"🔸 استجابة السيرفر: {resp.status_code} - {resp.text}")
    time.sleep(2)  # انتظار ثانيتين بين كل إشارة
