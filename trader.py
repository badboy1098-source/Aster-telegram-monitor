import os
import time
import math
import requests


# =========================================================
# ASTER AUTO TRADER
# PAPER MODE — РЕАЛЬНЫЕ ОРДЕРА ПОКА ОТКЛЮЧЕНЫ
# =========================================================

ASTER_BASE = "https://fapi.asterdex.com"

# ---------------------------------------------------------
# ОСНОВНЫЕ НАСТРОЙКИ
# ---------------------------------------------------------

AUTO_TRADE = False

RISK_PER_TRADE = 0.01          # 1%
MIN_RR = 3.0                    # минимум 1:3
MAX_OPEN_POSITIONS = 3

ALLOWED_SYMBOLS = set()         # пока пусто — сделки не открываются

TRADER_CHAT_ID = os.getenv("TRADER_CHAT_ID")

# Защита от повторных сделок
active_trades = {}
completed_trade_ids = set()


# =========================================================
# УТИЛИТЫ
# =========================================================

def log(message):
    print(f"[TRADER] {message}", flush=True)


def get_account_balance():
    """
    Пока PAPER MODE.
    Позже здесь будет получение реального баланса Aster.
    """
    return None


def calculate_position_size(
    balance,
    entry_price,
    stop_price,
    risk_percent=RISK_PER_TRADE
):
    """
    Рассчитывает размер позиции так,
    чтобы риск до SL составлял не более заданного процента.
    """

    if balance <= 0:
        return 0

    if entry_price <= 0 or stop_price <= 0:
        return 0

    stop_distance = abs(entry_price - stop_price)

    if stop_distance <= 0:
        return 0

    risk_amount = balance * risk_percent

    quantity = risk_amount / stop_distance

    return quantity


def calculate_rr(entry, stop, target):
    """
    Расчёт Risk/Reward.
    """

    risk = abs(entry - stop)

    if risk <= 0:
        return 0

    reward = abs(target - entry)

    return reward / risk


# =========================================================
# ПРОВЕРКА СИГНАЛА
# =========================================================

def validate_trade_signal(signal):
    """
    Финальная проверка перед потенциальным входом.

    Здесь позже будут:
    - Score ASTER PRO
    - 1H trend
    - 15M structure
    - 5M confirmation
    - 1M confirmation
    - RSI
    - EMA
    - MACD
    - ATR
    - volume
    - order book
    - overextension
    - RR
    """

    if not signal:
        return False, "Пустой сигнал"

    symbol = signal.get("symbol")

    if not symbol:
        return False, "Нет символа"

    if symbol not in ALLOWED_SYMBOLS:
        return False, f"{symbol} пока не разрешён"

    side = signal.get("side")

    if side not in ("LONG", "SHORT"):
        return False, "Неверное направление"

    entry = signal.get("entry")
    stop = signal.get("stop")
    target = signal.get("target")

    if not all([entry, stop, target]):
        return False, "Не хватает Entry / SL / TP"

    rr = calculate_rr(entry, stop, target)

    if rr < MIN_RR:
        return False, f"RR {rr:.2f} меньше минимального {MIN_RR}"

    return True, "Сигнал прошёл базовую проверку"


# =========================================================
# PAPER TRADE
# =========================================================

def paper_trade(signal):
    """
    Имитация сделки.
    Реальный ордер НЕ отправляется.
    """

    symbol = signal["symbol"]

    if symbol in active_trades:
        log(
            f"⛔ {symbol}: позиция уже существует. "
            f"Повторный вход запрещён."
        )
        return False

    valid, reason = validate_trade_signal(signal)

    if not valid:
        log(f"❌ {symbol}: {reason}")
        return False

    entry = float(signal["entry"])
    stop = float(signal["stop"])
    target = float(signal["target"])

    # Временно используем тестовый баланс.
    # Позже здесь будет реальный баланс Aster.
    paper_balance = float(
        signal.get("paper_balance", 1000)
    )

    quantity = calculate_position_size(
        paper_balance,
        entry,
        stop
    )

    rr = calculate_rr(
        entry,
        stop,
        target
    )

    trade_id = (
        f"{symbol}_"
        f"{signal['side']}_"
        f"{entry}"
    )

    if trade_id in completed_trade_ids:
        log(f"⛔ Дубликат сделки: {trade_id}")
        return False

    active
