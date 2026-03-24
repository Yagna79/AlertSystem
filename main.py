import requests
import pandas as pd
import time
import os
from datetime import datetime, timezone

# ===== LOAD ENV VARIABLES =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

print("🚀 Bot starting...")
print("BOT_TOKEN:", BOT_TOKEN)
print("CHAT_ID:", CHAT_ID)

SYMBOLS = ["BTCUSD", "ETHUSD", "SOLUSD"]

# ===== TELEGRAM FUNCTION =====
def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    try:
        response = requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": message
        })
        print("Telegram response:", response.text)
    except Exception as e:
        print("Telegram Error:", e)

# ===== SEND TEST MESSAGE ON START =====
send_telegram("🚀 Bot started successfully on Railway!")

# ===== GET MARKET DATA =====
def get_data(symbol):
    url = "https://api.delta.exchange/v2/history/candles"
    params = {
        "symbol": symbol,
        "resolution": "240",  # 4H timeframe
        "limit": 200
    }

    response = requests.get(url, params=params).json()
    df = pd.DataFrame(response['result'])
    df = df.astype(float)

    return df

# ===== GET START OF DAY PRICE =====
def get_day_open(symbol):
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    url = "https://api.delta.exchange/v2/history/candles"
    params = {
        "symbol": symbol,
        "resolution": "60",  # 1H candles
        "start": int(start.timestamp()),
        "limit": 1
    }

    response = requests.get(url, params=params).json()
    df = pd.DataFrame(response['result'])
    df = df.astype(float)

    return df.iloc[0]['open']

# ===== SUPER TREND (ATR 16, MULTIPLIER 1.5) =====
def supertrend(df, period=16, multiplier=1.5):
    df['hl2'] = (df['high'] + df['low']) / 2

    df['tr'] = df[['high', 'low', 'close']].max(axis=1) - df[['high', 'low', 'close']].min(axis=1)
    df['atr'] = df['tr'].rolling(period).mean()

    df['upper'] = df['hl2'] + (multiplier * df['atr'])
    df['lower'] = df['hl2'] - (multiplier * df['atr'])

    df['trend'] = 1

    for i in range(1, len(df)):
        if df['close'][i] > df['upper'][i - 1]:
            df.at[i, 'trend'] = 1
        elif df['close'][i] < df['lower'][i - 1]:
            df.at[i, 'trend'] = -1
        else:
            df.at[i, 'trend'] = df['trend'][i - 1]

    return df

# ===== SIGNAL LOGIC =====
def check_signal(df):
    latest = df.iloc[-1]
    atr = latest['atr']
    trend = latest['trend']

    avg_atr = df['atr'].rolling(50).mean().iloc[-1]

    if atr < avg_atr:
        return "RANGE"

    return "UPTREND" if trend == 1 else "DOWNTREND"

# ===== MAIN LOOP =====
while True:
    try:
        message = "📊 LIVE MARKET DASHBOARD (4H)\n\n"

        for symbol in SYMBOLS:
            df = get_data(symbol)
            df = supertrend(df)

            signal = check_signal(df)
            price = df.iloc[-1]['close']

            day_open = get_day_open(symbol)
            change_pct = ((price - day_open) / day_open) * 100

            if signal == "RANGE":
                emoji = "🟡"
                action = "SELL STRADDLE"
            elif signal == "UPTREND":
                emoji = "🟢"
                action = "SELL PUT"
            else:
                emoji = "🔴"
                action = "SELL CALL"

            message += f"""{emoji} {symbol}
Price: {round(price,2)}
Day: {round(change_pct,2)}%
Signal: {signal} → {action}

"""

        send_telegram(message)

        print("✅ Dashboard sent successfully")
        time.sleep(600)  # 10 minutes

    except Exception as e:
        print("❌ Error:", e)
        send_telegram(f"⚠️ Error: {e}")
        time.sleep(60)
