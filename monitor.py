import json
import os
import time
import requests
import websocket

WS_BASE = "wss://fstream.asterdex.com/stream?streams="

ORDER_THRESHOLD = 15000
MIN_VOLUME = 50000
MAX_SYMBOLS = 90

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

last_alerts = {}
ALERT_COOLDOWN = 60


def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram не настроен")
        print(message)
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

        response = requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": message
            },
            timeout=10
        )

        if not response.ok:
            print("Ошибка Telegram:", response.text)

    except Exception as e:
        print("Ошибка отправки Telegram:", e)


def get_symbols():
    try:
        ticker_url = "https://fapi.asterdex.com/fapi/v1/ticker/24hr"

        response = requests.get(
            ticker_url,
            timeout=10
        )

        data = response.json()

        coins = []

        for item in data:
            symbol = item.get("symbol", "")

            if not symbol.endswith("USDT"):
                continue

            volume = float(item.get("quoteVolume", 0))

            if volume < MIN_VOLUME:
                continue

            coins.append({
                "symbol": symbol,
                "volume": volume
            })

        coins.sort(
            key=lambda x: x["volume"],
            reverse=True
        )

        symbols = [
            x["symbol"].lower()
            for x in coins[:MAX_SYMBOLS]
        ]

        print(f"✅ Найдено монет: {len(symbols)}")

        return symbols

    except Exception as e:
        print("Ошибка получения списка монет:", e)
        return []


def check_order(symbol, side, price, qty):
    try:
        price = float(price)
        qty = float(qty)

        value = price * qty

        key = f"{symbol}:{side}:{price}"

        if value >= ORDER_THRESHOLD:

            if key not in last_alerts:

                last_alerts[key] = time.time()

                if side == "BUY":

                    message = (
                        "⚡ КРУПНЫЙ BUY\n\n"
                        f"💲 {symbol}\n"
                        f"🟢 BUY ≥ $15k: ${value:,.0f}\n"
                        f"💵 Цена уровня: {price}"
                    )

                else:

                    message = (
                        "⚡ КРУПНЫЙ SELL\n\n"
                        f"💲 {symbol}\n"
                        f"🔴 SELL ≥ $15k: ${value:,.0f}\n"
                        f"💵 Цена уровня: {price}"
                    )

                print(message)
                send_telegram(message)

        else:

            if key in last_alerts:
                del last_alerts[key]

    except Exception as e:
        print("Ошибка проверки ордера:", e)


def on_message(ws, message):

    try:

        data = json.loads(message)

        if "data" in data:
            data = data["data"]

        if data.get("e") != "depthUpdate":
            return

        symbol = data.get("s", "UNKNOWN")

        bids = data.get("b", [])
        asks = data.get("a", [])

        for price, qty in bids:
            check_order(
                symbol,
                "BUY",
                price,
                qty
            )

        for price, qty in asks:
            check_order(
                symbol,
                "SELL",
                price,
                qty
            )

    except Exception as e:
        print("Ошибка обработки WebSocket:", e)


def on_error(ws, error):
    print("⚠️ WebSocket ошибка:", error)


def on_close(ws, close_status_code, close_msg):
    print(
        "🔴 WebSocket отключён:",
        close_status_code,
        close_msg
    )


def on_open(ws):
    print("🟢 WebSocket подключён")
    print("⚡ Мониторинг крупных ордеров запущен")


def run_monitor():

    symbols = get_symbols()

    if not symbols:
        print("❌ Не удалось получить список монет")
        return

    streams = []

    for symbol in symbols:
        streams.append(
            f"{symbol}@depth20@100ms"
        )

    ws_url = WS_BASE + "/".join(streams)

    print("📡 Подключаемся к Aster...")
    print(f"📊 Потоков: {len(streams)}")

    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    ws.run_forever(
        ping_interval=60,
        ping_timeout=30
    )


while True:

    try:

        run_monitor()

    except Exception as e:

        print("❌ Ошибка монитора:", e)

    print("🔄 Переподключение через 5 секунд...")
    time.sleep(5)
