from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer 
from app.core.config import settings
from app.core.database import db


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _truncate_to_72_bytes(password: str) -> bytes:
    b = password.encode("utf-8")
    if len(b) <= 72:
        return b
    return b[:72]

def create_access_token(data: dict, expires_delta: int | None = None):
    to_encode = data.copy()
    minutes = expires_delta if expires_delta is not None else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.utcnow() + timedelta(minutes=minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_value, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Ensure backend never gets >72 bytes
    plain_bytes = _truncate_to_72_bytes(plain_password)
    return pwd_context.verify(plain_bytes, hashed_password)

def get_password_hash(password: str) -> str:
    # Truncate at byte level to 72 bytes to satisfy bcrypt
    plain_bytes = _truncate_to_72_bytes(password)
    return pwd_context.hash(plain_bytes)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_value, algorithms=[settings.JWT_ALGORITHM])
        subject = payload.get("sub")
        if subject is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # subject can be email or username; try email first
    with db.get_session() as session:
        record = session.run("MATCH (u:User {email: $sub}) RETURN u", sub=subject).single()
        if not record:
            # fallback by username
            record = session.run("MATCH (u:User {username: $sub}) RETURN u", sub=subject).single()
        if not record:
            raise credentials_exception
        u = dict(record["u"])
        u.pop("password", None)
        return u