"""Email verification and password authentication for public accounts."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import re
import secrets
import uuid

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.database import User, EmailOtp
from backend.email_delivery import send_code

EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')

class Register(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=200)
    name: str = Field(min_length=1, max_length=120)

class Verify(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    code: str = Field(pattern=r'^\d{6}$')

class Resend(BaseModel):
    email: str = Field(min_length=5, max_length=254)

class Login(BaseModel):
    email: str | None = Field(default=None, max_length=254)
    username: str | None = Field(default=None, max_length=80)
    password: str = Field(min_length=1, max_length=200)

def normalized_email(value: str) -> str:
    value = value.strip().casefold()
    if not EMAIL_RE.fullmatch(value):
        raise HTTPException(422, 'Enter a valid email address.')
    return value

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600_000)
    return f'pbkdf2_sha256$600000${salt.hex()}${key.hex()}'

def valid_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored.split('$')
        if algorithm != 'pbkdf2_sha256': return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False

def hash_code(code: str, user_id: str, secret: str) -> str:
    return hmac.new(secret.encode(), f'{user_id}:{code}'.encode(), hashlib.sha256).hexdigest()

def issue_code(db, user: User, secret: str) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    old = db.get(EmailOtp, user.id)
    if old and (now - old.sent_at).total_seconds() < 60:
        raise HTTPException(429, 'Wait one minute before requesting another code.')
    code = f'{secrets.randbelow(1_000_000):06d}'
    # A failed mail delivery must not create a usable code.
    send_code(user.email, code)
    if old:
        old.code_hash = hash_code(code, user.id, secret)
        old.expires_at = now + timedelta(minutes=10)
        old.sent_at = now
        old.attempts = 0
    else:
        db.add(EmailOtp(user_id=user.id, code_hash=hash_code(code, user.id, secret), expires_at=now + timedelta(minutes=10), sent_at=now, attempts=0))

def register(session, body: Register, secret: str):
    email = normalized_email(body.email)
    if len(body.password.encode()) > 1024: raise HTTPException(422, 'Password is too long.')
    with session() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise HTTPException(409, 'An account already exists for this email. Sign in or request another code.')
        user = User(id=str(uuid.uuid4()), email=email, name=body.name.strip(), password_hash=hash_password(body.password), verified_at=None)
        if not user.name: raise HTTPException(422, 'Enter your name.')
        issue_code(db, user, secret)
        db.add(user)
        try: db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(409, 'An account already exists for this email.') from exc
    return {'message': 'Verification code sent. Check your email.', 'email': email}

def resend(session, body: Resend, secret: str):
    email = normalized_email(body.email)
    with session() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user and not user.verified_at:
            issue_code(db, user, secret)
            db.commit()
    return {'message': 'If this account awaits verification, a new code has been sent.'}

def verify(session, body: Verify, secret: str):
    email = normalized_email(body.email)
    with session() as db:
        user = db.scalar(select(User).where(User.email == email))
        otp = db.get(EmailOtp, user.id) if user else None
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if not user or not otp or user.verified_at or otp.expires_at <= now or otp.attempts >= 5:
            raise HTTPException(400, 'Code is invalid or expired. Request a new code.')
        otp.attempts += 1
        if not hmac.compare_digest(otp.code_hash, hash_code(body.code, user.id, secret)):
            db.commit()
            raise HTTPException(400, 'Code is invalid or expired. Request a new code.')
        user.verified_at = now
        db.delete(otp)
        db.commit()
    return {'message': 'Email verified. You can now sign in.'}
