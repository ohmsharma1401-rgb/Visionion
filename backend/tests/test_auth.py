import importlib
from fastapi.testclient import TestClient

def test_signup_otp_and_login(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',f'sqlite:///{tmp_path / "auth.db"}')
    monkeypatch.setenv('ALLOW_SQLITE_FOR_TESTS','1')
    monkeypatch.setenv('DATA_DIR',str(tmp_path/'images'))
    monkeypatch.setenv('JWT_SECRET','test-secret-for-verification-only-123456')
    import backend.main as main
    importlib.reload(main)
    sent=[]
    monkeypatch.setattr(main.accounts,'send_code',lambda email,code:sent.append((email,code)))
    with TestClient(main.app) as client:
        signup={'email':'  Farmer@Example.com ','password':'strong-password-2026','name':'Farmer One'}
        assert client.post('/api/auth/register',json=signup).status_code==200
        assert sent[0][0]=='farmer@example.com'
        assert client.post('/api/auth/register',json=signup).status_code==409
        assert client.post('/api/auth/login',json={'email':'farmer@example.com','password':signup['password']}).status_code==403
        assert client.post('/api/auth/verify-otp',json={'email':signup['email'],'code':'000000'}).status_code==400
        assert client.post('/api/auth/verify-otp',json={'email':signup['email'],'code':sent[0][1]}).status_code==200
        assert client.post('/api/auth/verify-otp',json={'email':signup['email'],'code':sent[0][1]}).status_code==400
        token=client.post('/api/auth/login',json={'email':'FARMER@example.com','password':signup['password']}).json()['access_token']
        assert client.get('/api/auth/me',headers={'Authorization':f'Bearer {token}'}).json()['email']=='farmer@example.com'
        assert client.post('/api/auth/login',json={'email':'farmer@example.com','password':'wrong'}).status_code==401

def test_missing_smtp_does_not_create_user(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',f'sqlite:///{tmp_path / "auth.db"}')
    monkeypatch.setenv('ALLOW_SQLITE_FOR_TESTS','1')
    monkeypatch.setenv('DATA_DIR',str(tmp_path/'images'))
    monkeypatch.delenv('SMTP_APP_PASSWORD',raising=False)
    import backend.main as main
    importlib.reload(main)
    with TestClient(main.app) as client:
        response=client.post('/api/auth/register',json={'email':'a@example.com','password':'strong-password-2026','name':'A'})
        assert response.status_code==503
        assert client.post('/api/auth/login',json={'email':'a@example.com','password':'strong-password-2026'}).status_code==401

def test_short_gmail_credential_is_rejected_before_smtp(monkeypatch):
    from backend.auth import send_code
    from fastapi import HTTPException
    monkeypatch.setenv('SMTP_APP_PASSWORD','XXXX-XXXX-XXXX')
    import pytest
    with pytest.raises(HTTPException) as error:
        send_code('recipient@example.com','123456')
    assert error.value.status_code==503
    assert '16 characters' in error.value.detail
