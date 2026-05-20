from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from api.limiter import limiter
from api.models import User
from api.security import (
    create_access_token,
    create_refresh_token,
    generate_csrf_token,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_COOKIE_OPTS = {"httponly": True, "samesite": "strict", "secure": False}  # set secure=True in prod


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    role: str


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.email == body.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))
    csrf = generate_csrf_token()

    response.set_cookie("access_token", access, max_age=8 * 3600, **_COOKIE_OPTS)
    response.set_cookie("refresh_token", refresh, max_age=7 * 86400, **_COOKIE_OPTS)
    # CSRF token goes in a readable cookie so JS can send it as a header
    response.set_cookie("csrf_token", csrf, max_age=8 * 3600, httponly=False, samesite="strict")

    return {"user": UserOut(id=str(user.id), email=user.email, role=user.role), "csrf_token": csrf}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    response.delete_cookie("csrf_token")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut(id=str(user.id), email=user.email, role=user.role)
