"""Coverage / readiness monitor."""

from __future__ import annotations

from html import escape

from energy_intelligence.coverage import coverage_report
from energy_intelligence.product_html import _shell

PRIORITY_TH = {"required": "ต้องมี", "desired": "ควรมี", "optional": "มีเมื่อแหล่งบอก"}


def render_coverage(conn) -> bytes:
    report = coverage_report(conn)
    blocks = [_type_block("โซลาร์ฟาร์ม", report["types"]["solar_farm"])]
    blocks.append(_type_block("ศูนย์ข้อมูล", report["types"]["data_center"]))
    preds = "".join(
        f"<li><code>{escape(p['predicate'])}</code></li>" for p in report["registry_predicates"]
    )
    notes = "".join(f"<li>{escape(n)}</li>" for n in report["notes"])
    body = f"""
    <p class="kicker">Monitor · schema v0.2</p>
    <h1>ความพร้อมของข้อมูล</h1>
    <p class="lede">เทียบของที่มีในฐาน กับช่องที่สัญญา schema ต้องการ ไม่เติมค่าที่ไม่มีหลักฐาน</p>
    {''.join(blocks)}
    <div class="panel">
      <h2>Predicate ที่เปิดใน registry 0.2.0</h2>
      <ul>{preds}</ul>
    </div>
    <div class="panel">
      <h2>กติกาที่หน้านี้ยึด</h2>
      <ul>{notes}</ul>
    </div>
    """
    return _shell("ความพร้อมข้อมูล", body)


def _type_block(title: str, data: dict) -> str:
    n = data["n"]
    score = data["required_score"]
    rows = []
    for slot in data["slots"]:
        pct = slot["pct"]
        width = max(pct, 0)
        rows.append(
            f"""
            <tr>
              <td>{escape(slot['label'])}<div class="meta">{escape(slot['key'])} · {escape(slot['schema_object'])}</div></td>
              <td>{PRIORITY_TH.get(slot['priority'], slot['priority'])}</td>
              <td class="num">{slot['present']} / {slot['n']}</td>
              <td>
                <div class="bar"><span style="width:{width}%"></span></div>
                <span class="meta">{pct}%</span>
              </td>
            </tr>
            """
        )
    return f"""
    <section class="panel">
      <h2 style="text-transform:none;letter-spacing:0;font-size:22px;color:var(--ink)">{escape(title)}</h2>
      <p class="stat">{score}<span class="stat-unit">% ช่องที่ต้องมี</span></p>
      <p class="meta">{n} โครงการในฐาน</p>
      <table>
        <thead><tr><th>ช่องตาม schema</th><th>ความสำคัญ</th><th>มีแล้ว</th><th>สัดส่วน</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
    """
