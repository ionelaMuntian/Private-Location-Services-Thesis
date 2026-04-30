from fastapi import Depends, HTTPException, status

from .repository import AuthRepository
from .security import get_current_token_payload


repository = AuthRepository()


def get_current_user(payload: dict = Depends(get_current_token_payload)) -> dict:
    subject = payload.get("sub")
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
        )

    try:
        user_id = int(subject)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject.",
        ) from exc

    user = repository.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found for token.",
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    return {
        "id": int(user["id"]),
        "username": user["username"],
        "email": user["email"],
        "is_active": bool(user["is_active"]),
    }