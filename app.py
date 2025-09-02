import requests
from datetime import datetime
import random
import time

# رابط البوت على Render
WEBHOOK_URL = "https://luxbot-w6ek.onrender.com/webhook"

# مؤشرات وإشارات وهمية
indicators = ["LuxOscillator", "LuxVolume", "LuxTrend"]
signals = [
    "bullish_confirmation", "bearish_confirmation",
    "bullish_contrarian", "bearish_contrarian",
    "strong_bullish_confluence", "strong_bearish_confluence"
]

def send_fake_signal():
    indicator = random.choice(indicators)
    signal = random.choice(signals)
    strength = random.randint(50, 100)  # قوة عشوائية 50-100
    close = random.randint(4400, 4600)
    hl2 = close - random.randint(-10, 10)
    
    payload = {
        "signal": signal,
        "indicator": indicator,
        "strength": strength,
        "close": close,
        "hl2": hl2
    }
    
    try:
        r = requests.post(WEBHOOK_URL, json=payload)
        print(f"Sent: {payload} -> Status: {r.status_code}")
    except Exception as e:
        print("Error sending fake signal:", e)

if __name__ == "__main__":
    # إرسال 5 إشارات وهمية كل 2 ثانية
    for _ in range(5):
        send_fake_signal()
        time.sleep(2)
