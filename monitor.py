import json
import websocket

WS_URL = "wss://fstream.asterdex.com/ws/btcusdt@depth20@100ms"

ORDER_THRESHOLD = 15000

print("🤖 Aster Monitor запущен")
print("📡 Слушаем BTCUSDT...")

def on_message(ws, message):
    try:
        data = json.loads(message)

        if data.get("e") != "depthUpdate":
            return

        symbol = data.get("s", "UNKNOWN")

        for price, qty in data.get("b", []):
            value = float(price) * float(qty)

            if value >= ORDER_THRESHOLD:
                print(
                    f"🟢 BUY ≥ $15k | {symbol} | "
                    f"${value:,.0f} | цена {price}"
                )

        for price, qty in data.get("a", []):
            value = float(price) * float(qty)

            if value >= ORDER_THRESHOLD:
                print(
                    f"🔴 SELL ≥ $15k | {symbol} | "
                    f"${value:,.0f} | цена {price}"
                )

    except Exception as e:
        print("Ошибка:", e)


def on_error(ws, error):
    print("WebSocket ошибка:", error)


def on_close(ws, close_status_code, close_msg):
    print("WebSocket отключён:", close_status_code, close_msg)


def on_open(ws):
    print("✅ WebSocket подключён")


ws = websocket.WebSocketApp(
    WS_URL,
    on_open=on_open,
    on_message=on_message,
    on_error=on_error,
    on_close=on_close
)

ws.run_forever()
