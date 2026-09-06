import csv
import io
from collections import Counter
from pathlib import Path

import psycopg

text = Path("/tmp/boi-upload.csv").read_text(encoding="utf-8-sig")
rows = list(csv.DictReader(io.StringIO(text)))
print("rows", len(rows))
print("cols", list(rows[0].keys()) if rows else None)
names = [r["Company Name"].strip() for r in rows]
print("unique_companies", len(set(names)))
print("unique_com_id", len({r["COM_ID"].strip() for r in rows if r.get("COM_ID")}))
print("unique_hp_id", len({r["HP_ID"].strip() for r in rows if r.get("HP_ID")}))
print("products")
for k, n in Counter(r["Products"].strip() for r in rows).most_common(12):
    print(f"  {n:4d} {k[:80]}")
print("provinces")
for k, n in Counter(r["Province"].strip() for r in rows).most_common(12):
    print(f"  {n:4d} {k}")
print("top companies")
for k, n in Counter(names).most_common(12):
    print(f"  {n:4d} {k}")
bkk = sum(1 for r in rows if "กรุงเทพ" in r["Province"])
print("bangkok_rows", bkk)

with psycopg.connect("postgresql://hermes@127.0.0.1:55432/intelligence") as conn:
    orgs = {r[0] for r in conn.execute("SELECT legal_name FROM intelligence.organizations")}
hit = [n for n in set(names) if n in orgs]
print("exact_name_in_erc_orgs", len(hit), "/", len(set(names)))
print("sample unmatched")
miss = [n for n in sorted(set(names)) if n not in orgs][:8]
for n in miss:
    print(" -", n)
print("sample matched")
for n in sorted(hit)[:8]:
    print(" -", n)
print("first3")
for r in rows[:3]:
    print(dict(r))
