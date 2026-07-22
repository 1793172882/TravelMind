"""Local register, login and current-user endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUserDependency, DatabaseSession
from app.api.schemas.auth import CredentialsRequest, CurrentUserResponse, TokenResponse
from app.services.auth import AuthService, AuthenticationError

router = APIRouter(prefix="/auth", tags=["auth"])


def _authenticate(action: str, request: CredentialsRequest, session: DatabaseSession) -> TokenResponse:
    service = AuthService(session)
    try:
        user, token = getattr(service, action)(request.username, request.password)
    except AuthenticationError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    return TokenResponse(
        access_token=token,
        user_id=f"web:{user.id}",
        username=user.username,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(request: CredentialsRequest, session: DatabaseSession) -> TokenResponse:
    return _authenticate("register", request, session)


@router.post("/login", response_model=TokenResponse)
def login(request: CredentialsRequest, session: DatabaseSession) -> TokenResponse:
    return _authenticate("login", request, session)


@router.get("/me", response_model=CurrentUserResponse)
def current_user(user: CurrentUserDependency) -> CurrentUserResponse:
    return CurrentUserResponse(
        user_id=user.user_id,
        username=user.username,
        authenticated=user.id is not None,
    )
