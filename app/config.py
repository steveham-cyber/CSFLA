from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Azure Entra ID
    azure_tenant_id: str
    azure_client_id: str
    azure_client_secret: str = ""  # Empty in Azure — Managed Identity used instead

    # Azure Key Vault
    azure_key_vault_url: str
    azure_key_vault_key_name: str = "pseudonymisation-key"

    # Database
    db_host: str
    db_port: int = 5432
    db_name: str
    db_user: str
    db_password: str = ""  # Empty in Azure — Managed Identity token auth used

    # Application
    app_env: str = "production"
    secret_key: str
    allowed_origins: str = ""

    # Local dev only — pseudonymisation key (production uses Azure Key Vault)
    test_pseudonymisation_key: str = ""

    # Anthropic — intentionally absent until DPA is in place
    # anthropic_api_key: str = ""

    @property
    def is_local(self) -> bool:
        return self.app_env == "development"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
