#!/usr/bin/env python3
"""
Sync all kline data - Med separata tabeller per timeframe för optimal performance
Baserat på användarens beprövade produktionssystem
"""

import asyncio
import aiohttp
import aiomysql
import time
import json
from datetime import datetime
import pymysql.err
import sys
import os

# Setup logging to both file and terminal
class DualOutput:
    def __init__(self, file_path):
        self.terminal = sys.stdout
        self.log_file = open(file_path, 'a', encoding='utf-8')
        
    def write(self, message):
        self.terminal.write(message)
        self.terminal.flush()  # Flush terminal direkt
        self.log_file.write(message)
        self.log_file.flush()  # Säkerställ att allt skrivs direkt
        
    def flush(self):
        self.terminal.flush()
        self.log_file.flush()
        
    def close(self):
        self.log_file.close()

# Skapa loggfil med timestamp
log_filename = f"logs/sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
os.makedirs("logs", exist_ok=True)
dual_output = DualOutput(log_filename)
sys.stdout = dual_output
sys.stderr = dual_output

print(f"Logging to: {log_filename}")

# Databaskonfiguration
DB_HOST = 'localhost'
DB_PORT = 3306
DB_USER = 'root'
DB_PASS = 'root'
DB_NAME = 'smartchart'

DEFAULT_START_TIMESTAMP = int(datetime(2000, 1, 1).timestamp() * 1000)
MAX_CONCURRENT_REQUESTS = 20
REQUESTS_PER_SECOND = 60
MAX_RETRIES = 5
RETRY_DELAY = 0.5

# Lista över timeframes i ordning, störst till minst
timeframes = ["W", "D", "240", "60", "15", "5", "1"]

# Mapping till tabellnamn - EXAKT som originalscriptet
intervals_mapping = {
    "1": "candles1",
    "5": "candles5",
    "15": "candles15",
    "60": "candles60",
    "240": "candles240",
    "D": "candlesd",
    "W": "candlesw"
}

async def get_all_symbols(pool):
    """Hämta alla symbols från databasen"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT symbol FROM tickers ORDER BY turnover24h DESC")
            rows = await cur.fetchall()
    return [r[0] for r in rows]

async def get_last_candle_timestamp(pool, symbol, table_name):
    """Hämta timestamp för senaste candle"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            sql = f"SELECT MAX(open_time) FROM {table_name} WHERE symbol=%s"
            await cur.execute(sql, (symbol,))
            row = await cur.fetchone()
    return row[0] if row and row[0] else None

async def save_candles_to_database(pool, symbol, candles, table_name):
    """Spara candles till rätt tabell"""
    if not candles:
        return

    values = []
    for c in candles:
        open_time = int(c[0])
        open_datetime = datetime.utcfromtimestamp(open_time / 1000).strftime('%Y-%m-%d %H:%M:%S')
        open_price = float(c[1])
        high_price = float(c[2])
        low_price = float(c[3])
        close_price = float(c[4])
        volume = float(c[5])
        turnover = round(float(c[6]))  # Runda för att undvika overflow
        values.append((
            symbol,
            open_time,
            open_datetime,
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
            turnover
        ))

    placeholders = ", ".join(["(%s,%s,%s,%s,%s,%s,%s,%s,%s)"] * len(values))
    sql = f"""
    INSERT INTO {table_name} (symbol, open_time, open_datetime, open, high, low, close, volume, turnover)
    VALUES {placeholders}
    AS new
    ON DUPLICATE KEY UPDATE
        open_datetime=new.open_datetime,
        open=new.open,
        high=new.high,
        low=new.low,
        close=new.close,
        volume=new.volume,
        turnover=new.turnover
    """

    flat_values = []
    for v in values:
        flat_values.extend(v)

    attempt = 0
    while True:
        attempt += 1
        try:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql, tuple(flat_values))
                await conn.commit()
            return
        except pymysql.err.OperationalError as e:
            # Deadlock
            if e.args[0] == 1213 and attempt < MAX_RETRIES:
                print(f"[{symbol}] Deadlock inträffade, försöker igen... ({attempt}/{MAX_RETRIES})")
                await asyncio.sleep(RETRY_DELAY)
                continue
            else:
                print(f"[{symbol}] Fel vid insättning: {e}")
                raise

async def rate_limiter(token_queue: asyncio.Queue, requests_per_second: int):
    """Rate limiter för API requests"""
    interval = 1.0 / requests_per_second
    while True:
        await token_queue.put(None)  
        await asyncio.sleep(interval)

async def fetch_candles(session, symbol, start_timestamp, token_queue, api_interval, max_retries=5):
    """Hämta candles från Bybit API"""
    url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval={api_interval}&limit=1000"
    if start_timestamp is not None:
        url += f"&start={start_timestamp}"

    wait_time = 1
    for attempt in range(1, max_retries+1):
        await token_queue.get()
        token_queue.task_done()

        try:
            async with session.get(url) as resp:
                text = await resp.text()
                if resp.status == 200:
                    try:
                        data = json.loads(text)
                        result = data.get('result', {})
                        return result.get('list', [])
                    except json.JSONDecodeError:
                        print(f"[{symbol}] JSONDecodeError!\nSvar:\n{text}\nFörsök {attempt}/{max_retries}")
                else:
                    print(f"[{symbol}] Fick status {resp.status} istället för 200. Svar: {text} Försök {attempt}/{max_retries}")
        except asyncio.TimeoutError:
            print(f"[{symbol}] Timeout! Försök {attempt}/{max_retries}")
        except Exception as e:
            print(f"[{symbol}] Fel: {type(e).__name__}: {e} Försök {attempt}/{max_retries}")

        if attempt < max_retries:
            await asyncio.sleep(wait_time)
            wait_time *= 2

    print(f"[{symbol}] Kunde inte hämta data efter {max_retries} försök.")
    return []

async def writer_task(pool, queue, table_name):
    """Writer task för att spara candles"""
    while True:
        symbol, candles = await queue.get()
        if symbol is None and candles is None:
            queue.task_done()
            break
        await save_candles_to_database(pool, symbol, candles, table_name)
        queue.task_done()

async def process_symbol(session, pool, queue, token_queue, symbol, table_name, api_interval):
    """Process en symbol"""
    last_timestamp = await get_last_candle_timestamp(pool, symbol, table_name)
    if last_timestamp is None:
        last_timestamp = DEFAULT_START_TIMESTAMP
        print(f"Inga candles i {table_name} för {symbol}. Startar från: {datetime.utcfromtimestamp(last_timestamp/1000)}")

    while True:
        candles = await fetch_candles(session, symbol, last_timestamp, token_queue, api_interval)
        if not candles:
            print(f"Inga fler candles för {symbol} i {table_name}. Klar.")
            break

        candles.sort(key=lambda x: int(x[0]))

        await queue.put((symbol, candles))

        end_ts = int(candles[-1][0])
        last_timestamp = end_ts - 2  # Smart överlapp!
        print(f"Sparade chunk för {symbol} t.o.m: {datetime.utcfromtimestamp(end_ts/1000)}")

        if len(candles) < 1000:
            print(f"Alla candles för {symbol} har hämtats och kommer skrivas i {table_name}.")
            break

async def run_for_interval(interval, pool):
    """Kör synk för en specifik timeframe"""
    api_interval = interval.upper() if interval in ["D", "W"] else interval
    table_name = intervals_mapping[interval]
    
    all_symbols = await get_all_symbols(pool)
    if not all_symbols:
        print("Inga symboler i databasen, hoppar över denna timeframe.")
        return

    print(f"\n{'='*60}")
    print(f"Bearbetar {len(all_symbols)} symboler för interval {interval} (tabell: {table_name})")
    print(f"{'='*60}\n")

    candle_queue = asyncio.Queue()
    writer = asyncio.create_task(writer_task(pool, candle_queue, table_name))

    token_queue = asyncio.Queue()
    rate_task = asyncio.create_task(rate_limiter(token_queue, REQUESTS_PER_SECOND))

    # Skapa session med högre timeout för 1m data som tar längre tid
    timeout = aiohttp.ClientTimeout(total=300, connect=60, sock_read=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = [asyncio.create_task(process_symbol(session, pool, candle_queue, token_queue, sym, table_name, api_interval)) for sym in all_symbols]
        await asyncio.gather(*tasks)

    await candle_queue.put((None, None))
    print(f"[{table_name}] Alla API-hämtningar klara, väntar på att writer ska bli klar...")
    await candle_queue.join()
    await writer
    print(f"[{table_name}] Writer klar! All data sparad till databas.")

    rate_task.cancel()

async def main():
    """Huvudfunktion"""
    start_time = time.time()
    
    print(f"\n{'='*60}")
    print(f"SmartChart Data Sync - Med separata tabeller")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # Först, kör sync_tickers för att uppdatera symbols och tickers
    print("\nSynkar tickers med Bybit...")
    import subprocess
    # Kör utan capture_output så det printas direkt
    subprocess.run(['python', 'sync_tickers.py'])
    
    print("\nStartar datasynk...")

    pool = await aiomysql.create_pool(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, db=DB_NAME,
        autocommit=False, minsize=1, maxsize=MAX_CONCURRENT_REQUESTS*2
    )

    # Iterera över alla timeframes från störst till minst
    for interval in timeframes:
        await run_for_interval(interval, pool)

    pool.close()
    await pool.wait_closed()

    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\n{'='*60}")
    print(f"Scriptet kördes klart på {duration:.0f} sekunder ({duration/60:.1f} minuter)")
    print(f"{'='*60}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        # Stäng loggfilen
        print(f"\nLog saved to: {log_filename}")
        sys.stdout = dual_output.terminal
        sys.stderr = dual_output.terminal
        dual_output.close()