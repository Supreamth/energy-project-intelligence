"""Server-rendered product HTML."""

from __future__ import annotations

from html import escape

from energy_intelligence.product import get_project, list_projects

CSS = """
:root { --bg:#0b1020; --text:#eef4ff; --muted:#aebbd3; --line:rgba(255,255,255,.12); --accent:#7dd3fc; }
* { box-sizing:border-box; }
body { margin:0; font-family:ui-sans-serif,system-ui,sans-serif; background:linear-gradient(180deg,#0b1020,#070b16); color:var(--text); line-height:1.55; }
a { color:var(--accent); }
.wrap { width:min(1100px, calc(100% - 32px)); margin:0 auto; padding:28px 0 64px; }
.card { background:rgba(17,26,50,.92); border:1px solid var(--line); border-radius:18px; padding:16px 18px; margin:12px 0; }
.muted { color:var(--muted); }
.tag { display:inline-block; padding:2px 8px; border-radius:999px; border:1px solid var(--line); font-size:12px; }
table { width:100%; border-collapse:collapse; }
th,td { text-align:left; padding:8px 6px; border-bottom:1px solid var(--line); color:var(--muted); }
th { color:var(--text); }
"""


def _shell(title: str, body: str) -> bytes:
    html = f"""<!doctype html>
<html lang="th"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{escape(title)}</title><style>{CSS}</style></head>
<body><div class="wrap">{body}</div></body></html>"""
    return html.encode("utf-8")


def render_list(conn, project_type: str | None) -> bytes:
    rows = list_projects(conn, project_type=project_type)
    items = "\n".join(
        f'<div class="card"><a href="/projects/{r["id"]}">{escape(r["name"] or r["id"])}</a> '
        f'<span class="tag">{escape(r["project_type"])}</span></div>'
        for r in rows
    ) or '<div class="card">ยังไม่มีโครงการที่ผ่าน canonical</div>'
    body = f"""
    <p class="muted"><a href="/">เอกสาร</a> · <a href="/review">Review</a> · ทะเบียนโครงการ</p>
    <h1>Project Intelligence</h1>
    <p class="muted">แสดงเฉพาะค่า canonical ภายใน · กรอง:
      <a href="/projects">ทั้งหมด</a> ·
      <a href="/projects?type=data_center">data_center</a> ·
      <a href="/projects?type=solar_farm">solar_farm</a>
    </p>
    {items}
    """
    return _shell("Projects", body)


def render_detail(conn, project_id: str) -> bytes:
    detail = get_project(conn, project_id)
    caps = "".join(
        f"<tr><td>{escape(str(c['metric']))}</td><td>{escape(str(c['scope']))}</td>"
        f"<td>{escape(str(c['capacity_status']))}</td><td>{escape(str(c['value']))} {escape(str(c['unit'] or ''))}</td>"
        f"<td><a href=\"/review\">evidence {escape(c['evidence_id'][:8])}</a></td></tr>"
        for c in detail["capacity"]
    ) or "<tr><td colspan=5>ยังไม่มี canonical capacity</td></tr>"
    conflicts = "".join(
        f"<li>{escape(str(c['value']))} MW · <a href=\"/review\">evidence {escape(c['evidence_id'][:8])}</a> · {escape(c.get('excerpt') or '')}</li>"
        for c in detail["conflicts"]
    ) or "<li>ไม่มีค่าขัดแย้งที่ accepted</li>"
    sites = ", ".join(escape(s["label"] or s["id"][:8]) for s in detail["sites"]) or "ไม่ทราบ"
    phases = ", ".join(escape(p["label"] or p["phase_key"]) for p in detail["phases"]) or "—"
    body = f"""
    <p class="muted"><a href="/projects">ทะเบียนโครงการ</a></p>
    <h1>{escape(detail['name'])}</h1>
    <p><span class="tag">{escape(detail['project_type'])}</span></p>
    <div class="card"><strong>ไซต์</strong><p class="muted">{sites}</p><strong>เฟส</strong><p class="muted">{phases}</p></div>
    <div class="card">
      <h2>Capacity (canonical)</h2>
      <table><tr><th>metric</th><th>scope</th><th>status</th><th>value</th><th>หลักฐาน</th></tr>{caps}</table>
    </div>
    <div class="card"><h2>ค่าขัดแย้งที่ยังเก็บไว้</h2><ul>{conflicts}</ul></div>
    """
    return _shell(detail["name"], body)
