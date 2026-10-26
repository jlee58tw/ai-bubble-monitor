"""GPU cloud prices.

CONNECTED: Microsoft Azure Retail Prices API (official, unauthenticated, documented for programmatic use:
https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices).
These are LIST prices (pay-as-you-go and Spot) for whole VMs, Linux, one region - not negotiated / reserved /
marketplace rental prices. Per-GPU-hour = instance price / GPU count (from the documented SKU spec).

PLACEHOLDER: GPU *marketplace rental* indices (e.g. H100 $/hr on neoclouds/marketplaces) - no source whose
terms clearly allow automated collection was found; shown as unavailable, never estimated.
"""
from __future__ import annotations

import datetime as dt

import httpx

from ..providers.base import RateLimiter, get_with_retry

AZ_API = "https://prices.azure.com/api/retail/prices"
AZ_PUBLIC = "https://azure.microsoft.com/pricing/details/virtual-machines/linux/"
REGION = "eastus"
# SKU -> (GPU model, GPU count)  per Microsoft VM size docs
SKUS = {
    "Standard_ND96isr_H100_v5": ("H100 80GB SXM", 8),
    "Standard_NC40ads_H100_v5": ("H100 NVL 94GB", 1),
    "Standard_ND96amsr_A100_v4": ("A100 80GB SXM", 8),
    "Standard_NC24ads_A100_v4": ("A100 80GB PCIe", 1),
    "Standard_ND96isr_H200_v5": ("H200 141GB", 8),
    "Standard_ND96isr_MI300X_v5": ("MI300X 192GB", 8),
}
PLACEHOLDERS = [{
    "id": "gpu_marketplace_rental", "name": "GPU marketplace rental price (H100/H200 $/GPU-hr)",
    "status": "placeholder",
    "limitation": "No marketplace/neocloud price source with terms that clearly permit automated collection "
                  "was identified. Hyperscaler list prices (Azure) are shown instead; they are sticky list prices "
                  "and do not reflect negotiated, reserved or secondary-market rental rates.",
}]


def az_filter(region: str = REGION) -> str:
    skus = " or ".join(f"armSkuName eq '{s}'" for s in SKUS)
    return f"serviceName eq 'Virtual Machines' and armRegionName eq '{region}' and priceType eq 'Consumption' and ({skus})"


def parse_azure(items: list[dict]) -> list[dict]:
    out = []
    for i in items:
        sku = i.get("armSkuName")
        if sku not in SKUS or i.get("unitOfMeasure") != "1 Hour":
            continue
        prod, skuname = i.get("productName", ""), i.get("skuName", "")
        if "Windows" in prod or prod.rstrip().endswith(" Win") or "Low Priority" in skuname:
            continue
        kind = "list_spot" if "Spot" in skuname else "list_on_demand"
        gpu, n = SKUS[sku]
        price = float(i["retailPrice"])
        if price <= 0:
            continue
        eff = i.get("effectiveStartDate")
        out.append(dict(source="azure_retail", price_kind=kind, sku=sku, gpu_model=gpu, gpu_count=n,
                        region=i.get("armRegionName"), usd_per_hour=price, usd_per_gpu_hour=round(price / n, 6),
                        effective_from=dt.date.fromisoformat(eff[:10]) if eff else None,
                        source_url=AZ_PUBLIC))
    return out


def fetch_azure(client: httpx.Client) -> list[dict]:
    lim = RateLimiter(1.0)
    items, url, params = [], AZ_API, {"$filter": az_filter()}
    for _ in range(20):  # pagination guard
        doc = get_with_retry(client, str(httpx.URL(url, params=params) if params else url), lim).json()
        items.extend(doc.get("Items", []))
        url, params = doc.get("NextPageLink"), None
        if not url:
            break
    return parse_azure(items)


SOURCES = {"gpu_azure_retail": fetch_azure}
