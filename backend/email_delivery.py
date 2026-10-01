"""Verification email transports. Secrets stay in the backend environment."""
import base64
from email.message import EmailMessage
import logging
import os
import smtplib
import ssl
import threading
import time

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)
UNAVAILABLE = 'Email verification is currently unavailable. Please try again later, or use Try demo to explore the app.'
GMAIL_SCOPE = 'https://www.googleapis.com/auth/gmail.send'
_token_lock = threading.Lock()
_token_cache = {'credentials': None, 'token': None, 'expires_at': 0}


def email_delivery_configured():
    provider = os.getenv('EMAIL_PROVIDER', 'smtp').strip().lower()
    if provider == 'gmail_api':
        return all(os.getenv(key, '').strip() for key in
            ('GMAIL_CLIENT_ID', 'GMAIL_CLIENT_SECRET', 'GMAIL_REFRESH_TOKEN', 'GMAIL_SENDER'))
    if provider == 'smtp':
        return bool(os.getenv('SMTP_APP_PASSWORD')) and not bool(os.getenv('RENDER'))
    return False


def _gmail_access_token(client):
    credentials = tuple(os.getenv(key, '').strip() for key in
        ('GMAIL_CLIENT_ID', 'GMAIL_CLIENT_SECRET', 'GMAIL_REFRESH_TOKEN'))
    with _token_lock:
        if _token_cache['credentials'] == credentials and _token_cache['expires_at'] > time.monotonic():
            return _token_cache['token']
        response = client.post('https://oauth2.googleapis.com/token', data={
            'client_id': credentials[0], 'client_secret': credentials[1],
            'refresh_token': credentials[2], 'grant_type': 'refresh_token'})
        if not response.is_success:
            logger.warning('Gmail OAuth refresh failed with HTTP %s; check sender authorization.', response.status_code)
            raise HTTPException(503, UNAVAILABLE)
        try:
            payload = response.json()
            token = payload['access_token']
            expires = int(payload.get('expires_in', 3600))
            if not isinstance(token, str) or not token or expires <= 0:
                raise ValueError('Invalid token response')
            if payload.get('scope') and GMAIL_SCOPE not in payload['scope'].split():
                raise ValueError('Missing Gmail send scope')
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            logger.warning('Gmail token response was invalid or did not authorize sending.')
            raise HTTPException(503, UNAVAILABLE) from exc
        _token_cache.update(credentials=credentials, token=token,
                            expires_at=time.monotonic()+max(0, expires-60))
        return token


def send_code(email, code):
    provider = os.getenv('EMAIL_PROVIDER', 'smtp').strip().lower()
    if not email_delivery_configured():
        logger.warning('Verification email transport %s is not configured or unavailable on this host.', provider)
        raise HTTPException(503, UNAVAILABLE)
    message = EmailMessage()
    sender = os.getenv('GMAIL_SENDER', '').strip() if provider == 'gmail_api' else os.getenv('SMTP_FROM', os.getenv('SMTP_USERNAME', 'amrishs256@gmail.com'))
    message['From'] = sender
    message['To'] = email
    message['Subject'] = 'Your Visionion verification code'
    message.set_content(f'Your Visionion verification code is {code}. It expires in 10 minutes. If you did not request an account, ignore this message.')
    if provider == 'gmail_api':
        try:
            with httpx.Client(timeout=12) as client:
                token = _gmail_access_token(client)
                response = client.post('https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
                    headers={'Authorization': 'Bearer '+token},
                    json={'raw': base64.urlsafe_b64encode(message.as_bytes()).decode('ascii')})
                if not response.is_success:
                    if response.status_code == 401:
                        with _token_lock:
                            _token_cache['expires_at'] = 0
                    logger.warning('Gmail send failed with HTTP %s.', response.status_code)
                    raise HTTPException(503, UNAVAILABLE)
        except httpx.HTTPError as exc:
            logger.warning('Gmail HTTPS transport failed.')
            raise HTTPException(503, UNAVAILABLE) from exc
        return
    password = os.getenv('SMTP_APP_PASSWORD', '').replace(' ', '')
    host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    if host == 'smtp.gmail.com' and len(password) != 16:
        raise HTTPException(503, 'The configured Gmail app password is not 16 characters. Create a new app password for the sender account.')
    try:
        with smtplib.SMTP(host, int(os.getenv('SMTP_PORT', '587')), timeout=12) as client:
            client.starttls(context=ssl.create_default_context())
            client.login(os.getenv('SMTP_USERNAME', 'amrishs256@gmail.com'), password)
            client.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        logger.warning('SMTP verification transport failed.')
        raise HTTPException(503, UNAVAILABLE) from exc
