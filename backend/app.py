"""Flask application serving candlestick data."""

from datetime import timezone
from typing import List, Dict

from flask import Flask, jsonify, request, abort
from flask_cors import CORS

from db import get_connection

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:*"}})

TABLE_MAP = {
    "1m": "candles1",
    "5m": "candles5",
    "15m": "candles15",
    "1h": "candles60",
    "4h": "candles240",
}


@app.get("/api/candles")
def get_candles() -> List[Dict]:
    """Return candlestick data as JSON."""
    symbol = request.args.get("symbol", "BTCUSDT")
    tf = request.args.get("tf", "1m")
    limit = request.args.get("limit", 500, type=int)

    if tf not in TABLE_MAP:
        abort(400, description="Invalid timeframe")

    table = TABLE_MAP[tf]

    query = (
        "SELECT startTime AS t, openPrice AS o, highPrice AS h, "
        "lowPrice AS l, closePrice AS c, volume AS v "
        f"FROM {table} "
        "WHERE symbol = %s "
        "ORDER BY startTime DESC "
        "LIMIT %s"
    )

    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (symbol, limit))
        rows = cursor.fetchall()
    finally:
        connection.close()

    # Convert timestamps and sort ascending
    data = []
    for row in reversed(rows):
        timestamp = int(row["t"].replace(tzinfo=timezone.utc).timestamp())
        data.append({
            "time": timestamp,
            "open": float(row["o"]),
            "high": float(row["h"]),
            "low": float(row["l"]),
            "close": float(row["c"]),
            "volume": float(row["v"]),
        })

    return jsonify(data)


if __name__ == "__main__":
    app.run(port=5000)
