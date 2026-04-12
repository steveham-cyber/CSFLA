"""
Pseudonymisation key retrieval.

Development (APP_ENV=development): reads TEST_PSEUDONYMISATION_KEY from the
environment. Set by the developer locally or by CI via GitHub Secrets.

Production (Azure): fetches the secret from Azure Key Vault using the
pipeline's Managed Identity. Single authenticated fetch per batch — the key
is held in memory for the batch duration and zeroed afterward.

See Data Architecture Spec v0.3 Section 5.3.
"""

import os

from config import get_settings


async def get_pseudonymisation_key() -> str:
    """
    Retrieve the HMAC pseudonymisation key for the current environment.

    Raises:
        PipelineHalt: If the key cannot be retrieved (missing env var in dev,
                      Key Vault unavailable in production).
    """
    from pipeline import PipelineHalt  # deferred to avoid circular at import time

    settings = get_settings()

    if settings.is_local:
        key = os.environ.get("TEST_PSEUDONYMISATION_KEY")
        if not key:
            raise PipelineHalt(
                "TEST_PSEUDONYMISATION_KEY is not set — "
                "cannot run the import pipeline in development mode."
            )
        return key

    # Production: Azure Key Vault via Managed Identity
    try:
        from azure.identity.aio import DefaultAzureCredential
        from azure.keyvault.secrets.aio import SecretClient

        async with DefaultAzureCredential() as credential:
            async with SecretClient(
                vault_url=settings.azure_key_vault_url, credential=credential
            ) as client:
                secret = await client.get_secret(settings.azure_key_vault_key_name)
                return secret.value
    except Exception as exc:
        raise PipelineHalt(
            f"Failed to retrieve pseudonymisation key from Key Vault: {exc}"
        ) from exc
