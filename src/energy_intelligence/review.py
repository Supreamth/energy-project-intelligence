"""Review events and canonical selection for schema v0.2."""

from __future__ import annotations

import uuid


def attach_demo_phase(conn, *, evidence_id) -> uuid.UUID:
    """Create or reuse a demo phase and attach it as evidence subject."""
    row = conn.execute(
        """
        SELECT ev.subject_entity_id, r.external_key
        FROM intelligence.evidence ev
        JOIN intelligence.raw_records r ON r.id = ev.raw_record_id
        WHERE ev.id = %s
        """,
        (evidence_id,),
    ).fetchone()
    if row is None:
        raise ValueError("evidence not found")
    subject_id, external_key = row
    if subject_id:
        return subject_id
    project_id, site_id, phase_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    conn.execute("INSERT INTO intelligence.entities(id, kind) VALUES (%s, 'project')", (project_id,))
    conn.execute(
        "INSERT INTO intelligence.projects(entity_id, name_en, project_type) VALUES (%s, %s, 'data_center')",
        (project_id, f"Demo {external_key}"),
    )
    conn.execute("INSERT INTO intelligence.entities(id, kind) VALUES (%s, 'site')", (site_id,))
    conn.execute(
        "INSERT INTO intelligence.sites(entity_id, project_id, label) VALUES (%s, %s, 'demo')",
        (site_id, project_id),
    )
    conn.execute("INSERT INTO intelligence.entities(id, kind) VALUES (%s, 'phase')", (phase_id,))
    conn.execute(
        "INSERT INTO intelligence.phases(entity_id, site_id, phase_key, label) VALUES (%s, %s, 'A', 'Phase A')",
        (phase_id, site_id),
    )
    conn.execute(
        "UPDATE intelligence.evidence SET subject_entity_id = %s WHERE id = %s",
        (phase_id, evidence_id),
    )
    return phase_id


def accept_evidence(conn, *, evidence_id, actor: str, reason: str) -> None:
    _transition(conn, evidence_id=evidence_id, to_status="accepted", actor=actor, reason=reason)


def reject_evidence(conn, *, evidence_id, actor: str, reason: str) -> None:
    _transition(conn, evidence_id=evidence_id, to_status="rejected", actor=actor, reason=reason)
    _invalidate_if_selected(conn, evidence_id=evidence_id, reason=f"evidence rejected: {reason}")


def select_canonical(
    conn,
    *,
    evidence_id,
    field_key: str,
    actor: str,
    reason: str,
    publication_class: str = "internal",
):
    row = conn.execute(
        """
        SELECT review_status, subject_entity_id, predicate
        FROM intelligence.evidence
        WHERE id = %s
        """,
        (evidence_id,),
    ).fetchone()
    if row is None:
        raise ValueError("evidence not found")
    status, subject_id, predicate = row
    if status != "accepted":
        raise ValueError("evidence must be accepted before canonical selection")
    if subject_id is None:
        raise ValueError("evidence has no subject")
    mapped = conn.execute(
        """
        SELECT canonical_field_key FROM intelligence.predicate_registry
        WHERE registry_version = '0.2.0' AND predicate = %s AND enabled
        """,
        (predicate,),
    ).fetchone()
    if not mapped or mapped[0] != field_key:
        raise ValueError("predicate does not map to field_key")
    conn.execute(
        """
        UPDATE intelligence.canonical_selections
        SET superseded_at = now(), invalidation_reason = 'replaced by new selection'
        WHERE subject_entity_id = %s AND field_key = %s AND publication_class = %s
          AND superseded_at IS NULL
        """,
        (subject_id, field_key, publication_class),
    )
    new_id = uuid.uuid4()
    conn.execute(
        """
        INSERT INTO intelligence.canonical_selections(
          id, subject_entity_id, field_key, evidence_id, publication_class,
          selected_by, reason
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (new_id, subject_id, field_key, evidence_id, publication_class, actor, reason),
    )
    return new_id


def _transition(conn, *, evidence_id, to_status: str, actor: str, reason: str) -> None:
    current = conn.execute(
        "SELECT review_status FROM intelligence.evidence WHERE id = %s",
        (evidence_id,),
    ).fetchone()
    if current is None:
        raise ValueError("evidence not found")
    from_status = current[0]
    conn.execute(
        """
        INSERT INTO intelligence.evidence_review_events(
          id, evidence_id, from_status, to_status, actor, reason
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (uuid.uuid4(), evidence_id, from_status, to_status, actor, reason),
    )
    conn.execute(
        """
        UPDATE intelligence.evidence
        SET review_status = %s, reviewed_by = %s, reviewed_at = now()
        WHERE id = %s
        """,
        (to_status, actor, evidence_id),
    )


def _invalidate_if_selected(conn, *, evidence_id, reason: str) -> None:
    conn.execute(
        """
        UPDATE intelligence.canonical_selections
        SET superseded_at = now(), invalidation_reason = %s
        WHERE evidence_id = %s AND superseded_at IS NULL
        """,
        (reason, evidence_id),
    )
