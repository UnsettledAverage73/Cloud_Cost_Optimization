import os

import pytest
from fastapi.testclient import TestClient

from main import app


client = TestClient(app)

AWS_PAYLOAD = {
    "provider": "AWS",
    "account_name": "Learner Lab Sandbox",
    "auth_method": "learner_lab",
    "access_key": os.getenv("AWS_ACCESS_KEY_ID"),
    "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
    "session_token": os.getenv("AWS_SESSION_TOKEN"),
    "region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
}

pytestmark = pytest.mark.skipif(
    not all((AWS_PAYLOAD["access_key"], AWS_PAYLOAD["secret_key"], AWS_PAYLOAD["session_token"])),
    reason="AWS integration credentials are not configured",
)


class TestLiveCloudPulseBackend:
    @pytest.fixture(autouse=True, scope="module")
    def authenticate_aws(self):
        response = client.post("/api/v1/connect-cloud", json=AWS_PAYLOAD)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_connect_aws_missing_token(self):
        invalid_payload = AWS_PAYLOAD.copy()
        invalid_payload["session_token"] = ""
        response = client.post("/api/v1/connect-cloud", json=invalid_payload)
        assert response.status_code == 400

    def test_get_live_nodes_list(self):
        response = client.get("/api/v1/resources/nodes")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_live_security_audit(self):
        response = client.get("/api/v1/security/audit")
        assert response.status_code == 200
        assert "exposed_security_groups" in response.json()
