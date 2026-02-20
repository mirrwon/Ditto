from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.api.security import SECRET_KEY, ALGORITHM, TOKEN_COOKIE_NAME

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)


def get_current_user(request: Request, token: str | None = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    raw_token = request.cookies.get(TOKEN_COOKIE_NAME) or token
    if not raw_token:
        raise credentials_exception
    try:
        payload = jwt.decode(raw_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        # In a real DB scenario, we might fetch the full user object here.
        # For now, we trust the token's username claim.
        user_data = {"user_name": username}
        return user_data
    except JWTError:
        raise credentials_exception
