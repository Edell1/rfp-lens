from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.dependencies import CurrentUser, DatabaseSession
from app.auth.schemas import RegisterRequest, TokenResponse, UserResponse
from app.auth.service import authenticate_user, create_access_token, register_user
from app.core.config import Settings, get_settings


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register(payload: RegisterRequest, db: DatabaseSession) -> UserResponse:
    return UserResponse.model_validate(
        register_user(db, email=payload.email, password=payload.password)
    )


@router.post("/token", response_model=TokenResponse)
def token(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DatabaseSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    user = authenticate_user(db, email=form.username, password=form.password)
    return TokenResponse(access_token=create_access_token(user.id, settings))


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
