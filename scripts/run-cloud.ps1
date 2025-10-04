param(
  [int]$Port = 8000
)
$env:PYTHONUNBUFFERED = "1"
python -m uvicorn cloud.main:app --host 0.0.0.0 --port $Port --reload
