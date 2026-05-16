# client_app/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Client App - Trusted Side"

    service_provider_grpc_host: str = "service_provider_app"
    service_provider_grpc_port: int = 50051
    service_provider_base_url: str = "http://127.0.0.1:8001"

    # CKKS / TenSEAL settings
    ckks_poly_modulus_degree: int = 8192
    ckks_coeff_mod_bit_sizes: str = "60,40,40,60"
    ckks_global_scale_bits: int = 40

    # BFV / TenSEAL settings
    bfv_poly_modulus_degree: int = 8192
    bfv_plain_modulus: int = 1032193
    bfv_scale: int = 100

    # Auth DB — credentials only
    auth_db_host: str = "127.0.0.1"
    auth_db_port: int = 5432
    auth_db_name: str = "auth_db"
    auth_db_user: str = "postgres"
    auth_db_password: str
    auth_db_schema: str = "auth"

    # Users DB — home locations, location inputs, location status
    users_db_host: str = "127.0.0.1"
    users_db_port: int = 5434
    users_db_name: str = "users_data"
    users_db_user: str = "postgres"
    users_db_password: str

    # Company DB — companies, company_users, compliance_jobs
    company_db_host: str = "127.0.0.1"
    company_db_port: int = 5435
    company_db_name: str = "company_data"
    company_db_user: str = "postgres"
    company_db_password: str

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

    @property
    def users_dsn(self) -> str:
        return (
            f"host={self.users_db_host} "
            f"port={self.users_db_port} "
            f"dbname={self.users_db_name} "
            f"user={self.users_db_user} "
            f"password={self.users_db_password}"
        )

    @property
    def company_dsn(self) -> str:
        return (
            f"host={self.company_db_host} "
            f"port={self.company_db_port} "
            f"dbname={self.company_db_name} "
            f"user={self.company_db_user} "
            f"password={self.company_db_password}"
        )


settings = Settings()
