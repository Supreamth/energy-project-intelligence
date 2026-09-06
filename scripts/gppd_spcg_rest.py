import csv
from pathlib import Path

needles = (
    "Udon",
    "Surin",
    "Sakon",
    "Nong Khai",
    "Si Chula",
    "Wichian",
    "Noen",
    "Dong Khon",
    "Ta Khit",
    "Gunkul",
    "Bueng",
)
with Path("/tmp/gppd.csv").open(newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if row.get("country") != "THA":
            continue
        if (row.get("primary_fuel") or "").lower() != "solar":
            continue
        blob = " ".join(
            [
                row.get("name") or "",
                row.get("owner") or "",
                row.get("source") or "",
            ]
        )
        if any(n.lower() in blob.lower() for n in needles):
            print(
                f"{row['name']}|{row['owner']}|{row['latitude']}|{row['longitude']}|{row['capacity_mw']}"
            )
