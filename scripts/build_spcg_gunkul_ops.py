import csv
import json
from pathlib import Path

LEGAL = {
    "Solar Power (Korat 1) Company Limited": ("บริษัท โซล่า เพาเวอร์ (โคราช 1) จำกัด", "โคราช 1)", "นครราชสีมา"),
    "Solar Power (Korat 2) Company Limited": ("บริษัท โซล่า เพาเวอร์ (โคราช 2) จำกัด", "โคราช 2)", "นครราชสีมา"),
    "Solar Power (Korat 3) Company Limited": ("บริษัท โซล่า เพาเวอร์ (โคราช 3) จำกัด", "โคราช 3)", "นครราชสีมา"),
    "Solar Power (Korat 4) Company Limited": ("บริษัท โซล่า เพาเวอร์ (โคราช 4) จำกัด", "โคราช 4)", "นครราชสีมา"),
    "Solar Power (Korat 5) Company Limited": ("บริษัท โซล่า เพาเวอร์ (โคราช 5) จำกัด", "โคราช 5)", "นครราชสีมา"),
    "Solar Power (Korat 6) Company Limited": ("บริษัท โซล่า เพาเวอร์ (โคราช 6) จำกัด", "โคราช 6)", "นครราชสีมา"),
    "Solar Power (Korat 7) Company Limited": ("บริษัท โซล่า เพาเวอร์ (โคราช 7) จำกัด", "โคราช 7)", "นครราชสีมา"),
    "Solar Power (Korat 8) Company Limited": ("บริษัท โซล่า เพาเวอร์ (โคราช 8) จำกัด", "โคราช 8)", "นครราชสีมา"),
    "Solar Power (Korat 9) Company Limited": ("บริษัท โซล่า เพาเวอร์ (โคราช 9) จำกัด", "โคราช 9)", "นครราชสีมา"),
    "Solar Power (Khon Kaen 1) Company Limited": ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 1) จำกัด", "ขอนแก่น 1)", "ขอนแก่น"),
    "Solar Power (Khon Kaen 2) Company Limited": ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 2) จำกัด", "ขอนแก่น 2)", "ขอนแก่น"),
    "Solar Power (Khon Kaen 3) Company Limited": ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 3) จำกัด", "ขอนแก่น 3)", "ขอนแก่น"),
    "Solar Power (Khon Kaen 4) Company Limited": ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 4) จำกัด", "ขอนแก่น 4)", "ขอนแก่น"),
    "Solar Power (Khon Kaen 5) Company Limited": ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 5) จำกัด", "ขอนแก่น 5)", "ขอนแก่น"),
    "Solar Power (Khon Kaen 6) Company Limited": ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 6) จำกัด", "ขอนแก่น 6)", "ขอนแก่น"),
    "Solar Power (Khon Kaen 7) Company Limited": ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 7) จำกัด", "ขอนแก่น 7)", "ขอนแก่น"),
    "Solar Power (Khon Kaen 8) Company Limited": ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 8) จำกัด", "ขอนแก่น 8)", "ขอนแก่น"),
    "Solar Power (Khon Kaen 9) Company Limited": ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 9) จำกัด", "ขอนแก่น 9)", "ขอนแก่น"),
    "Solar Power (Khon Kaen 10) Company Limited": ("บริษัท โซล่า เพาเวอร์ (ขอนแก่น 10) จำกัด", "ขอนแก่น 10)", "ขอนแก่น"),
    "Solar Power (Bureerum 1) Company Limited": ("บริษัท โซล่า เพาเวอร์ (บุรีรัมย์ 1) จำกัด", "บุรีรัมย์ 1)", "บุรีรัมย์"),
    "Solar Power (Bureerum 2) Company Limited": ("บริษัท โซล่า เพาเวอร์ (บุรีรัมย์ 2) จำกัด", "บุรีรัมย์ 2)", "บุรีรัมย์"),
    "Solar Power (Bureerum 3) Company Limited": ("บริษัท โซล่า เพาเวอร์ (บุรีรัมย์ 3) จำกัด", "บุรีรัมย์ 3)", "บุรีรัมย์"),
    "Solar Power (Nakhon Phanom 1) Company Limited": ("บริษัท โซล่า เพาเวอร์ (นครพนม 1) จำกัด", "นครพนม 1)", "นครพนม"),
    "Solar Power (Nakhon Phanom 2) Company Limited": ("บริษัท โซล่า เพาเวอร์ (นครพนม 2) จำกัด", "นครพนม 2)", "นครพนม"),
    "Solar Power (Nakhon Phanom 3) Company Limited": ("บริษัท โซล่า เพาเวอร์ (นครพนม 3) จำกัด", "นครพนม 3)", "นครพนม"),
    "Solar Power (Sakon Nakhon 1) Company Limited": ("บริษัท โซล่า เพาเวอร์ (สกลนคร 1) จำกัด", "สกลนคร 1)", "สกลนคร"),
    "Solar Power (Sakon Nakhon 2) Company Limited": ("บริษัท โซล่า เพาเวอร์ (สกลนคร 2) จำกัด", "สกลนคร 2)", "สกลนคร"),
    "Solar Power (Surin 1) Company Limited": ("บริษัท โซล่า เพาเวอร์ (สุรินทร์ 1) จำกัด", "สุรินทร์ 1)", "สุรินทร์"),
    "Solar Power (Surin 2) Company Limited": ("บริษัท โซล่า เพาเวอร์ (สุรินทร์ 2) จำกัด", "สุรินทร์ 2)", "สุรินทร์"),
    "Solar Power (Surin 3) Company Limited": ("บริษัท โซล่า เพาเวอร์ (สุรินทร์ 3) จำกัด", "สุรินทร์ 3)", "สุรินทร์"),
    "Solar Power (Loei 1) Company Limited": ("บริษัท โซล่า เพาเวอร์ (เลย 1) จำกัด", "เลย 1)", "เลย"),
    "Solar Power (Loei 2) Company Limited": ("บริษัท โซล่า เพาเวอร์ (เลย 2) จำกัด", "เลย 2)", "เลย"),
    "Solar Power (Nong Khai 1) Company Limited": ("บริษัท โซล่า เพาเวอร์ (หนองคาย 1) จำกัด", "หนองคาย 1)", "บึงกาฬ"),
    "Solar Power (Udon Thani 1) Company Limited": ("บริษัท โซล่า เพาเวอร์ (อุดรธานี 1) จำกัด", "อุดรธานี 1)", "อุดรธานี"),
}

gunkul_sites = {
    "Sri Chula Solar Power Plant": ("สาขาศรีจุฬา", "นครนายก"),
    "Wichian Buri Solar Power Plant": ("สาขาวิเชียรบุรี", "เพชรบูรณ์"),
    "Noen Po Solar Power Plant": ("สาขาเนินปอ", "พิจิตร"),
}

rows = []
with Path("/tmp/gppd.csv").open(newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if row.get("country") != "THA" or (row.get("primary_fuel") or "").lower() != "solar":
            continue
        owner = (row.get("owner") or "").strip()
        name = (row.get("name") or "").strip()
        if owner in LEGAL:
            legal, needle, province = LEGAL[owner]
            rows.append(
                {
                    "legal_name": legal,
                    "website": "https://www.spcg.co.th/th/home",
                    "notes": "พิกัดโรงไฟฟ้าจาก GPPD ของบริษัทย่อย SPCG ที่หน้าบริษัทระบุเป็นที่ตั้งฟาร์ม ไม่ใช่ HQ กรุงเทพฯ.",
                    "sites": [
                        {
                            "name_contains": needle,
                            "province": province,
                            "lat": float(row["latitude"]),
                            "lon": float(row["longitude"]),
                            "location_method": "gppd",
                            "accuracy_m": 500,
                            "source_url": "https://datasets.wri.org/dataset/globalpowerplantdatabase",
                            "excerpt": f"GPPD {name} owner {owner}",
                        }
                    ],
                }
            )
        if name in gunkul_sites and "Gunkul" in owner:
            needle, province = gunkul_sites[name]
            rows.append(
                {
                    "legal_name": "บริษัท กันกุล ชูบุ พาวเวอร์เจน จำกัด",
                    "website": "https://www.gunkul.com/en/businesses/energy-business/solar-farm",
                    "notes": "พิกัดจาก GPPD ของสาขาที่รายงานประจำปีระบุว่าเป็นที่ดินผลิตไฟฟ้า ไม่ใช่สำนักงาน OCC.",
                    "sites": [
                        {
                            "name_contains": needle,
                            "province": province,
                            "lat": float(row["latitude"]),
                            "lon": float(row["longitude"]),
                            "location_method": "gppd",
                            "accuracy_m": 500,
                            "source_url": "https://datasets.wri.org/dataset/globalpowerplantdatabase",
                            "excerpt": f"GPPD {name}",
                        }
                    ],
                }
            )

# merge gunkul into one operator
merged = {}
for r in rows:
    key = r["legal_name"]
    if key not in merged:
        merged[key] = r
    else:
        merged[key]["sites"].extend(r["sites"])
        if r.get("website") and not merged[key].get("website"):
            merged[key]["website"] = r["website"]

out = list(merged.values())
Path("/tmp/spcg-gunkul-ops.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
print("operators", len(out), "sites", sum(len(x["sites"]) for x in out))
