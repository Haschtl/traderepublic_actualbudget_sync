from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.services.trade_republic import _SAMPLE

settings.app_mode = 'mock'

client = TestClient(app)


def test_health():
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json().get('status') == 'ok'


def test_fetch_and_map_flow():
    # fetch
    r = client.post('/tr/fetch')
    assert r.status_code == 200
    data = r.json()
    assert data['count'] == len(_SAMPLE)

    # map
    r2 = client.post('/tr/map', json=data['transactions'])
    assert r2.status_code == 200
    mapped = r2.json()
    assert isinstance(mapped, list)
    assert len(mapped) == 2


def test_connect_mock():
    r = client.post('/tr/connect')
    assert r.status_code == 200
    j = r.json()
    assert 'status' in j


def test_complete_mock_reuses_session_id():
    start = client.post('/tr/connect')
    assert start.status_code == 200
    sid = start.json().get('session_id')
    assert sid

    done = client.post('/tr/complete', json={'code': '123456', 'session_id': sid})
    assert done.status_code == 200
    payload = done.json()
    assert payload['session_id'] == sid
    assert payload['status'] == 'connected'


def test_complete_requires_code():
    r = client.post('/tr/complete', json={'session_id': 'dummy'})
    assert r.status_code == 400


