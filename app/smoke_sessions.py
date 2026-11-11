"""Build-time sign-in persistence and sign-out regression smoke."""
import os
from fastapi.testclient import TestClient

os.environ["APP_PASSWORD"]="smoke-password-not-a-production-secret"
from .main import app,sessions
from .signed_session import valid

def main():
    with TestClient(app) as client:
        login=client.post("/api/login",json={"password":os.environ["APP_PASSWORD"]},
                          headers={"X-Kraken-Request":"1"})
        assert login.status_code==200,login.text
        cookie=client.cookies.get("kraken_session")
        assert cookie and valid(cookie,os.environ["APP_PASSWORD"])
        sessions.clear()
        assert client.get("/api/me").status_code==200
        assert client.post("/api/logout",headers={"X-Kraken-Request":"1"}).status_code==200
        assert client.get("/api/me").status_code==401
        print("KRAKEN RESTART-SAFE 14-DAY LOGIN SMOKE OK",flush=True)

if __name__=="__main__":main()
