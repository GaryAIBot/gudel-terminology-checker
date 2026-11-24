from fastapi.testclient import TestClient
from api.index import app
c=TestClient(app)

def test_check_api_offsets():
    r=c.post('/api/v1/check/text',json={"text":"Install the side guide.","language":"en-US"})
    assert r.status_code==200
    data=r.json(); assert data["findings_count"]==1
    assert data["findings"][0]["start_offset"]==12
    assert data["findings"][0]["end_offset"]==22

def test_search():
    r=c.get('/api/v1/terms/search',params={"q":"locking bolt"})
    assert r.json()["results"][0]["status"]=="forbidden"

