from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)
project = client.post("/api/projects", json={"name": "样例项目", "code": "TEST-2026-001"}).json()
with open("samples/脱敏招标文件样例.txt", "rb") as handle:
    response = client.post(
        f"/api/projects/{project['id']}/documents",
        files={"file": ("sample.txt", handle, "text/plain")},
    )
print(response.status_code, response.json())
body = client.get(f"/api/projects/{project['id']}").json()
print("requirements", len(body["requirements"]))
print(body["requirements"][0]["category"], body["requirements"][0]["source_location"])
