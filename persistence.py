import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parent / "dados" / "ena.sqlite3"
HASH_PATTERNS = {
    "md5": re.compile(r"^[0-9a-f]{32}$"),
    "sha256": re.compile(r"^[0-9a-f]{64}$"),
}


class PersistenceStore:
    """Persistência local de casos, evidências, hashes e eventos imutáveis."""

    def __init__(self, database_path=DATABASE_PATH):
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self):
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidences (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL REFERENCES cases(id),
                    path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                    registered_at TEXT NOT NULL,
                    UNIQUE (case_id, id)
                );
                CREATE TABLE IF NOT EXISTS hashes (
                    id TEXT PRIMARY KEY,
                    evidence_id TEXT NOT NULL REFERENCES evidences(id),
                    md5 TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    calculated_at TEXT NOT NULL,
                    CHECK (length(md5) = 32),
                    CHECK (length(sha256) = 64)
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL REFERENCES cases(id),
                    evidence_id TEXT,
                    operator TEXT NOT NULL,
                    action TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    FOREIGN KEY (case_id, evidence_id) REFERENCES evidences(case_id, id)
                );
                CREATE INDEX IF NOT EXISTS audit_events_case_time
                    ON audit_events(case_id, occurred_at);
                """
            )
            for table in ("cases", "evidences", "hashes", "audit_events"):
                connection.executescript(
                    f"""
                    CREATE TRIGGER IF NOT EXISTS {table}_no_update
                    BEFORE UPDATE ON {table}
                    BEGIN
                        SELECT RAISE(ABORT, 'registos imutaveis');
                    END;
                    CREATE TRIGGER IF NOT EXISTS {table}_no_delete
                    BEFORE DELETE ON {table}
                    BEGIN
                        SELECT RAISE(ABORT, 'registos imutaveis');
                    END;
                    """
                )

    @staticmethod
    def _timestamp():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _event_values(case_id, evidence_id, operator, action, details, occurred_at):
        if not operator or not operator.strip():
            raise ValueError("O operador do evento é obrigatório.")
        if not action or not action.strip():
            raise ValueError("A ação do evento é obrigatória.")
        return (
            str(uuid.uuid4()),
            case_id,
            evidence_id,
            operator.strip(),
            action.strip(),
            occurred_at,
            json.dumps(details or {}, ensure_ascii=False, sort_keys=True),
        )

    def create_case(self, name, operator):
        name = name.strip() if name else ""
        operator = operator.strip() if operator else ""
        if not name:
            raise ValueError("O nome do caso é obrigatório.")
        if not operator:
            raise ValueError("O operador é obrigatório.")

        case_id = str(uuid.uuid4())
        created_at = self._timestamp()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO cases (id, name, operator, created_at) VALUES (?, ?, ?, ?)",
                (case_id, name, operator, created_at),
            )
            connection.execute(
                """
                INSERT INTO audit_events
                    (id, case_id, evidence_id, operator, action, occurred_at, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                self._event_values(
                    case_id, None, operator, "case_created", {"name": name}, created_at
                ),
            )
        return case_id

    def list_cases(self):
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, name, operator, created_at FROM cases ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def register_evidence(self, case_id, path, size_bytes):
        evidence_id = str(uuid.uuid4())
        registered_at = self._timestamp()
        evidence_path = str(Path(path).resolve())
        with self._connect() as connection:
            case = connection.execute(
                "SELECT operator FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
            if case is None:
                raise ValueError("O caso selecionado não existe.")
            connection.execute(
                """
                INSERT INTO evidences (id, case_id, path, size_bytes, registered_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (evidence_id, case_id, evidence_path, size_bytes, registered_at),
            )
            connection.execute(
                """
                INSERT INTO audit_events
                    (id, case_id, evidence_id, operator, action, occurred_at, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                self._event_values(
                    case_id,
                    evidence_id,
                    case["operator"],
                    "evidence_opened",
                    {"path": evidence_path, "size_bytes": size_bytes},
                    registered_at,
                ),
            )
        return evidence_id

    def record_event(self, case_id, evidence_id, action, details=None):
        occurred_at = self._timestamp()
        with self._connect() as connection:
            case = connection.execute(
                "SELECT operator FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
            if case is None:
                raise ValueError("O caso selecionado não existe.")
            if evidence_id is not None:
                evidence = connection.execute(
                    "SELECT case_id FROM evidences WHERE id = ?", (evidence_id,)
                ).fetchone()
                if evidence is None or evidence["case_id"] != case_id:
                    raise ValueError("A evidência não pertence ao caso selecionado.")
            event = self._event_values(
                case_id, evidence_id, case["operator"], action, details, occurred_at
            )
            connection.execute(
                """
                INSERT INTO audit_events
                    (id, case_id, evidence_id, operator, action, occurred_at, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                event,
            )
        return event[0]

    def record_hashes(self, case_id, evidence_id, md5, sha256):
        if not HASH_PATTERNS["md5"].fullmatch(md5 or ""):
            raise ValueError("O MD5 tem de conter 32 caracteres hexadecimais.")
        if not HASH_PATTERNS["sha256"].fullmatch(sha256 or ""):
            raise ValueError("O SHA-256 tem de conter 64 caracteres hexadecimais.")

        calculated_at = self._timestamp()
        with self._connect() as connection:
            evidence = connection.execute(
                """
                SELECT e.case_id, c.operator
                FROM evidences e JOIN cases c ON c.id = e.case_id
                WHERE e.id = ?
                """,
                (evidence_id,),
            ).fetchone()
            if evidence is None or evidence["case_id"] != case_id:
                raise ValueError("A evidência não pertence ao caso selecionado.")

            connection.execute(
                """
                INSERT INTO hashes (id, evidence_id, md5, sha256, calculated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), evidence_id, md5, sha256, calculated_at),
            )
            connection.execute(
                """
                INSERT INTO audit_events
                    (id, case_id, evidence_id, operator, action, occurred_at, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                self._event_values(
                    case_id,
                    evidence_id,
                    evidence["operator"],
                    "hashes_calculated",
                    {"md5": md5, "sha256": sha256},
                    calculated_at,
                ),
            )

    def list_events(self, case_id):
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, case_id, evidence_id, operator, action, occurred_at, details_json
                FROM audit_events
                WHERE case_id = ?
                ORDER BY occurred_at, rowid
                """,
                (case_id,),
            ).fetchall()
        return [
            {**dict(row), "details": json.loads(row["details_json"])}
            for row in rows
        ]
