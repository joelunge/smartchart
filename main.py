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
from indicators import calculate_macd, calculate_volatility, calculate_dual_ema, calculate_rsi

app = FastAPI()

# CORS middleware to allow requests from the browser
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
    'database': 'smartchart',  # Dedicated database
    'user': 'root',
    'password': 'root',
    'charset': 'utf8mb4'
}

def get_db_connection():
    """Create database connection"""
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)

@app.get("/api/candles/{symbol}")
async def get_candles(symbol: str, timeframe: str = "60", limit: int = 20000, include_indicators: bool = True):
    """Fetch candlestick data from the right table based on timeframe"""
    
    # Mapping of timeframe to table name
    timeframe_tables = {
        '1': 'candles1',
        '5': 'candles5',
        '15': 'candles15',
        '60': 'candles60',
        '240': 'candles240',
        'D': 'candlesd',
        'W': 'candlesw'
    }
    
    # Validate timeframe
    if timeframe not in timeframe_tables:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe: {timeframe}")
    
    table_name = timeframe_tables[timeframe]
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Fetch from the right table
        query = f"""
        SELECT 
            open_time / 1000 as time,
            open,
            high,
            low,
            close,
            volume
        FROM {table_name}
        WHERE symbol = %s
        ORDER BY open_time DESC
        LIMIT %s
        """
        
        cursor.execute(query, (symbol, limit))
        data = cursor.fetchall()
        
        # Reverse order (oldest first for charts)
        data = data[::-1]
        
        # Convert to the right format
        formatted_data = []
        closing_prices = []
        for candle in data:
            formatted_data.append({
                'time': int(candle['time']),
                'open': float(candle['open']),
                'high': float(candle['high']),
                'low': float(candle['low']),
                'close': float(candle['close']),
                'volume': float(candle['volume'])
            })
            closing_prices.append(float(candle['close']))
        
        cursor.close()
        conn.close()
        
        # Calculate indicators if requested
        indicators = {}
        if include_indicators and len(closing_prices) > 0:
            # Calculate MACD
            macd_result = calculate_macd(closing_prices)
            indicators['macd'] = macd_result
            
            # Calculate Volatility
            volatility_result = calculate_volatility(closing_prices)
            indicators['volatility'] = volatility_result
            
            # Calculate dual EMA
            dual_ema_result = calculate_dual_ema(closing_prices)
            indicators['dual_ema'] = dual_ema_result
            
            # Calculate RSI
            rsi_result = calculate_rsi(closing_prices)
            indicators['rsi'] = rsi_result
        
        # Adjust timeframe display for D and W
        tf_display = timeframe
        if timeframe == 'D':
            tf_display = '1D'
        elif timeframe == 'W':
            tf_display = '1W'
        elif timeframe not in ['D', 'W']:
            tf_display = f"{timeframe}m"
        
        return {
            "success": True,
            "data": formatted_data,
            "indicators": indicators,
            "count": len(formatted_data),
            "symbol": symbol,
            "timeframe": tf_display
        }
        
    except Exception as e:
        print(f"Error fetching candles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/test-db")
async def test_db():
    """Test database connection"""
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

@app.get("/api/indicators/{indicator}/{symbol}")
async def get_indicator(indicator: str, symbol: str, timeframe: str = "60", limit: int = 1000):
    """Fetch indicator data for a symbol"""
    
    # Validate timeframe
    timeframe_tables = {
        '1': 'candles1',
        '5': 'candles5',
        '15': 'candles15',
        '60': 'candles60',
        '240': 'candles240',
        'D': 'candlesd',
        'W': 'candlesw'
    }
    
    if timeframe not in timeframe_tables:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe: {timeframe}")
    
    table_name = timeframe_tables[timeframe]
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Fetch candlestick data
        query = f"""
        SELECT 
            open_time / 1000 as time,
            close
        FROM {table_name}
        WHERE symbol = %s
        ORDER BY open_time DESC
        LIMIT %s
        """
        
        cursor.execute(query, (symbol, limit))
        data = cursor.fetchall()
        
        # Reverse order (oldest first)
        data = data[::-1]
        
        # Extract prices
        times = [int(row['time']) for row in data]
        prices = [float(row['close']) for row in data]
        
        # Calculate indicator
        if indicator.lower() == 'macd':
            result = calculate_macd(prices)
            
            # Format for charts
            formatted_data = []
            for i in range(len(times)):
                formatted_data.append({
                    'time': times[i],
                    'macd': result['macd'][i],
                    'signal': result['signal'][i],
                    'histogram': result['histogram'][i]
                })
            
            cursor.close()
            conn.close()
            
            return {
                "success": True,
                "indicator": "macd",
                "data": formatted_data,
                "count": len(formatted_data)
            }
        elif indicator.lower() == 'rsi':
            from indicators import calculate_rsi
            result = calculate_rsi(prices)
            
            # Format for charts (simple array)
            cursor.close()
            conn.close()
            
            return {
                "success": True,
                "indicator": "rsi",
                "data": result,
                "count": len(result)
            }
        elif indicator.lower() == 'volatility':
            from indicators import calculate_volatility
            result = calculate_volatility(prices)
            
            # Format for charts
            formatted_data = []
            for i in range(len(times)):
                formatted_data.append({
                    'time': times[i],
                    'volatility': result[i]
                })
            
            cursor.close()
            conn.close()
            
            return {
                "success": True,
                "indicator": "volatility",
                "data": formatted_data,
                "count": len(formatted_data)
            }
        elif indicator.lower() == 'dual_ema':
            from indicators import calculate_dual_ema
            result = calculate_dual_ema(prices)
            
            # Format for charts
            formatted_data = []
            for i in range(len(times)):
                formatted_data.append({
                    'time': times[i],
                    'ema50': result['ema50'][i],
                    'ema200': result['ema200'][i]
                })
            
            cursor.close()
            conn.close()
            
            return {
                "success": True,
                "indicator": "dual_ema",
                "data": formatted_data,
                "count": len(formatted_data)
            }
        else:
            raise HTTPException(status_code=400, detail=f"Unknown indicator: {indicator}")
            
    except Exception as e:
        print(f"Error calculating indicator: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/symbols")
async def get_symbols():
    """Fetch all symbols with current ticker data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Fetch directly from tickers table
        query = """
        SELECT 
            symbol,
            lastPrice as price,
            price24hPcnt * 100 as change_24h,
            turnover24h as volume_24h_usdt
        FROM tickers
        WHERE turnover24h > 0
        ORDER BY turnover24h DESC
        """
        
        cursor.execute(query)
        result = cursor.fetchall()
        
        # Format the result
        symbols = []
        for row in result:
            symbols.append({
                'symbol': row['symbol'],
                'price': float(row['price']),
                'change_24h': float(row['change_24h']),
                'volume_24h_usdt': float(row['volume_24h_usdt'])
            })
        
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

# Root endpoint for index.html
@app.get("/")
async def read_root():
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    print("Starting SmartChart API server...")
    print("Open http://localhost:8000 in your browser")
    uvicorn.run(app, host="0.0.0.0", port=8000)