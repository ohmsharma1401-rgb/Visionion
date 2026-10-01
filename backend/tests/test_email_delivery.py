import base64
from email import message_from_bytes
import httpx
import pytest
from fastapi import HTTPException
from backend import email_delivery as delivery


@pytest.fixture
def configured(monkeypatch):
    for key, value in {'EMAIL_PROVIDER':'gmail_api','GMAIL_CLIENT_ID':'test-client',
        'GMAIL_CLIENT_SECRET':'test-secret','GMAIL_REFRESH_TOKEN':'test-refresh',
        'GMAIL_SENDER':'sender@example.com'}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setitem(delivery._token_cache, 'expires_at', 0)


def test_gmail_refresh_mime_delivery_and_cached_token(configured, monkeypatch):
    calls=[]
    def handler(request):
        calls.append(request)
        if request.url.host == 'oauth2.googleapis.com':
            assert b'grant_type=refresh_token' in request.content
            return httpx.Response(200,json={'access_token':'test-access','expires_in':3600,'scope':delivery.GMAIL_SCOPE})
        assert request.headers['Authorization'] == 'Bearer test-access'
        import json
        message=message_from_bytes(base64.urlsafe_b64decode(json.loads(request.content)['raw']))
        assert message['From']=='sender@example.com' and message['To']=='recipient@example.com'
        assert '123456' in message.get_payload(decode=True).decode()
        return httpx.Response(200,json={'id':'test-message'})
    original_client=httpx.Client
    monkeypatch.setattr(delivery.httpx,'Client',lambda **kwargs:original_client(transport=httpx.MockTransport(handler),**kwargs))
    delivery.send_code('recipient@example.com','123456')
    delivery.send_code('recipient@example.com','123456')
    assert sum(r.url.host=='oauth2.googleapis.com' for r in calls)==1
    assert len(calls)==3


def test_failed_refresh_never_sends_or_leaks_secrets(configured, monkeypatch):
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(400,json={'error':'invalid_grant','secret':'test-secret'})
    original_client=httpx.Client
    monkeypatch.setattr(delivery.httpx,'Client',lambda **kwargs:original_client(transport=httpx.MockTransport(handler),**kwargs))
    with pytest.raises(HTTPException) as error:
        delivery.send_code('recipient@example.com','123456')
    assert error.value.status_code==503 and 'test-secret' not in error.value.detail
    assert len(calls)==1


def test_missing_gmail_credentials_does_not_fall_back_to_smtp(configured, monkeypatch):
    monkeypatch.delenv('GMAIL_REFRESH_TOKEN')
    monkeypatch.setenv('SMTP_APP_PASSWORD','test-password-16')
    assert delivery.email_delivery_configured() is False
    with pytest.raises(HTTPException):delivery.send_code('recipient@example.com','123456')


def test_render_smtp_configuration_does_not_claim_delivery(monkeypatch):
    monkeypatch.setenv('EMAIL_PROVIDER','smtp')
    monkeypatch.setenv('RENDER','true')
    monkeypatch.setenv('SMTP_APP_PASSWORD','test-password-16')
    assert delivery.email_delivery_configured() is False
