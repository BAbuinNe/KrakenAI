"""Regression tests: signed sessions survive Python worker state loss."""
import os
import hashlib
from fastapi.testclient import TestClient
from app.main import app, sessions, revoked_sessions
from app import signed_session

HEAD={"X-Kraken-Request":"1"}
PASSWORD="test_password_at_least_16_characters"


def test_signed_cookie_valid_for_two_weeks_and_rejects_tampering():
    token=signed_session.create(PASSWORD,now=1000000)
    assert signed_session.valid(token,PASSWORD,now=1000001)
    assert signed_session.valid(token,PASSWORD,now=1000000+signed_session.SESSION_AGE-1)
    assert not signed_session.valid(token,PASSWORD,now=1000000+signed_session.SESSION_AGE)
    assert not signed_session.valid(token,"changed_password_at_least_16_chars",now=1000001)
    changed=token[:-1]+("0" if token[-1]!="0" else "1")
    assert not signed_session.valid(changed,PASSWORD,now=1000001)
    assert not signed_session.valid("v1.999999999999999999999999999.nonce."+("0"*64),PASSWORD)


def test_logged_in_user_stays_authenticated_after_session_store_clear(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD",PASSWORD)
    with TestClient(app) as client:
        response=client.post("/api/login",json={"password":PASSWORD},headers=HEAD)
        assert response.status_code==200,response.text
        assert "Max-Age=1209600" in response.headers["set-cookie"]
        cookie=client.cookies.get("kraken_session")
        assert cookie and cookie.startswith("v1.")
        sessions.clear()
        assert client.get("/api/me",headers=HEAD).status_code==200
        # Simulate worker process reinitialization: signed cookie still verifies.
        revoked_sessions.clear()
        assert client.get("/api/me",headers=HEAD).status_code==200
        assert client.post("/api/logout",headers=HEAD).status_code==200
        assert client.get("/api/me",headers=HEAD).status_code==401


def test_logged_out_session_cannot_be_reused_in_live_process(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD",PASSWORD)
    with TestClient(app) as client:
        assert client.post("/api/login",json={"password":PASSWORD},headers=HEAD).status_code==200
        token=client.cookies["kraken_session"]
        assert client.post("/api/logout",headers=HEAD).status_code==200
        client.cookies.set("kraken_session",token)
        assert client.get("/api/me",headers=HEAD).status_code==401
