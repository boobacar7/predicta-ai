class ProviderError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class LiveIngestionDisabled(ProviderError):
    def __init__(self, provider: str) -> None:
        super().__init__(
            "live_disabled",
            f"Provider '{provider}' is not connected. Live ingestion is disabled until a human validates the contract.",
        )


class ProviderNotConfigured(ProviderError):
    def __init__(self, provider: str) -> None:
        super().__init__(
            "not_configured",
            f"Provider '{provider}' has no API key in the environment. Keys must never be committed to Git.",
        )


class ProviderUnavailable(ProviderError):
    def __init__(self, provider: str, detail: str) -> None:
        super().__init__("unavailable", f"{provider}: {detail}")


class ProviderRateLimited(ProviderError):
    def __init__(self, provider: str) -> None:
        super().__init__("rate_limited", f"{provider} returned a rate limit.")


class ProviderAuthError(ProviderError):
    def __init__(self, provider: str) -> None:
        super().__init__("auth", f"{provider} rejected authentication. The secret is not logged.")
