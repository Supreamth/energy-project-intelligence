"""Geocode plant tambon from SPCG addresses. Skip amphoe/province centroids and Bangkok HQ."""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = "EnergyProjectIntelligence/0.2 (research; not a crawler)"
ROOT = Path("/tmp/spcg-subs")

LEGAL = {
    1: ("บริษัท โซล่า เพาเวอร์ (โคราช 1) จำกัด", "โคราช 1)", "นครราชสีมา"),
    2: ("บริษัท โซล่า เพาเวอร์ (สกลนคร 1) จำกัด", "สกลนคร 1)", "สกลนคร"),
    3: ("บริษัท โซล่า เพาเวอร์ (นครพนม 1) จำกัด", "นครพนม 1)", "นครพนม"),
    4: ("บริษัท โซล่า เพาเวอร์ (โคราช 2) จำกัด", "โคราช 2)", "นครราชสีมา"),
    5: ("บริษัท โซล่า เพาเวอร์ (เลย 1) จำกัด", "เลย 1)", "เลย"),
    6: ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 1) จำกัด", "ขอนแก่น 1)", "ขอนแก่น"),
    7: ("บริษัท โซล่า เพาเวอร์ (โคราช 3) จำกัด", "โคราช 3)", "นครราชสีมา"),
    8: ("บริษัท โซล่า เพาเวอร์ (โคราช 4) จำกัด", "โคราช 4)", "นครราชสีมา"),
    9: ("บริษัท โซล่า เพาเวอร์ (โคราช 7) จำกัด", "โคราช 7)", "นครราชสีมา"),
    10: ("บริษัท โซล่า เพาเวอร์ (โคราช 5) จำกัด", "โคราช 5)", "นครราชสีมา"),
    11: ("บริษัท โซล่า เพาเวอร์ (โคราช 8) จำกัด", "โคราช 8)", "นครราชสีมา"),
    12: ("บริษัท โซล่า เพาเวอร์ (โคราช 9) จำกัด", "โคราช 9)", "นครราชสีมา"),
    13: ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 3) จำกัด", "ขอนแก่น 3)", "ขอนแก่น"),
    14: ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 4) จำกัด", "ขอนแก่น 4)", "ขอนแก่น"),
    15: ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 5) จำกัด", "ขอนแก่น 5)", "ขอนแก่น"),
    16: ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 8) จำกัด", "ขอนแก่น 8)", "ขอนแก่น"),
    17: ("บริษัท โซล่า เพาเวอร์ (โคราช 6) จำกัด", "โคราช 6)", "นครราชสีมา"),
    18: ("บริษัท โซล่า เพาเวอร์ (บุรีรัมย์ 1) จำกัด", "บุรีรัมย์ 1)", "บุรีรัมย์"),
    19: ("บริษัท โซล่า เพาเวอร์ (บุรีรัมย์ 2) จำกัด", "บุรีรัมย์ 2)", "บุรีรัมย์"),
    20: ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 2) จำกัด", "ขอนแก่น 2)", "ขอนแก่น"),
    21: ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 7) จำกัด", "ขอนแก่น 7)", "ขอนแก่น"),
    22: ("บริษัท โซล่า เพาเวอร์ (นครพนม 2) จำกัด", "นครพนม 2)", "นครพนม"),
    23: ("บริษัท โซล่า เพาเวอร์ (หนองคาย 1) จำกัด", "หนองคาย 1)", "บึงกาฬ"),
    24: ("บริษัท โซล่า เพาเวอร์ (บุรีรัมย์ 3) จำกัด", "บุรีรัมย์ 3)", "บุรีรัมย์"),
    25: ("บริษัท โซล่า เพาเวอร์ (นครพนม 3) จำกัด", "นครพนม 3)", "นครพนม"),
    26: ("บริษัท โซล่า เพาเวอร์ (อุดรธานี 1) จำกัด", "อุดรธานี 1)", "อุดรธานี"),
    27: ("บริษัท โซล่า เพาเวอร์ (เลย 2) จำกัด", "เลย 2)", "เลย"),
    28: ("บริษัท โซล่า เพาเวอร์ (สกลนคร 2) จำกัด", "สกลนคร 2)", "สกลนคร"),
    29: ("บริษัท โซล่า เพาเวอร์ (สุรินทร์ 3) จำกัด", "สุรินทร์ 3)", "สุรินทร์"),
    30: ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 9) จำกัด", "ขอนแก่น 9)", "ขอนแก่น"),
    31: ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 10) จำกัด", "ขอนแก่น 10)", "ขอนแก่น"),
    32: ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 6) จำกัด", "ขอนแก่น 6)", "ขอนแก่น"),
    33: ("บริษัท โซล่า เพาเวอร์ (สุรินทร์ 1) จำกัด", "สุรินทร์ 1)", "สุรินทร์"),
    34: ("บริษัท โซล่า เพาเวอร์ (สุรินทร์ 2) จำกัด", "สุรินทร์ 2)", "สุรินทร์"),
}

GUNKUL = [
    ("สาขาศรีจุฬา", "นครนายก", "Si Chula, Mueang Nakhon Nayok, Nakhon Nayok, Thailand"),
    ("สาขาวิเชียรบุรี", "เพชรบูรณ์", "Sam Yaek, Wichian Buri, Phetchabun, Thailand"),
    ("สาขาเนินปอ", "พิจิตร", "Noen Po, Sam Ngam, Phichit, Thailand"),
    ("สาขาบึงสามพัน", "เพชรบูรณ์", "Subsomboon, Bueng Sam Phan, Phetchabun, Thailand"),
]

OK_TYPES = {
    "village",
    "hamlet",
    "suburb",
    "quarter",
    "neighbourhood",
    "isolated_dwelling",
    "town",
    "municipality",
    "city_district",
}
# Nominatim addresstype for tambon is often "suburb" or "city_district" or "village"
# skip county/state/province


def parse_location(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html).replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text)
    m = re.search(r"Location\s*:?\s*(.+?)\s+Commercial Operation", text, re.I)
    if not m:
        return ""
    return re.sub(r"^:\s*", "", m.group(1).strip(" :"))


def tambon_query(loc: str) -> str | None:
    # "548 Moo 8 Ban Phue Sub District, Ban Phue District, Udon Thani Province"
    m = re.search(
        r"(.+?)\s+Sub[\s-]?District,\s*(.+?)\s+District,?\s*(.+?)\s+Province",
        loc,
        re.I,
    )
    if not m:
        return None
    tambon, amphoe, province = (x.strip(" ,") for x in m.groups())
    tambon = re.sub(r"^\d[\d/]*\s*(Moo\s*\d+\s*)?", "", tambon, flags=re.I).strip(" ,")
    return f"{tambon}, {amphoe}, {province}, Thailand"


def geocode(query: str) -> dict | None:
    q = urllib.parse.urlencode(
        {"q": query, "format": "jsonv2", "limit": 3, "countrycodes": "th", "addressdetails": 1}
    )
    req = urllib.request.Request(
        f"https://nominatim.openstreetmap.org/search?{q}",
        headers={"User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.loads(r.read().decode())
    for hit in data:
        lat, lon = float(hit["lat"]), float(hit["lon"])
        addrt = (hit.get("addresstype") or hit.get("type") or "").lower()
        cls = (hit.get("class") or "").lower()
        if not (5.5 < lat < 20.6 and 97.2 < lon < 105.7):
            continue
        if 13.65 < lat < 13.85 and 100.45 < lon < 100.65:
            continue
        if addrt in {"county", "state", "province", "country"}:
            continue
        if cls == "boundary" and addrt in {"county", "state"}:
            continue
        # allow administrative boundary if it's tambon-rank (place_rank >= 16 typically tambon)
        rank = int(hit.get("place_rank") or 0)
        if cls == "boundary" and rank < 14:
            continue
        acc = 2500 if rank >= 16 or addrt in OK_TYPES else 4000
        if rank < 14:
            acc = 8000
            continue
        return {
            "lat": lat,
            "lon": lon,
            "display": hit.get("display_name"),
            "addresstype": addrt,
            "rank": rank,
            "accuracy_m": acc,
        }
    return None


def main() -> None:
    rows = []
    for i, (legal, needle, province) in LEGAL.items():
        html = (ROOT / f"{i}.html").read_text("utf-8", errors="replace")
        loc = parse_location(html)
        query = tambon_query(loc)
        hit = geocode(query) if query else None
        time.sleep(1.05)
        print(i, "OK" if hit else "MISS", query, hit and hit.get("display"))
        rows.append(
            {
                "id": i,
                "legal_name": legal,
                "name_contains": needle,
                "province": province,
                "address": loc,
                "query": query,
                "hit": hit,
                "source_url": f"https://www.spcg.co.th/en/getsubsidiaries/x/{i}",
            }
        )
    gunkul = []
    for needle, province, query in GUNKUL:
        hit = geocode(query)
        time.sleep(1.05)
        print("g", needle, "OK" if hit else "MISS", hit and hit.get("display"))
        gunkul.append(
            {
                "legal_name": "บริษัท กันกุล ชูบุ พาวเวอร์เจน จำกัด",
                "website": "https://www.gunkul.com/en/businesses/energy-business/solar-farm",
                "name_contains": needle,
                "province": province,
                "query": query,
                "hit": hit,
                "source_url": "https://www.gunkul.com/storage/document/annual-reports/2024/attachment-en.pdf",
            }
        )
    Path("/tmp/spcg-geocode.json").write_text(
        json.dumps({"spcg": rows, "gunkul": gunkul}, ensure_ascii=False, indent=2)
    )
    ok = sum(1 for r in rows if r["hit"]) + sum(1 for r in gunkul if r["hit"])
    print("ok", ok)


if __name__ == "__main__":
    main()
