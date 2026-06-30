from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Service Provider App - Untrusted Side"

    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str = "osm_ro"
    db_user: str = "postgres"
    db_password: str
    db_schema: str = "thesis"
    db_table: str = "poi"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def dsn(self) -> str:
        return (
            f"host={self.db_host} "
            f"port={self.db_port} "
            f"dbname={self.db_name} "
            f"user={self.db_user} "
            f"password={self.db_password}"
        )


settings = Settings()