-- Memoire: Development seed data
-- Run AFTER all 001-006 migrations

BEGIN;

-- ── Dev user ──

INSERT INTO users (first_name, last_name, email, email_verified)
VALUES ('Dev', 'User', 'dev@memoire.local', true)
ON CONFLICT (email) DO NOTHING;

INSERT INTO user_passwords (user_id, password_hash)
SELECT id, 'DEV_ONLY_PLACEHOLDER_HASH'
FROM users
WHERE email = 'dev@memoire.local'
ON CONFLICT (user_id) DO NOTHING;

-- ── Dev space ──

INSERT INTO spaces (name, owner_user_id)
SELECT 'Dev Space', id
FROM users
WHERE email = 'dev@memoire.local'
  AND NOT EXISTS (
      SELECT 1 FROM spaces
      WHERE name = 'Dev Space'
        AND owner_user_id = (SELECT id FROM users WHERE email = 'dev@memoire.local')
  );

INSERT INTO user_spaces (user_id, space_id, role)
SELECT u.id, s.id, 'owner'
FROM users u
JOIN spaces s ON s.owner_user_id = u.id
WHERE u.email = 'dev@memoire.local'
ON CONFLICT (user_id, space_id) DO NOTHING;

-- ── Example inference rules (uses the dev space) ──

INSERT INTO inference_rules(space_id, name, rule_json, is_enabled)
SELECT s.id, 'employment_location',
    '{
      "version": 1,
      "pattern": [
        {"from": "A", "rel": "works_at", "to": "B"},
        {"from": "B", "rel": "located_in", "to": "C"}
      ],
      "infer": {"from": "A", "rel": "works_in", "to": "C"},
      "confidence": 0.55
    }'::jsonb,
    true
FROM spaces s
JOIN users u ON u.id = s.owner_user_id
WHERE u.email = 'dev@memoire.local'
  AND s.name = 'Dev Space'
ON CONFLICT (space_id, name) DO NOTHING;

INSERT INTO inference_rules(space_id, name, rule_json, is_enabled)
SELECT s.id, 'residence_country',
    '{
      "version": 1,
      "pattern": [
        {"from": "A", "rel": "lives_in", "to": "B"},
        {"from": "B", "rel": "located_in", "to": "C"}
      ],
      "infer": {"from": "A", "rel": "lives_in", "to": "C"},
      "confidence": 0.55
    }'::jsonb,
    true
FROM spaces s
JOIN users u ON u.id = s.owner_user_id
WHERE u.email = 'dev@memoire.local'
  AND s.name = 'Dev Space'
ON CONFLICT (space_id, name) DO NOTHING;

COMMIT;
