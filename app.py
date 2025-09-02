@app.route("/webhook", methods=["POST"])
def webhook():
    global last_bar_time

    if request.is_json:
        data = request.get_json()
    else:
        return {"status": "error", "message": "Content-Type must be application/json"}, 415

    signal = data.get("signal")
    price = data.get("price")
    bar_time = data.get("time")
    layers_confirmed = data.get("layers_confirmed", 0)

    # تحويل layers_confirmed إلى رقم
    try:
        layers_confirmed = int(layers_confirmed)
    except (ValueError, TypeError):
        layers_confirmed = 0

    # تحقق من تحقق شرطين أو أكثر
    if layers_confirmed < 2:
        return {"status": "skipped_not_enough_layers"}, 200

    # تجاهل إشعارات نفس الشمعة
    if bar_time == last_bar_time:
        return {"status": "skipped_duplicate"}, 200
    last_bar_time = bar_time

    signal_text = "كول" if signal == "CALL" else "بوت" if signal == "PUT" else signal
    message = f"📊 إشارة {signal_text}\nالسعر: {price}\nالوقت: {bar_time}"
    send_telegram(message)

    return {"status": "ok"}, 200
