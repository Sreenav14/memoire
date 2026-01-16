BEGIN;

-- 1. Create a dev user
INSERT INTO users (first_name, last_name, email, email_verified)
VALUES ('Dev','User', 'dev@memoire.local', true)
ON CONFLICT DO NOTHING;

-- 2. Add a placeholder password hash (API will replace later with bycrypt/argon2)
-- NOTE: this is not a real hash, it is just a placeholder
INSERT INTO user_passwords (user_id, password_hash)
SELECT id, 'DEV_ONLY_PLACEHOLDER_HASH'
FROM users
WHERE email = 'dev@memoire.local'
ON CONFLICT (user_id) DO NOTHING;

-- 3. Create a default space owned by the dev user
INSERT INTO spaces (name, owner_user_id)
SELECT 'Dev Space', id
FROM users 
WHERE email = 'dev@memoire.local'
ON CONFLICT DO NOTHING;

-- 4. Add membership now
INSERT INTO user_spaces (user_id, space_id, role)
SELECT u.id, s.id, 'owner'
FROM users u
JOIN spaces s ON s.owner_user_id = u.id
WHERE u.email = 'dev@memoire.local'
ON CONFLICT do nothing;

commit;