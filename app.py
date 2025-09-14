from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import hashlib
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont
import io

app = Flask(__name__)

TIMEZONE_OFFSET = 3
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

signals_store = defaultdict(lambda: {"bullish": {}, "bearish": {}})

def hash_signal(signal_text: str):
    return hashlib.sha256(signal_text.encode()).hexdigest()

def create_signal_image(symbol, direction, signals_list, total_signals):
    # حجم الصورة يعتمد على عدد الإشارات
    width, height = 900, 250 + 35 * len(signals_list)
    
    # إعداد خلفية متدرجة
    base_color = (245, 245, 245)  # فاتح
    gradient_color = (220, 220, 220)
    image = Image.new("RGB", (width, height), color=base_color)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        r = int(base_color[0] + (gradient_color[0]-base_color[0]) * y/height)
        g = int(base_color[1] + (gradient_color[1]-base_color[1]) * y/height)
        b = int(base_color[2] + (gradient_color[2]-base_color[2]) * y/height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # خطوط
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 32)
        font_text = ImageFont.truetype("arial.ttf", 26)
    except:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()
    
    # ألوان حسب الاتجاه
    main_color = (0, 102, 204) if direction == "bullish" else (204, 0, 0)  # أزرق/أحمر
    arrow = "📈" if direction == "bullish" else "📉"
    main_direction_text = "صعودية" if direction == "bullish" else "هبوطية"
    
    sa_time = (datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)).strftime("%H:%M:%S")
    
    # رسم المربعات الملونة للأقسام
    draw.rectangle([10, 10, width-10, 70], fill=main_color)
    draw.rectangle([10, 80, width-10, 80 + 40 + 35*len(signals_list)], outline=(0,0,0), width=2)
    
    # كتابة النصوص
    y = 20
    draw.text((20, y), f"{arrow} {symbol} - تأكيد إشارة {main_direction_text} قوية", fill="white", font=font_title)
    y = 90
    draw.text((20, y), "📊 الإشارات المختلفة:", fill="black", font=font_text)
    y += 35
    for sig in signals_list:
        draw.text((40, y), f"• {sig}", fill="black", font=font_text)
        y += 35
    
    draw.text((20, y), f"🔢 عدد الإشارات الكلي: {total_signals}", fill="black", font=font_text)
    y += 35
    draw.text((20, y), f"⏰ التوقيت السعودي: {sa_time}", fill="black", font=font_text)
    y += 45
    draw.text((20, y), f"متوقع حركة {main_direction_text} من {total_signals} إشارات مختلفة", fill=main_color, font=font_text)
    
    # حفظ الصورة في BytesIO
    bio = io.BytesIO()
    image.save(bio, format="PNG")
    bio.seek(0)
    return bio

def send_telegram_image(image_bytes):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    files = {"photo": ("signal.png", image_bytes)}
    data = {"chat_id": CHAT_ID}
    try:
        response = requests.post(url, files=files, data=data, timeout=15)
        if response.status_code == 200:
            print("✅ أرسلنا الصورة للتليجرام")
        else:
            print(f"⚠️ فشل ارسال الصورة ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"⚠️ خطأ أثناء ارسال الصورة: {e}")

def process_signal(signal_text: str):
    lines = signal_text.strip().split("\n")
    if len(lines) < 2:
        return
    signal_name = lines[0].strip()
    symbol = lines[1].strip()
    direction = "bullish" if "bullish" in signal_name.lower() else "bearish"
    signal_hash = hash_signal(signal_name)
    
    if signal_hash in signals_store[symbol][direction]:
        return
    
    signals_store[symbol][direction][signal_hash] = signal_name
    
    if len(signals_store[symbol][direction]) >= 2:
        signals_list = list(signals_store[symbol][direction].values())
        total_signals = len(signals_list)
        image_bytes = create_signal_image(symbol, direction, signals_list, total_signals)
        send_telegram_image(image_bytes)
        signals_store[symbol][direction].clear()

@app.route("/webhook", methods=["POST"])
def webhook():
    signal_text = request.get_data(as_text=True)
    process_signal(signal_text)
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
