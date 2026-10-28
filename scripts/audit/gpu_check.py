"""Family (6): Azure GPU VM list prices vs the Azure Retail Prices API queried fresh, one armSkuName at a time."""
import json, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(__file__))
from common import db, fetch, Results, close

R = Results("azure_gpu")
con = db()
rows = con.execute("select price_kind, sku, region, gpu_count, usd_per_hour, usd_per_gpu_hour, effective_from, last_seen_at "
                   "from gpu_prices where id not in (select supersedes_id from gpu_prices where supersedes_id is not null)").fetchall()
for sku in sorted({r[1] for r in rows}):
    f = (f"serviceName eq 'Virtual Machines' and armRegionName eq 'eastus' and armSkuName eq '{sku}' "
         f"and priceType eq 'Consumption'")
    url = "https://prices.azure.com/api/retail/prices?api-version=2023-01-01-preview&$filter=" + urllib.parse.quote(f)
    items = json.loads(fetch(url, min_gap=1.0))["Items"]
    lin = [i for i in items if not i["productName"].endswith("Windows") and "Windows" not in i["productName"]
           and "Low Priority" not in i["skuName"] and i["unitOfMeasure"] == "1 Hour"]
    for kind in ("list_on_demand", "list_spot"):
        src = [i for i in lin if ("Spot" in i["skuName"]) == (kind == "list_spot")]
        st = [r for r in rows if r[1] == sku and r[0] == kind]
        if not st:
            R.add(f"{sku} {kind}", None, [i["retailPrice"] for i in src], None if not src else False, url, "not stored")
            continue
        s = st[0]
        ok = len(src) == 1 and close(s[4], src[0]["retailPrice"], 1e-9, 1e-9) and s[6] == src[0]["effectiveStartDate"][:10]
        R.add(f"{sku} {kind} eastus Linux USD/h", (s[4], s[6]),
              [(i["retailPrice"], i["effectiveStartDate"][:10], i["meterName"]) for i in src], ok, url)
        R.add(f"{sku} {kind} per-GPU-hour = /{s[3]}", s[5], round(s[4] / s[3], 6), close(s[5], s[4] / s[3], 1e-6), url)
R.add("freshness: gpu_prices last_seen_at (UTC)", max(r[7] for r in rows), "<= 2 days", None,
      "https://prices.azure.com/api/retail/prices", "refreshed with datasets job")
R.save()
