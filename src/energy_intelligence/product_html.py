"""Server-rendered product HTML. Explore list + inspect detail."""

from __future__ import annotations

from html import escape

from energy_intelligence.product import get_project, list_projects

TYPE_TH = {"data_center": "ศูนย์ข้อมูล", "solar_farm": "โซลาร์ฟาร์ม"}
METRIC_TH = {
    "dc_it_load": "IT load",
    "dc_facility_power": "กำลังไฟสถานที่",
    "solar_dc": "DC (MWp)",
    "solar_ac": "AC",
    "export_limit": "ขีดจำกัดจ่ายไฟ",
    "contracted_power": "กำลังตามสัญญา",
}
STATUS_TH = {"planned": "ตามแผน", "operating": "เดินเครื่อง", "unknown": "ไม่ทราบ"}
SCOPE_TH = {"phase": "เฟส", "project": "โครงการ", "unknown": "ไม่ทราบขอบเขต"}

CSS = """
:root {
  --bg: #0c0f14; --ink: #f4f1ea; --muted: #9aa3b2; --line: rgba(244,241,234,.12);
  --paper: #141922; --accent: #c9a227; --ok: #8fbf9f; --warn: #d4a574;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  font-family: "Segoe UI", "Noto Sans Thai", ui-sans-serif, system-ui, sans-serif;
  background: var(--bg);
  color: var(--ink);
  line-height: 1.5;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.top {
  position: sticky; top: 0; z-index: 2;
  background: rgba(12,15,20,.92); backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--line);
}
.top-inner, .wrap { width: min(1120px, calc(100% - 32px)); margin: 0 auto; }
.top-inner { display: flex; gap: 16px; align-items: center; padding: 12px 0; font-size: 14px; }
.top-inner nav { display: flex; gap: 14px; margin-left: auto; }
.wrap { padding: 28px 0 72px; }
h1 { font-family: Georgia, "Iowan Old Style", serif; font-size: clamp(28px, 4vw, 44px); letter-spacing: -.03em; margin: 0 0 8px; }
h2 { font-size: 15px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); margin: 0 0 12px; }
.lede { color: var(--muted); max-width: 46rem; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; margin: 22px 0 18px; }
.filters a, .pill {
  display: inline-flex; align-items: center; min-height: 36px;
  padding: 0 12px; border: 1px solid var(--line); border-radius: 999px;
  color: var(--ink); font-size: 13px; font-weight: 650;
}
.filters a[aria-current="page"] { background: var(--ink); color: var(--bg); border-color: var(--ink); }
.row {
  display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: baseline;
  padding: 16px 0; border-bottom: 1px solid var(--line);
}
.row .name { font-size: 20px; color: var(--ink); }
.kicker { font-size: 12px; color: var(--muted); letter-spacing: .04em; }
.hero { display: grid; grid-template-columns: 1.2fr .8fr; gap: 28px; margin: 18px 0 28px; }
.stat {
  font-variant-numeric: tabular-nums;
  font-size: clamp(40px, 6vw, 64px); line-height: .95; letter-spacing: -.04em;
}
.stat-unit { font-size: 18px; color: var(--muted); margin-left: 6px; }
.meta { color: var(--muted); font-size: 14px; margin-top: 8px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.panel { background: var(--paper); border: 1px solid var(--line); border-radius: 4px; padding: 18px; }
table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--line); font-size: 14px; }
th { color: var(--muted); font-weight: 650; }
.map { width: 100%; height: 280px; border: 0; border-radius: 4px; filter: grayscale(.2) contrast(1.05); }
.unknown { color: var(--warn); }
.empty { color: var(--muted); padding: 28px 0; }
form.upload { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-top:14px; padding-top:14px; border-top:1px solid var(--line); }
form.upload input[type=file] { color: var(--muted); max-width: 100%; }
form.upload button {
  min-height: 44px; padding: 0 16px; border: 0; border-radius: 4px;
  background: var(--accent); color: #1a1404; font-weight: 750; cursor: pointer;
}
@media (max-width: 800px) {
  .hero, .grid2, .row { grid-template-columns: 1fr; }
}
"""


def _shell(title: str, body: str) -> bytes:
    html = f"""<!doctype html>
<html lang="th"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{escape(title)}</title><style>{CSS}</style>
</head><body>
<div class="top"><div class="top-inner">
  <strong>Enerise</strong>
  <nav><a href="/">เอกสาร</a><a href="/projects">โครงการ</a><a href="/sources">แหล่งข้อมูล</a><a href="/review">Review</a></nav>
</div></div>
<div class="wrap">{body}</div>
</body></html>"""
    return html.encode("utf-8")


def render_list(conn, project_type: str | None) -> bytes:
    rows = list_projects(conn, project_type=project_type)

    def chip(label: str, href: str, current: bool) -> str:
        cur = ' aria-current="page"' if current else ""
        return f'<a href="{href}"{cur}>{escape(label)}</a>'

    filters = (
        chip("ทั้งหมด", "/projects", project_type is None)
        + chip("ศูนย์ข้อมูล", "/projects?type=data_center", project_type == "data_center")
        + chip("โซลาร์ฟาร์ม", "/projects?type=solar_farm", project_type == "solar_farm")
    )
    items = "\n".join(
        f'<div class="row"><a class="name" href="/projects/{r["id"]}">{escape(r["name"] or r["id"])}</a>'
        f'<span class="kicker">{escape(TYPE_TH.get(r["project_type"], r["project_type"]))}</span></div>'
        for r in rows
    ) or '<p class="empty">ยังไม่มีโครงการในมุมมองนี้</p>'
    body = f"""
    <p class="kicker">ทะเบียนภายใน · ค่า canonical เท่านั้น</p>
    <h1>โครงการ</h1>
    <p class="lede">อ่านค่าที่ผู้ตรวจเลือกแล้ว แต่ยังเก็บหลักฐานที่ขัดกันไว้ให้เปิดดูได้</p>
    <div class="filters">{filters}</div>
    {items}
    """
    return _shell("โครงการ", body)


def render_detail(conn, project_id: str) -> bytes:
    detail = get_project(conn, project_id)
    type_label = TYPE_TH.get(detail["project_type"], detail["project_type"])
    primary = detail["capacity"][0] if detail["capacity"] else None
    hero_stat = (
        f'<div class="stat">{escape(str(primary["value"]))}<span class="stat-unit">{escape(str(primary.get("unit") or "MW"))}</span></div>'
        f'<p class="meta">{escape(METRIC_TH.get(primary["metric"], primary["metric"]))} · '
        f'{escape(SCOPE_TH.get(primary["scope"], primary["scope"] or ""))} · '
        f'{escape(STATUS_TH.get(primary["capacity_status"], primary["capacity_status"] or ""))} · '
        f'<a href="/review">หลักฐาน {escape(primary["evidence_id"][:8])}</a></p>'
        if primary
        else '<p class="unknown">ยังไม่มีค่า canonical สำหรับกำลังผลิต/โหลด</p>'
    )
    cap_rows = "".join(
        f"<tr><td>{escape(METRIC_TH.get(c['metric'], c['metric']))}</td>"
        f"<td>{escape(SCOPE_TH.get(c['scope'], c['scope'] or '—'))}</td>"
        f"<td>{escape(STATUS_TH.get(c['capacity_status'], c['capacity_status'] or '—'))}</td>"
        f"<td>{escape(str(c['value']))} {escape(str(c['unit'] or ''))}</td>"
        f"<td><a href=\"/review\"> {escape(c['evidence_id'][:8])}</a></td></tr>"
        for c in detail["capacity"]
    ) or "<tr><td colspan=5>ไม่มี canonical capacity</td></tr>"
    conflicts = "".join(
        f"<li>{escape(str(c['value']))} · <a href=\"/review\">{escape(c['evidence_id'][:8])}</a>"
        f" — {escape(c.get('excerpt') or '')}</li>"
        for c in detail["conflicts"]
    ) or "<li>ไม่มีค่าขัดแย้งที่ accepted</li>"
    site_blocks = []
    for site in detail["sites"]:
        coords = site.get("coordinates")
        if coords:
            lon, lat = coords["lon"], coords["lat"]
            bbox = f"{lon-0.03},{lat-0.03},{lon+0.03},{lat+0.03}"
            method = escape(site.get("location_method") or "พิกัดจากหลักฐาน")
            site_blocks.append(
                f'<p>{escape(site.get("label") or "ไซต์")}</p>'
                f'<p class="meta">{method}</p>'
                f'<iframe class="map" title="แผนที่ไซต์" src="https://www.openstreetmap.org/export/embed.html?bbox={bbox}&amp;layer=mapnik&amp;marker={lat}%2C{lon}"></iframe>'
            )
        else:
            site_blocks.append(
                f'<p>{escape(site.get("label") or "ไซต์")}</p>'
                f'<p class="unknown">ไม่ทราบพิกัด — ไม่ใช้ที่อยู่สำนักงานใหญ่แทน</p>'
            )
    if not site_blocks:
        site_blocks.append('<p class="unknown">ยังไม่มีไซต์</p>')
    phases = ", ".join(escape(p["label"] or p["phase_key"]) for p in detail["phases"]) or "—"
    body = f"""
    <p class="kicker"><a href="/projects">← ทะเบียน</a> · {escape(type_label)}</p>
    <h1>{escape(detail["name"])}</h1>
    <div class="hero">
      <div>{hero_stat}</div>
      <div class="panel"><h2>ที่ตั้ง</h2>{''.join(site_blocks)}<p class="meta">เฟส: {phases}</p></div>
    </div>
    <div class="grid2">
      <div class="panel">
        <h2>Capacity ที่เลือกใช้</h2>
        <table><thead><tr><th>ชนิด</th><th>ขอบเขต</th><th>สถานะ</th><th>ค่า</th><th>หลักฐาน</th></tr></thead>
        <tbody>{cap_rows}</tbody></table>
      </div>
      <div class="panel">
        <h2>หลักฐานที่ยังขัดกัน</h2>
        <ul>{conflicts}</ul>
        <p class="meta">เก็บไว้ ไม่ลบ และไม่ถูกนำไปรวมกับค่า canonical</p>
      </div>
    </div>
    """
    return _shell(detail["name"], body)
