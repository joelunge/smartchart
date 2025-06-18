from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pymysql
pymysql.install_as_MySQLdb()
import MySQLdb as mysql
import pandas as pd
from datetime import datetime
import json
import os

app = FastAPI()

# CORS middleware för att tillåta requests från webbläsaren
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,  # Standard MySQL port
    'database': 'sct_2024',
    'user': 'root',
    'password': 'root',
    'charset': 'utf8mb4'
}

def get_db_connection():
    """Skapa databaskoppling"""
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)

@app.get("/api/candles/{symbol}")
async def get_candles(symbol: str, timeframe: str = "5m", limit: int = 1000):
    """Hämta candlestick data för en symbol"""
    
    # Välj rätt tabell baserat på timeframe
    table_map = {
        "5m": "candles5",
        "15m": "candles15",
        "1h": "candles60",
        "1d": "candlesd"
    }
    
    if timeframe not in table_map:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe: {timeframe}")
    
    table = table_map[timeframe]
    
    try:
        print(f"Fetching candles for {symbol}, timeframe={timeframe}, table={table}")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Först, kontrollera om tabellen och data finns
        cursor.execute(f"SELECT COUNT(*) as count FROM {table} WHERE symbol = %s", (symbol,))
        count_result = cursor.fetchone()
        print(f"Found {count_result['count']} rows for symbol={symbol}")
        
        query = f"""
        SELECT 
            UNIX_TIMESTAMP(startTime) as time,
            openPrice as open,
            highPrice as high,
            lowPrice as low,
            closePrice as close,
            volume
        FROM {table}
        WHERE symbol = %s
        ORDER BY startTime DESC
        LIMIT %s
        """
        
        cursor.execute(query, (symbol, limit))
        data = cursor.fetchall()
        print(f"Fetched {len(data)} candles")
        
        # Konvertera till rätt format och vänd ordningen
        data = data[::-1]  # Äldsta först
        
        # Konvertera decimaler till float
        for candle in data:
            candle['time'] = int(candle['time'])
            candle['open'] = float(candle['open'])
            candle['high'] = float(candle['high'])
            candle['low'] = float(candle['low'])
            candle['close'] = float(candle['close'])
            candle['volume'] = float(candle['volume'])
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "data": data,
            "count": len(data),
            "symbol": symbol,
            "timeframe": timeframe
        }
        
    except pymysql.Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        print(f"General error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/test-db")
async def test_db():
    """Testa databaskopplingen"""
    try:
        print("Trying to connect to database...")
        conn = get_db_connection()
        print("Connected!")
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        cursor.close()
        conn.close()
        return {"success": True, "mysql_version": version['VERSION()']}
    except Exception as e:
        print(f"Error type: {type(e).__name__}")
        print(f"Error details: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e), "error_type": type(e).__name__}

@app.get("/api/symbols")
async def get_symbols():
    """Hämta alla tillgängliga symboler"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT id, symbol
        FROM symbols
        ORDER BY symbol
        """
        
        cursor.execute(query)
        symbols = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "symbols": symbols
        }
        
    except pymysql.Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        print(f"General error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Root endpoint för index.html
@app.get("/")
async def read_root():
    return FileResponse("index.html")

# Servera statiska filer (HTML, CSS, JS) - men inte på root
# app.mount("/static", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    print("Starting SmartChart API server...")
    print("Open http://localhost:8000 in your browser")
    uvicorn.run(app, host="0.0.0.0", port=8000)