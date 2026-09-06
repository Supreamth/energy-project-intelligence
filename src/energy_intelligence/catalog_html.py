"""Source catalog page."""

from __future__ import annotations

from html import escape

from energy_intelligence.catalog import load_sources
from energy_intelligence.product_html import _shell

MODE_TH = {
    "cli_import": "CLI นำเข้า",
    "manual_first": "คัดลอกด้วยมือก่อน",
    "manual_url_list": "รับ URL ที่ละรายการ",
    "manual_release": "เมื่อมีไฟล์ release",
}


def render_sources(notice: str | None = None) -> bytes:
    rows = load_sources()
    cards = []
    for row in rows:
        conn = row.get("connection") or {}
        related = "".join(
            f'<li><a href="{escape(u)}" rel="noopener">{escape(u)}</a></li>' for u in row.get("related_urls") or []
        )
        enabled = "เปิดใช้" if row.get("enabled") else "ยังไม่เปิดดึงอัตโนมัติ"
        cards.append(
            f"""
            <article class="panel" id="{escape(row['code'])}">
              <p class="kicker">{escape(row['code'])} · {escape(row['access_method'])} · {escape(row['rights_status'])} · {enabled}</p>
              <h2 style="text-transform:none;letter-spacing:0;font-size:22px;color:var(--ink)">{escape(row['name_th'])}</h2>
              <p class="meta">{escape(row['name_en'])}</p>
              <p><strong>เป้าหมาย:</strong> {escape(row['goal'])}</p>
              <p><strong>เว็บหลัก:</strong> <a href="{escape(row['base_url'])}" rel="noopener">{escape(row['base_url'])}</a></p>
              <p><strong>วิธีเชื่อมต่อ:</strong> {escape(MODE_TH.get(conn.get('mode',''), conn.get('mode') or ''))}</p>
              <p><strong>การยืนยันตัวตน:</strong> {escape(conn.get('auth') or '—')}</p>
              <p><strong>วิธีทำ:</strong> {escape(conn.get('how') or '')}</p>
              <p class="meta">{escape(conn.get('notes') or '')}</p>
              {'<ul>'+related+'</ul>' if related else ''}
              <form class="upload" method="post" enctype="multipart/form-data" action="/sources/{escape(row['code'])}/upload">
                <label class="meta">อัปโหลดไฟล์ด้วยมือ (ไม่เปิด collector)</label>
                <input type="file" name="file" required />
                <button type="submit">อัปโหลดไฟล์</button>
              </form>
            </article>
            """
        )
    banner = f'<p class="panel">{escape(notice)}</p>' if notice else ""
    body = f"""
    <p class="kicker">แหล่งข้อมูลรุ่นแรก · ยังไม่เปิด collector</p>
    <h1>เป้าหมายการเก็บข้อมูล</h1>
    <p class="lede">เริ่มจากแหล่งสาธารณะที่ระบุได้ บันทึกวิธีเชื่อมต่อให้ชัด และดึงด้วยมือก่อน สิทธิ unknown ห้ามเผยแพร่ภายนอก</p>
    {banner}
    {''.join(cards)}
    """
    return _shell("แหล่งข้อมูล", body)
