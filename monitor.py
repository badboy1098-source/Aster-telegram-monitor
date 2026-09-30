import json
import os
import requests
import websocket

WS_URL = "wss://fstream.asterdex.com/ws/btcusdt@depth20@100ms"

ORDER_THRESHOLD = 15000

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram пока не настроен")
        print(message)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=10
    )


def on_message(ws, message):
    try:
        data = json.loads(message)

        if data.get("e") != "depthUpdate":
            return

        symbol = data.get("s", "UNKNOWN")

        for price, qty in data.get("b", []):
            value = float(price) * float(qty)

            if value >= ORDER_THRESHOLD:
                message = (
                    "⚡ КРУПНЫЙ BUY\n\n"
                    f"💲 {symbol}\n"
                    f"🟢 BUY ≥ $15k: ${value:,.0f}\n"
                    f"💵 Цена уровня: {price}"
                )

                print(message)
                send_telegram(message)

        for price, qty in data.get("a", []):
            value = float(price) * float(qty)

            if value >= ORDER_THRESHOLD:
                message = (
                    "⚡ КРУПНЫЙ SELL\n\n"
                    f"💲 {symbol}\n"
                    f"🔴 SELL ≥ $15k: ${value:,.0f}\n"
                    f"💵 Цена уровня: {price}"
                )

                print(message)
                send_telegram(message)

    except Exception as e:
        print("Ошибка:", e)


def on_error(ws, error):
    print("WebSocket ошибка:", error)


def on_close(ws, close_status_code, close_msg):
    print("WebSocket отключён:", close_status_code, close_msg)


def on_open(ws):
    print("✅ WebSocket подключён")
    print("📡 Слушаем BTCUSDT...")


ws = websocket.WebSocketApp(
    WS_URL,
    on_open=on_open,
    on_message=on_message,
    on_error=on_error,
    on_close=on_close
)

ws.run_forever()
