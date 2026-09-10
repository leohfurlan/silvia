CREATE TABLE projects(id TEXT PRIMARY KEY, root TEXT NOT NULL, git_common TEXT, identity TEXT, created_at TEXT NOT NULL);
CREATE TABLE locations(path TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id));
CREATE TABLE sessions(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), name TEXT NOT NULL,
 state TEXT NOT NULL, revision INTEGER NOT NULL, checkout TEXT NOT NULL, baseline TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, runner TEXT, heartbeat TEXT);
CREATE UNIQUE INDEX checkout_writer ON sessions(checkout) WHERE state NOT IN ('completed','cancelled','archived');
CREATE TABLE objectives(session_id TEXT NOT NULL REFERENCES sessions(id), revision INTEGER NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(session_id,revision));
CREATE TABLE events(event_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id), sequence INTEGER NOT NULL, data TEXT NOT NULL, UNIQUE(session_id,sequence));
CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'immutable-event'); END;
CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'immutable-event'); END;
CREATE TRIGGER objectives_no_update BEFORE UPDATE ON objectives BEGIN SELECT RAISE(ABORT,'immutable-objective'); END;
CREATE TRIGGER objectives_no_delete BEFORE DELETE ON objectives BEGIN SELECT RAISE(ABORT,'immutable-objective'); END;
CREATE TABLE records(kind TEXT NOT NULL, id TEXT NOT NULL, session_id TEXT REFERENCES sessions(id), revision INTEGER, data TEXT NOT NULL, PRIMARY KEY(kind,id));
CREATE INDEX records_session ON records(session_id,kind);
CREATE TABLE memory(id TEXT PRIMARY KEY, project_id TEXT, session_id TEXT, scope TEXT NOT NULL, status TEXT NOT NULL, content TEXT NOT NULL, data TEXT NOT NULL);
CREATE VIRTUAL TABLE memory_search USING fts5(id UNINDEXED, content);
CREATE TABLE sources(id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, path TEXT NOT NULL UNIQUE);
