#!/usr/bin/env python3
"""
Symbol management script - Python version av tickers.php
Synkar symbols med Bybit API:
- Lägger till nya symbols
- Tar bort delistade symbols
- Uppdaterar ticker data
"""

import pymysql
import requests
import json
from datetime import datetime

# Databaskonfiguration
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'database': 'smartchart',
    'user': 'root',
    'password': 'root',
    'charset': 'utf8mb4'
}

def get_db_connection():
    """Skapa databaskoppling"""
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)

def fetch_tickers():
    """Hämta alla tickers från Bybit API"""
    url = "https://api.bybit.com/v5/market/tickers?category=linear"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if data.get('retCode') == 0 and 'result' in data and 'list' in data['result']:
            return data['result']['list']
        else:
            print(f"API error: {data}")
            return []
    except Exception as e:
        print(f"Error fetching tickers: {e}")
        return []

def get_db_symbols(conn):
    """Hämta alla symbols från databasen"""
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT symbol FROM tickers")
    symbols = [row['symbol'] for row in cursor.fetchall()]
    cursor.close()
    return symbols

def add_new_symbols(conn, symbols):
    """Lägg till nya symbols i databasen"""
    # Denna funktion behövs inte längre eftersom vi lägger till symbols via update_tickers
    pass

def remove_symbols(conn, symbols):
    """Ta bort symbols som inte längre finns"""
    if not symbols:
        return
    
    cursor = conn.cursor()
    
    # Lista av tabeller att rensa från
    tables = [
        'tickers',
        'klines'  # Vår klines tabell
    ]
    
    for table in tables:
        placeholders = ','.join(['%s'] * len(symbols))
        query = f"DELETE FROM {table} WHERE symbol IN ({placeholders})"
        cursor.execute(query, symbols)
        print(f"Removed {cursor.rowcount} rows from {table}")
    
    conn.commit()
    cursor.close()

def update_tickers(conn, tickers_data):
    """Uppdatera tickers tabell med senaste data"""
    if not tickers_data:
        return
    
    cursor = conn.cursor()
    
    # Först, rensa gamla tickers
    cursor.execute("TRUNCATE TABLE tickers")
    
    # Helper functions för säker konvertering
    def safe_float(val):
        return float(val) if val else None
    
    def safe_int(val):
        return int(val) if val else None
    
    # Förbered data för insert
    inserted_count = 0
    for ticker in tickers_data:
        # Filtrera bara USDT perpetuals
        if ticker.get('symbol', '').endswith('USDT'):
            cursor.execute("""
            INSERT INTO tickers (
                symbol, lastPrice, indexPrice, markPrice, prevPrice24h, price24hPcnt,
                highPrice24h, lowPrice24h, prevPrice1h, openInterest, openInterestValue,
                turnover24h, volume24h, fundingRate, nextFundingTime, predictedDeliveryPrice,
                basisRate, deliveryFeeRate, deliveryTime, ask1Size, bid1Price,
                ask1Price, bid1Size, basis
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """, (
                ticker['symbol'],
                safe_float(ticker.get('lastPrice')),
                safe_float(ticker.get('indexPrice')),
                safe_float(ticker.get('markPrice')),
                safe_float(ticker.get('prevPrice24h')),
                safe_float(ticker.get('price24hPcnt')),
                safe_float(ticker.get('highPrice24h')),
                safe_float(ticker.get('lowPrice24h')),
                safe_float(ticker.get('prevPrice1h')),
                safe_float(ticker.get('openInterest')),
                safe_float(ticker.get('openInterestValue')),
                safe_float(ticker.get('turnover24h')),
                safe_float(ticker.get('volume24h')),
                safe_float(ticker.get('fundingRate')),
                safe_int(ticker.get('nextFundingTime')),
                safe_float(ticker.get('predictedDeliveryPrice')),
                safe_float(ticker.get('basisRate')),
                safe_float(ticker.get('deliveryFeeRate')),
                safe_int(ticker.get('deliveryTime')),
                safe_float(ticker.get('ask1Size')),
                safe_float(ticker.get('bid1Price')),
                safe_float(ticker.get('ask1Price')),
                safe_float(ticker.get('bid1Size')),
                ticker.get('basis', '')
            ))
            inserted_count += 1
    
    conn.commit()
    cursor.close()
    print(f"Updated {inserted_count} tickers")

def main():
    """Huvudfunktion"""
    print(f"\n{'='*60}")
    print(f"Symbol Manager - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # Hämta ticker data från API
    print("Fetching tickers from Bybit API...")
    api_tickers = fetch_tickers()
    
    if not api_tickers:
        print("ERROR: No tickers received from API")
        return
    
    # Extrahera bara USDT perpetual symbols
    api_symbols = []
    for ticker in api_tickers:
        symbol = ticker.get('symbol', '')
        if symbol.endswith('USDT'):
            api_symbols.append(symbol)
    
    print(f"Found {len(api_symbols)} USDT perpetual symbols from API")
    
    # Anslut till databasen
    conn = get_db_connection()
    
    try:
        # Hämta befintliga symbols från databasen
        db_symbols = get_db_symbols(conn)
        print(f"Found {len(db_symbols)} symbols in database")
        
        # Beräkna skillnader
        symbols_to_add = list(set(api_symbols) - set(db_symbols))
        symbols_to_remove = list(set(db_symbols) - set(api_symbols))
        
        print(f"\nChanges detected:")
        print(f"- Symbols to add: {len(symbols_to_add)}")
        print(f"- Symbols to remove: {len(symbols_to_remove)}")
        
        # Nya symbols kommer automatiskt att läggas till via update_tickers
        if symbols_to_add:
            print(f"\nNew symbols to be added via tickers update:")
            for symbol in sorted(symbols_to_add):
                print(f"  + {symbol}")
        
        # Ta bort gamla symbols
        if symbols_to_remove:
            print(f"\nRemoving delisted symbols:")
            for symbol in sorted(symbols_to_remove):
                print(f"  - {symbol}")
            remove_symbols(conn, symbols_to_remove)
        
        # Uppdatera tickers tabell
        print("\nUpdating tickers table...")
        update_tickers(conn, api_tickers)
        
        print("\n✓ Symbol management completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Error during symbol management: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()