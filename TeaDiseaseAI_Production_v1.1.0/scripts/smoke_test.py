from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as client:
    r = client.get('/api/health')
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['status'] == 'ok'
    print('HEALTH CHECK: PASSED')
    print(body)
