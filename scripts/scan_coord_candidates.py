import csv
from collections import Counter
from pathlib import Path

import psycopg

with psycopg.connect("postgresql://hermes@127.0.0.1:55432/intelligence") as conn:
    erc = conn.execute(
        """
        SELECT p.entity_id, p.name_th, s.province_code, s.point IS NOT NULL
        FROM intelligence.projects p
        JOIN intelligence.sites s ON s.project_id = p.entity_id
        WHERE p.project_type = 'solar_farm'
        """
    ).fetchall()
print("erc", len(erc))
rows = list(csv.DictReader(Path("/tmp/gppd.csv").open(encoding="utf-8")))
g = [
    r
    for r in rows
    if r.get("country_long") == "Thailand" and (r.get("primary_fuel") or "").lower() == "solar"
]
print("gppd solar", len(g))
print("gppd owners", Counter((r.get("owner") or "")[:50] for r in g).most_common(10))
for label, pred in [
    ("tse", lambda n: "ไทย โซล่าร์" in n or "ไทยโซล่า" in n or "TSE" in n),
    ("spcg", lambda n: "เอสพีซีจี" in n or "SPCG" in n),
    ("merry", lambda n: "เมอร์" in n),
    ("snc", lambda n: "เอสเอ็นซี" in n or "เอส.เอ็น.ซี" in n),
    ("steel", lambda n: "สตีล" in n),
    ("brother", lambda n: "บราเธอร์" in n),
]:
    hits = [r for r in erc if pred(r[1] or "")]
    print(label, len(hits), hits[:4])
