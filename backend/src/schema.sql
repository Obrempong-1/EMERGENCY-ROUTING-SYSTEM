CREATE TABLE IF NOT EXISTS students (
  id              BIGSERIAL PRIMARY KEY,
  email           TEXT UNIQUE NOT NULL,
  trust           REAL NOT NULL DEFAULT 0.25,
  role            TEXT NOT NULL DEFAULT 'student',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  knust_verified  BOOLEAN NOT NULL DEFAULT false,
  auth_user_id    UUID,
  CONSTRAINT trust_range CHECK (trust >= 0 AND trust <= 1),
  CONSTRAINT known_role CHECK (role IN ('student', 'security', 'mapper', 'admin'))
);

CREATE UNIQUE INDEX IF NOT EXISTS students_auth_user_id_key
  ON students (auth_user_id) WHERE auth_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS students_role ON students (role) WHERE role <> 'student';

ALTER TABLE students DROP CONSTRAINT IF EXISTS known_role;
ALTER TABLE students ADD CONSTRAINT known_role
  CHECK (role IN ('student', 'security', 'mapper', 'admin'));

ALTER TABLE students ADD COLUMN IF NOT EXISTS roles TEXT[];
UPDATE students SET roles = ARRAY[role]::text[] WHERE roles IS NULL;
ALTER TABLE students ALTER COLUMN roles SET DEFAULT ARRAY['student']::text[];
ALTER TABLE students ALTER COLUMN roles SET NOT NULL;

ALTER TABLE students DROP CONSTRAINT IF EXISTS known_roles;
ALTER TABLE students ADD CONSTRAINT known_roles CHECK (
  roles <@ ARRAY['student', 'security', 'mapper', 'admin']::text[]
  AND array_length(roles, 1) >= 1
);

CREATE TABLE IF NOT EXISTS incident_clusters (
  id           BIGSERIAL PRIMARY KEY,
  kind         TEXT NOT NULL,
  lat          DOUBLE PRECISION NOT NULL,
  lon          DOUBLE PRECISION NOT NULL,
  expires_at   TIMESTAMPTZ NOT NULL,
  resolved_at  TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  override     TEXT,
  CONSTRAINT incident_override_known
    CHECK (override IS NULL OR override IN ('verified', 'false'))
);

CREATE INDEX IF NOT EXISTS incident_clusters_live
  ON incident_clusters (expires_at, resolved_at);

CREATE INDEX IF NOT EXISTS incident_clusters_by_kind
  ON incident_clusters (kind, expires_at);

CREATE TABLE IF NOT EXISTS incident_reports (
  id          BIGSERIAL PRIMARY KEY,
  cluster_id  BIGINT NOT NULL REFERENCES incident_clusters(id) ON DELETE CASCADE,
  student_id  BIGINT NOT NULL REFERENCES students(id),
  lat         DOUBLE PRECISION NOT NULL,
  lon         DOUBLE PRECISION NOT NULL,
  note        TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (cluster_id, student_id)
);

CREATE INDEX IF NOT EXISTS incident_reports_by_student
  ON incident_reports (student_id, created_at DESC);

CREATE TABLE IF NOT EXISTS curated_places (
  id             TEXT PRIMARY KEY,
  name           TEXT NOT NULL,
  category       TEXT NOT NULL,
  type           TEXT,
  lat            DOUBLE PRECISION NOT NULL,
  lon            DOUBLE PRECISION NOT NULL,
  phone          TEXT,
  opening_hours  TEXT,
  description    TEXT,
  created_by     BIGINT REFERENCES students(id),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
