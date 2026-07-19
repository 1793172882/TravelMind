from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "TravelMind"}

def test_version() -> None:
    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() ==  {'name': 'TravelMind', 'version': '0.1.0'}
def test_trip_preview():
    # json 参数自动序列化为请求体
    payload = {
     "origin": "北京",
      "destination": "上海"    
      }
    response = client.post("/trips/preview", json=payload)
    # 断言
    assert response.status_code == 200

def test_trip_preview_rejects_empty_origin() -> None:
    payload = {
        "origin": "",
        "destination": "上海",
    }

    response = client.post("/trips/preview", json=payload)

    assert response.status_code == 422
    
def test_get_trip_uses_default_detail() -> None:
    response = client.get("/trips/1001")

    assert response.status_code == 200
    assert response.json() == {
        "trip_id": 1001,
        "detail": False,
        "language":"zh"
    }
