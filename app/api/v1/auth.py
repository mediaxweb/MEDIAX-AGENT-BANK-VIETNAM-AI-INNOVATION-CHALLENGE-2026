from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.schemas.auth import AuthTokenResponse, LoginRequest, RegisterRequest, UserResponse
from app.core.dependencies import get_auth_service, get_current_user
from app.services.auth_service import (
    AuthService,
    DEMO_ACCOUNTS,
    DemoAccountNotFoundError,
    EmailAlreadyExistsError,
    InactiveUserError,
    InvalidCredentialsError,
)


router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Register a new user account."""

    try:
        return await auth_service.register(payload)
    except EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    """Authenticate a user and return a Bearer access token."""

    try:
        return await auth_service.login(payload)
    except (InvalidCredentialsError, InactiveUserError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post("/demo-login/{account_number}", response_model=AuthTokenResponse)
async def demo_login(
    account_number: int = Path(..., ge=1, le=len(DEMO_ACCOUNTS)),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    """Authenticate as one of the public demo accounts."""

    try:
        return await auth_service.login_demo_account(account_number)
    except (DemoAccountNotFoundError, InactiveUserError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/me", response_model=UserResponse)
async def me(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """Return the currently authenticated user."""

    return current_user
