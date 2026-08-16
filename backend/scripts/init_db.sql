-- QuantPilot init DDL (subset). See docs for full spec.
CREATE TABLE users (
  id            TEXT PRIMARY KEY,
  email         TEXT UNIQUE NOT NULL,
  pw_hash       TEXT NOT NULL,
  totp_secret   TEXT,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE google_accounts (
  user_id            TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  google_sub         TEXT UNIQUE NOT NULL,
  google_email       TEXT,
  scopes             TEXT NOT NULL,
  enc_refresh_token  BLOB NOT NULL,
  linked_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_used_at       TIMESTAMP
);

CREATE TABLE audit_logs (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id      TEXT REFERENCES users(id),
  endpoint     TEXT NOT NULL,
  status       INT  NOT NULL,
  duration_ms  INT DEFAULT 0,
  ip           TEXT DEFAULT '',
  payload_hash TEXT DEFAULT '',
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE strategies (
  id            TEXT PRIMARY KEY,
  user_id       TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  description   TEXT,
  current_ref   TEXT,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, name)
);

CREATE TABLE commits (
  sha           TEXT PRIMARY KEY,
  strategy_id   TEXT NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
  parent_sha    TEXT REFERENCES commits(sha),
  merge_parent  TEXT REFERENCES commits(sha),
  author_id     TEXT NOT NULL REFERENCES users(id),
  message       TEXT NOT NULL,
  tree_hash     TEXT NOT NULL,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE commit_files (
  commit_sha    TEXT NOT NULL REFERENCES commits(sha) ON DELETE CASCADE,
  path          TEXT NOT NULL,
  blob_sha      TEXT NOT NULL,
  content       TEXT NOT NULL,
  PRIMARY KEY (commit_sha, path)
);

CREATE TABLE branches (
  strategy_id   TEXT NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  head_sha      TEXT NOT NULL REFERENCES commits(sha),
  protected     BOOLEAN DEFAULT 0,
  updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (strategy_id, name)
);

CREATE TABLE tags (
  strategy_id   TEXT NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  target_sha    TEXT NOT NULL REFERENCES commits(sha),
  message       TEXT,
  created_by    TEXT REFERENCES users(id),
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (strategy_id, name)
);

CREATE TABLE deployments (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  strategy_id   TEXT NOT NULL REFERENCES strategies(id),
  environment   TEXT NOT NULL CHECK (environment IN ('paper','live')),
  commit_sha    TEXT NOT NULL REFERENCES commits(sha),
  deployed_by   TEXT NOT NULL REFERENCES users(id),
  deployed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  reverted_at   TIMESTAMP,
  reason        TEXT
);
