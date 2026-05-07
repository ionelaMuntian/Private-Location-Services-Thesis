# client_app/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Client App - Trusted Side"

    # gRPC settings for client_app -> service_provider_app communication
    service_provider_grpc_host: str = "service_provider_app"
    service_provider_grpc_port: int = 50051

    # Optional: keep this only if you still want HTTP fallback/debugging
    service_provider_base_url: str = "http://127.0.0.1:8001"

    # CKKS / TenSEAL settings
    ckks_poly_modulus_degree: int = 8192
    ckks_coeff_mod_bit_sizes: str = "60,40,40,60"
    ckks_global_scale_bits: int = 40

    # BFV / TenSEAL settings
    bfv_poly_modulus_degree: int = 8192
    bfv_plain_modulus: int = 1032193
    bfv_scale: int = 100

    # Auth DB settings
    auth_db_host: str = "127.0.0.1"
    auth_db_port: int = 5432
    auth_db_name: str = "auth_db"
    auth_db_user: str = "postgres"
    auth_db_password: str
    auth_db_schema: str = "auth"

    # JWT settings
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def ckks_coeff_mod_bit_sizes_list(self) -> list[int]:
        return [int(x.strip()) for x in self.ckks_coeff_mod_bit_sizes.split(",") if x.strip()]

    @property
    def auth_dsn(self) -> str:
        return (
            f"host={self.auth_db_host} "
            f"port={self.auth_db_port} "
            f"dbname={self.auth_db_name} "
            f"user={self.auth_db_user} "
            f"password={self.auth_db_password}"
        )


settings = Settings()