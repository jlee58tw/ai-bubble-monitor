"""Provider registry. To add a provider: implement providers.base.Provider and register it here."""
from __future__ import annotations

from .base import Provider
from .fred import FredProvider
from .sec_edgar import SecEdgarProvider

PROVIDERS: dict[str, type[Provider]] = {
    SecEdgarProvider.name: SecEdgarProvider,
    FredProvider.name: FredProvider,
}


def get_provider(name: str) -> Provider:
    if name not in PROVIDERS:
        raise KeyError(f"unknown provider {name!r}; known: {sorted(PROVIDERS)}")
    return PROVIDERS[name]()
