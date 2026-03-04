from __future__ import annotations

import json
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger("memoire.worker.rules")


def store_rules(db: Session, space_id: str, rules: list[dict]) -> None:
    for rule in rules:
        name = rule.get("name")
        if not name:
            log.warning("Skipping rule with no name: %s", str(rule)[:200])
            continue

        db.execute(
            text(
                """
                INSERT INTO inference_rules(space_id, name, rule_json, is_enabled)
                VALUES(:space_id, :name, :rule::jsonb, false)
                ON CONFLICT(space_id, name)
                DO UPDATE SET
                    rule_json = EXCLUDED.rule_json,
                    updated_at = now();
                """
            ),
            {
                "space_id": space_id,
                "name": name,
                "rule": json.dumps(rule),
            },
        )

    db.commit()
