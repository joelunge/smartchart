# SmartChart

Simple example project that serves candlestick data from a MySQL database and
renders it in the browser using lightweight-charts.

## Backend

```bash
cd backend
pip install -r requirements.txt
python app.py
```

## Frontend

```bash
cd frontend
python -m http.server 8000
# or open index.html directly in the browser
```

## Starta
1. backend `$ python app.py`
2. frontend `$ python -m http.server 8000`
Öppna http://localhost:8000  → grafen visas.

### Ladda ner biblioteket
Kör i projektroten (ersätter stubben med den riktiga UMD-builden):
```bash
cd frontend
rm -f lightweight-charts.js
curl -L --fail -o lightweight-charts.js \
  https://cdn.jsdelivr.net/npm/lightweight-charts@5.0.7/dist/lightweight-charts.umd.js
```
