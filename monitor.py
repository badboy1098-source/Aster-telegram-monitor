import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
# =========================================================
# SUPABASE — ПОДПИСЧИКИ TELEGRAM
# =========================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET = os.getenv("SUPABASE_SECRET")


def get_subscribers():

    if not SUPABASE_URL or not SUPABASE_SECRET:
        print("❌ SUPABASE настройки не найдены")
        return []

url = (
    f"{SUPABASE_URL}"
    f"/rest/v1/subscribers"
    f"?select=chat_id&approved=eq.true"
)

    headers = {
        "apikey": SUPABASE_SECRET,
        "Authorization": f"Bearer {SUPABASE_SECRET}"
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )
        print(
    "SUPABASE:",
    response.status_code,
    response.text
        )

        response.raise_for_status()

        data = response.json()

        return [
            str(item["chat_id"])
            for item in data
            if item.get("chat_id")
        ]

    except Exception as e:

        print(
            "❌ Ошибка получения подписчиков:",
            e
        )

        return []


def add_subscriber(chat_id):

    if not SUPABASE_URL or not SUPABASE_SECRET:
        print("❌ SUPABASE настройки не найдены")
        return False

    url = (
        f"{SUPABASE_URL}"
        f"/rest/v1/subscribers"
    )

    headers = {
        "apikey": SUPABASE_SECRET,
        "Authorization": f"Bearer {SUPABASE_SECRET}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    data = {
        "chat_id": str(chat_id)
    }

    try:

        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=10
        )

        response.raise_for_status()

        return True

    except Exception as e:

        print(
            "❌ Ошибка добавления подписчика:",
            e
        )

        return False


# =========================================================
# НАСТРОЙКИ
# =========================================================

ASTER_BASE = "https://fapi.asterdex.com"

ORDER_THRESHOLD = 15000
MIN_VOLUME = 15000

SCAN_INTERVAL = 30
ALERT_COOLDOWN = 300

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

EXCLUDED_SYMBOLS = {
    "BTCUSDT",
    "ETHUSDT"
}

last_alerts = {}


# =========================================================
# TELEGRAM
# =========================================================
# =========================================================
# TELEGRAM — ОБРАБОТКА КОМАНД
# =========================================================

telegram_offset = 0


def check_telegram_commands():

    global telegram_offset

    if not TELEGRAM_TOKEN:
        return

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_TOKEN}/getUpdates"
    )

    params = {
        "offset": telegram_offset + 1,
        "timeout": 1
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=5
        )

        response.raise_for_status()

        data = response.json()

        if not data.get("ok"):
            return

        for update in data.get("result", []):

            telegram_offset = update["update_id"]

            message = update.get("message")

            if not message:
                continue

            chat = message.get("chat")

            if not chat:
                continue

            chat_id = chat.get("id")

            text = message.get("text", "")

            if text == "/start":

                add_subscriber(chat_id)

                welcome = (
                    "👋 Здравствуйте! "
                    "Добро пожаловать в наш клуб!\n\n"

                    "🤖 Ваш помощник по трейдингу — "
                    "анализирует рынок, ликвидность и стакан, "
                    "помогая находить интересные торговые ситуации.\n\n"

                    "⚠️ Бот создан исключительно для "
                    "информационных рекомендаций и "
                    "не гарантирует прибыль.\n\n"

                    "🧠 А последнее слово — как и в жизни — "
                    "всегда за вами.\n\n"

                    "━━━━━━━━━━━━━━\n\n"

                    "⚡ Бот работает 24/7"
                )

                send_telegram_to_chat(
                    chat_id,
                    welcome
                )

    except Exception as e:

        print(
            "❌ Ошибка Telegram:",
            e
        )

def send_telegram(message):

    subscribers = get_subscribers()

    # Если подписчиков пока нет —
    # используем старый CHAT_ID как запасной вариант
    if not subscribers and CHAT_ID:
        subscribers = [CHAT_ID]

    if not subscribers:

        print(
            "❌ Подписчиков пока нет"
        )

        return

    for chat_id in subscribers:

        send_telegram_to_chat(
            chat_id,
            message
        )


# =========================================================
# СТАКАН
# =========================================================

def get_order_book(symbol):

    try:

        url = f"{ASTER_BASE}/fapi/v1/depth"

        params = {
            "symbol": symbol,
            "limit": 100
        }

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        bids = data.get("bids", [])
        asks = data.get("asks", [])

        buy_total = sum(
            float(price) * float(quantity)
            for price, quantity in bids
        )

        sell_total = sum(
            float(price) * float(quantity)
            for price, quantity in asks
        )

        best_bid = None
        best_ask = None

        if bids:
            best_bid = float(bids[0][0])

        if asks:
            best_ask = float(asks[0][0])

        return (
            buy_total,
            sell_total,
            best_bid,
            best_ask
        )

    except Exception as e:

        print(
            f"Ошибка стакана {symbol}:",
            e
        )

        return (
            0,
            0,
            None,
            None
        )


# =========================================================
# ПРОВЕРКА ОСНОВНОГО СИГНАЛА
# =========================================================

def check_symbol(symbol, volume):

    try:

        url = f"{ASTER_BASE}/fapi/v1/klines"

        params = {
            "symbol": symbol,
            "interval": "1m",
            "limit": 3
        }

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        klines = response.json()

        if not klines or len(klines) < 2:
            return None

        # Последняя свеча может быть текущей
        current_candle = klines[-1]

        # Предыдущая свеча уже закрыта
        closed_candle = klines[-2]

        current_open = float(
            current_candle[1]
        )

        current_close = float(
            current_candle[4]
        )

        closed_open = float(
            closed_candle[1]
        )

        closed_close = float(
            closed_candle[4]
        )

        if current_open == 0 or closed_open == 0:
            return None

        change_current = (
            (current_close - current_open)
            / current_open
        ) * 100

        change_closed = (
            (closed_close - closed_open)
            / closed_open
        ) * 100

        # =================================================
        # СИЛЬНОЕ ДВИЖЕНИЕ
        # =================================================

        strong_rise = (
            change_current >= 3
            or
            change_closed >= 3
        )

        strong_fall = (
            change_current <= -3
            or
            change_closed <= -3
        )

        # Если нет сильного движения —
        # стакан пока не проверяем
        if not strong_rise and not strong_fall:
            return None

        # =================================================
        # СТАКАН
        # =================================================

        (
            buy_total,
            sell_total,
            best_bid,
            best_ask
        ) = get_order_book(symbol)

        signal = None

        entry = None
        stop = None
        tp1 = None
        tp2 = None

        # =================================================
        # СИЛЬНЫЙ BUY
        # =================================================

        if (
            strong_rise
            and buy_total >= ORDER_THRESHOLD
            and buy_total > sell_total
        ):

            signal = "🚀 СИЛЬНЫЙ BUY"

            if best_ask:
                entry = best_ask
                stop = entry * 0.99
                tp1 = entry * 1.015
                tp2 = entry * 1.025

        # =================================================
        # СИЛЬНЫЙ SELL
        # =================================================

        elif (
            strong_fall
            and sell_total >= ORDER_THRESHOLD
            and sell_total > buy_total
        ):

            signal = "🚨 СИЛЬНЫЙ SELL"

            if best_bid:
                entry = best_bid
                stop = entry * 1.01
                tp1 = entry * 0.985
                tp2 = entry * 0.975

        if not signal:
            return None

        return {
            "symbol": symbol,
            "signal": signal,

            "change_current": change_current,
            "change_closed": change_closed,

            "buy": buy_total,
            "sell": sell_total,

            "entry": entry,
            "stop": stop,
            "tp1": tp1,
            "tp2": tp2,

            "key": f"{symbol}:{signal}"
        }

    except Exception as e:

        print(
            f"Ошибка проверки {symbol}:",
            e
        )

        return None


# =========================================================
# ОТПРАВКА ОСНОВНОГО СИГНАЛА
# =========================================================

def send_signal(result):

    if not result:
        return

    key = result["key"]

    now = time.time()

    # Не отправляем тот же сигнал
    # чаще одного раза в 5 минут
    if key in last_alerts:

        if now - last_alerts[key] < ALERT_COOLDOWN:
            return

    last_alerts[key] = now

    levels = ""

    if (
        result["signal"] == "🚀 СИЛЬНЫЙ BUY"
        and result.get("entry")
    ):

        levels = (
            "\n\n"
            "🎯 ТОЧКА ВХОДА\n"
            f"💵 Вход: {result['entry']:.8f}\n"
            f"🛑 Stop Loss: {result['stop']:.8f}\n"
            f"🎯 TP1: {result['tp1']:.8f}\n"
            f"🎯 TP2: {result['tp2']:.8f}"
        )

    elif (
        result["signal"] == "🚨 СИЛЬНЫЙ SELL"
        and result.get("entry")
    ):

        levels = (
            "\n\n"
            "🎯 ТОЧКА ВХОДА\n"
            f"💵 Вход: {result['entry']:.8f}\n"
            f"🛑 Stop Loss: {result['stop']:.8f}\n"
            f"🎯 TP1: {result['tp1']:.8f}\n"
            f"🎯 TP2: {result['tp2']:.8f}"
        )

    message = (
        "🚨 СИГНАЛ Aster DEX\n\n"

        f"💲 {result['symbol']}\n"
        f"📌 Сигнал: {result['signal']}\n\n"

        f"📈 1M текущая: "
        f"{result['change_current']:+.2f}%\n"

        f"🕐 1M закрытая: "
        f"{result['change_closed']:+.2f}%\n\n"

        f"🟢 BUY ≥ $15k: "
        f"${result['buy']:,.0f}\n"

        f"🔴 SELL ≥ $15k: "
        f"${result['sell']:,.0f}"

        f"{levels}"
    )

    print(message)

    send_telegram(message)

def get_symbols():

    try:

        url = f"{ASTER_BASE}/fapi/v1/ticker/24hr"

        response = requests.get(
            url,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        symbols = []

        for item in data:

            symbol = item.get("symbol")

            if not symbol:
                continue

            if not symbol.endswith("USDT"):
                continue

            if symbol in EXCLUDED_SYMBOLS:
                continue

            volume = float(
                item.get("quoteVolume", 0)
            )

            if volume < MIN_VOLUME:
                continue

            symbols.append(
                (
                    symbol,
                    volume
                )
            )

        return symbols

    except Exception as e:

        print(
            "❌ Ошибка получения списка монет:",
            e
        )

        return []


# =========================================================
# ОСНОВНОЙ СКАН
# =========================================================

def scan():

    print(
        "\n"
        "=============================="
    )

    print(
        "🔥 Aster DEX — новый скан"
    )

    print(
        "=============================="
    )

    symbols = get_symbols()

    print(
        f"✅ Монет для проверки: "
        f"{len(symbols)}"
    )

    results = []

    # =====================================================
    # ОСНОВНАЯ ПРОВЕРКА
    # =====================================================

    with ThreadPoolExecutor(
        max_workers=10
    ) as executor:

        futures = {}

        for symbol, volume in symbols:

            future = executor.submit(
                check_symbol,
                symbol,
                volume
            )

            futures[future] = symbol

        for future in as_completed(futures):

            symbol = futures[future]

            try:

                result = future.result()

                if result:
                    results.append(result)

            except Exception as e:

                print(
                    f"Ошибка результата {symbol}:",
                    e
                )

    # =====================================================
    # ОСНОВНЫЕ СИГНАЛЫ
    # =====================================================

    if results:

        print(
            f"\n🚨 Найдено сигналов: "
            f"{len(results)}"
        )

        for result in results:

            send_signal(result)

    else:

        print(
            "⚪ Подходящих сигналов нет"
        )
   

# =========================================================
# ЗАПУСК МОНИТОРА
# =========================================================


def main():

    import threading

    telegram_thread = threading.Thread(
        target=poll_telegram,
        daemon=True
    )

    telegram_thread.start()

    print(
        "🚀 Aster Monitor запущен"
    )

    print(
        "🚫 BTCUSDT и ETHUSDT исключены"
    )

    print(
        "📊 Порог движения: ±3% за 1M"
    )

    print(
        "💰 Порог стакана: $15,000"
    )

    print(
        "⏱ Интервал сканирования: 30 секунд"
    )

    print(
        "=============================="
    )

    while True:

        try:

            scan()

        except Exception as e:

            print(
                "❌ Критическая ошибка скана:",
                e
            )

        print(
            "\n🔄 Следующий скан через "
            f"{SCAN_INTERVAL} секунд.."
        )

        time.sleep(
            SCAN_INTERVAL
        )

# =========================================================
# TELEGRAM — ПОДПИСКА ПОЛЬЗОВАТЕЛЕЙ
# =========================================================

def send_telegram_to_chat(chat_id, message):

    if not TELEGRAM_TOKEN:
        return

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_TOKEN}/sendMessage"
    )

    data = {
        "chat_id": str(chat_id),
        "text": message
    }

    try:

        response = requests.post(
            url,
            json=data,
            timeout=10
        )

        response.raise_for_status()

    except Exception as e:

        print(
            f"❌ Ошибка отправки {chat_id}:",
            e
        )


def poll_telegram():

    offset = None

    print(
        "📩 Telegram подписки запущены"
    )

    while True:

        try:

            url = (
                f"https://api.telegram.org/"
                f"bot{TELEGRAM_TOKEN}/getUpdates"
            )

            params = {
                "timeout": 25
            }

            if offset is not None:
                params["offset"] = offset

            response = requests.get(
                url,
                params=params,
                timeout=35
            )

            response.raise_for_status()

            updates = response.json().get(
                "result",
                []
            )

            for update in updates:

                offset = update["update_id"] + 1

                message = update.get(
                    "message"
                )

                if not message:
                    continue

                chat = message.get(
                    "chat",
                    {}
                )

                chat_id = chat.get(
                    "id"
                )

                text = (
                    message.get("text") or ""
                ).strip()

                if not chat_id:
                    continue

                if text.startswith("/start"):

                    if add_subscriber(chat_id):

                        send_telegram_to_chat(
    chat_id,
    "👋 Здравствуйте! "
    "Добро пожаловать в наш клуб!\n\n"

    "🤖 Ваш помощник по трейдингу — "
    "анализирует рынок, ликвидность и стакан, "
    "помогая находить интересные торговые ситуации.\n\n"

    "⚠️ Бот создан исключительно для "
    "информационных рекомендаций и "
    "не гарантирует прибыль.\n\n"

    "🧠 А последнее слово — как и в жизни — "
    "всегда за вами.\n\n"

    "━━━━━━━━━━━━━━\n\n"

    "⚡ Бот работает 24/7\n\n"

    "✅ Ты подписан на сигналы Aster DEX!\n\n"
    "🔥 Бот будет автоматически присылать "
    "сигналы Aster DEX.\n\n"

    "📊 Порог движения: ±3% за 1M\n"
    "💰 Стакан: от $15,000"
)

        except Exception as e:

            print(
                "❌ Ошибка Telegram:",
                e
            )

            time.sleep(5)
            
# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    main()
