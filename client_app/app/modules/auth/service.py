# client_app/app/modules/auth/service.py
from fastapi import HTTPException, status

from .repository import AuthRepository
from .security import create_access_token, hash_password, verify_password


class AuthService:
    def __init__(self) -> None:
        self.repository = AuthRepository()

    def initialize_auth_storage(self) -> None:
        self.repository.create_schema_and_table_if_not_exists()

    def register_user(self, username: str, email: str, password: str) -> dict:
        existing_username = self.repository.get_user_by_username(username)
        if existing_username is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists.",
            )

        existing_email = self.repository.get_user_by_email(email)
        if existing_email is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists.",
            )

        password_hash = hash_password(password)
        return self.repository.create_user(
            username=username,
            email=email,
            password_hash=password_hash,
        )

    def login_user(self, username: str, password: str) -> dict:
        user = self.repository.get_user_by_username(username)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password.",
            )

        if not user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive.",
            )

        if not verify_password(password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password.",
            )

        access_token = create_access_token(
            user_id=int(user["id"]),
            username=user["username"],
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
        }

    def get_user_profile(self, user_id: int) -> dict:
        user = self.repository.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        return {
            "id": int(user["id"]),
            "username": user["username"],
            "email": user["email"],
            "is_active": bool(user["is_active"]),
        }