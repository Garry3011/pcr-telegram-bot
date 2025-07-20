import requests
from datetime import datetime, timezone
from urllib.parse import quote_plus
import asyncio
from telegram import Bot

# Telegram Config
BOT_TOKEN = "8194009496:AAErt7jbq-TKPxzEByiTFyU0aIYfCDg2zcI"
CHAT_ID = 1092736863  # Your Telegram chat ID as integer

# Deribit API endpoints
DERIBIT_INSTRUMENTS_URL = "https://www.deribit.com/api/v2/public/get_instruments?currency={symbol}&kind=option"

def fetch_instruments(symbol):
    print(f"{symbol}: \U0001F50D Fetching instruments...")
    url = DERIBIT_INSTRUMENTS_URL.format(symbol=symbol)
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        instruments = data.get('result', [])
        option_instruments = [inst for inst in instruments if inst.get('option_type') in ['call', 'put']]
        print(f"{symbol}: ✅ Found {len(option_instruments)} option instruments")
        return option_instruments
    except requests.RequestException as e:
        print(f"{symbol}: ❌ API request failed: {e}")
        return []

def filter_near_expiry_options(options):
    near_expiry = []
    today = datetime.now(timezone.utc)
    for option in options:
        expiry_ts = option.get('expiration_timestamp')
        if expiry_ts:
            expiry_date = datetime.fromtimestamp(expiry_ts / 1000, timezone.utc)
            if 0 <= (expiry_date - today).days <= 7:
                near_expiry.append(option)
    print(f"📆 Near-expiry options = {len(near_expiry)}")
    return near_expiry

def fetch_option_open_interest(instrument_name):
    instrument_name_clean = instrument_name.strip().upper()
    encoded_name = quote_plus(instrument_name_clean)
    url = f"https://www.deribit.com/api/v2/public/ticker?instrument_name={encoded_name}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        ticker = data.get('result', {})
        oi = ticker.get('open_interest', 0)
        return oi
    except requests.HTTPError as e:
        if response.status_code == 400:
            print(f"Skipping invalid instrument (400 error): {instrument_name_clean}")
            return 0
        else:
            print(f"Failed to fetch ticker for {instrument_name_clean}: {e}")
            return 0
    except requests.RequestException as e:
        print(f"Failed to fetch ticker for {instrument_name_clean}: {e}")
        return 0

def calculate_pcr(options):
    call_oi = 0
    put_oi = 0
    for opt in options:
        oi = fetch_option_open_interest(opt['instrument_name'])
        opt_type = opt.get('option_type')
        print(f"Instrument: {opt['instrument_name']}, Type: {opt_type}, Open Interest: {oi}")
        if opt_type == 'call':
            call_oi += oi
        elif opt_type == 'put':
            put_oi += oi

    pcr = put_oi / call_oi if call_oi else 0
    print(f"Total Call OI: {call_oi}, Total Put OI: {put_oi}, PCR: {pcr}")
    return round(pcr, 2), call_oi, put_oi

def get_signal(pcr):
    if pcr < 0.7:
        return "📈 Buy Signal"
    elif pcr > 1.0:
        return "📉 Sell Signal"
    else:
        return "⚪ Neutral"

def get_symbol_report(symbol):
    instruments = fetch_instruments(symbol)
    near_expiry = filter_near_expiry_options(instruments)
    pcr, call_oi, put_oi = calculate_pcr(near_expiry)
    signal = get_signal(pcr)

    return (f"<b>{symbol} PCR</b>\n"
            f"PCR: {pcr}\n"
            f"Call OI: {call_oi}\n"
            f"Put OI: {put_oi}\n"
            f"Options Count: {len(near_expiry)}\n"
            f"Signal: {signal}")

async def main():
    print("\U0001F504 Fetching PCR data...")
    report_lines = []
    for sym in ["BTC", "ETH"]:
        report = get_symbol_report(sym)
        report_lines.append(report)

    message = "\n\n".join(report_lines)
    print("\U0001F4E4 Sending message to Telegram...")
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='HTML')

if __name__ == "__main__":
    asyncio.run(main())
