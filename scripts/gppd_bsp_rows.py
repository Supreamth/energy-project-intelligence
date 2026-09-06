import csv
from pathlib import Path

p = Path("/tmp/gppd.csv")
with p.open(encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
bsp = [
    r
    for r in rows
    if r.get("country_long") == "Thailand"
    and (r.get("primary_fuel") or "").lower() == "solar"
    and "Bangkok Solar" in ((r.get("owner") or "") + (r.get("source") or ""))
]
print("bsp", len(bsp))
for r in bsp:
    print(r["name"], r["capacity_mw"], r["latitude"], r["longitude"], r.get("owner"))
