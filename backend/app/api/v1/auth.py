from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from starlette.concurrency import run_in_threadpool

from app.core.security import create_access_token, verify_password
from app.models.models import User
from app.schemas.auth import JWTPayload, TokenResponse

router = APIRouter(prefix="/api/v1", tags=["Auth"])

@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await User.find_one(
        User.email == form_data.username,
        fetch_links=True,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    password_valid = await run_in_threadpool(
        verify_password,
        form_data.password,
        user.pwd_hash,
    )
    if not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jwt_claims = JWTPayload(
        sub=str(user.id),
        org_id=str(user.org_id),
        role=str(user.roles.id),
        permissions=list(user.roles.permissions),
    )
    token = create_access_token(jwt_claims)
    return TokenResponse(access_token=token)