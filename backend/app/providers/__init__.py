"""Provider registry. To add a provider: implement providers.base.Provider and register it here."""
from __future__ import annotations

from .base import Provider
from .alphavantage import AlphaVantageProvider
from .fred import FredProvider
from .sec_edgar import SecEdgarProvider
from .sec_filing_xbrl import SecFilingXbrlProvider
from .twse import TwseProvider

PROVIDERS: dict[str, type[Provider]] = {
    SecEdgarProvider.name: SecEdgarProvider,
    FredProvider.name: FredProvider,
    SecFilingXbrlProvider.name: SecFilingXbrlProvider,
    TwseProvider.name: TwseProvider,
    AlphaVantageProvider.name: AlphaVantageProvider,
}


def get_provider(name: str) -> Provider:
    if name not in PROVIDERS:
        raise KeyError(f"unknown provider {name!r}; known: {sorted(PROVIDERS)}")
    return PROVIDERS[name]()
