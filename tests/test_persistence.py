import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from persistence import PersistenceStore


class PersistenceStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "dados" / "casos.sqlite3"
        self.store = PersistenceStore(self.database)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_records_case_evidence_hashes_and_audit_events(self):
        image = Path(self.temporary_directory.name) / "evidencia.dd"
        image.write_bytes(b"evidencia")
        case_id = self.store.create_case("Caso de teste", "Analista")
        evidence_id = self.store.register_evidence(case_id, image, image.stat().st_size)
        md5 = "a" * 32
        sha256 = "b" * 64

        self.store.record_hashes(case_id, evidence_id, md5, sha256)
        self.store.record_event(
            case_id, evidence_id, "carving_completed", {"files_found": 2}
        )

        restarted_store = PersistenceStore(self.database)
        events = restarted_store.list_events(case_id)
        self.assertEqual(
            [event["action"] for event in events],
            ["case_created", "evidence_opened", "hashes_calculated", "carving_completed"],
        )
        self.assertTrue(all(event["operator"] == "Analista" for event in events))
        self.assertIsNotNone(datetime.fromisoformat(events[0]["occurred_at"]).utcoffset())
        self.assertEqual(events[2]["details"], {"md5": md5, "sha256": sha256})
        self.assertEqual(events[3]["details"], {"files_found": 2})
        self.assertEqual(restarted_store.list_cases()[0]["name"], "Caso de teste")

    def test_all_case_records_are_append_only(self):
        image = Path(self.temporary_directory.name) / "evidencia.dd"
        image.write_bytes(b"evidencia")
        case_id = self.store.create_case("Caso", "Analista")
        evidence_id = self.store.register_evidence(case_id, image, image.stat().st_size)
        self.store.record_hashes(case_id, evidence_id, "a" * 32, "b" * 64)
        event_id = self.store.list_events(case_id)[0]["id"]

        connection = sqlite3.connect(self.database)
        try:
            for statement in (
                "UPDATE cases SET name = 'alterado' WHERE id = ?",
                "DELETE FROM cases WHERE id = ?",
                "UPDATE evidences SET path = 'alterado' WHERE id = ?",
                "DELETE FROM evidences WHERE id = ?",
                "UPDATE hashes SET md5 = ? WHERE evidence_id = ?",
                "DELETE FROM hashes WHERE evidence_id = ?",
                "UPDATE audit_events SET action = 'alterado' WHERE id = ?",
                "DELETE FROM audit_events WHERE id = ?",
            ):
                parameters = (
                    ("alterado", evidence_id)
                    if statement.startswith("UPDATE hashes")
                    else (evidence_id,)
                    if "evidences" in statement or "hashes" in statement
                    else (event_id,)
                    if "audit_events" in statement
                    else (case_id,)
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(statement, parameters)
        finally:
            connection.close()

    def test_rejects_hashes_for_another_case_and_invalid_hash_values(self):
        case_id = self.store.create_case("Caso", "Analista")
        other_case_id = self.store.create_case("Outro caso", "Analista")
        image = Path(self.temporary_directory.name) / "evidencia.dd"
        image.write_bytes(b"evidencia")
        evidence_id = self.store.register_evidence(
            case_id, image, image.stat().st_size
        )

        with self.assertRaisesRegex(ValueError, "não pertence"):
            self.store.record_hashes(other_case_id, evidence_id, "a" * 32, "b" * 64)
        with self.assertRaisesRegex(ValueError, "MD5"):
            self.store.record_hashes(case_id, evidence_id, "invalid", "b" * 64)

    def test_event_details_are_valid_json_and_records_are_ordered(self):
        case_id = self.store.create_case("Caso", "Analista")
        event_id = self.store.record_event(case_id, None, "note_added", {"texto": "ação"})

        event = self.store.list_events(case_id)[1]
        self.assertEqual(event["id"], event_id)
        self.assertEqual(event["details"], {"texto": "ação"})
        self.assertEqual(json.loads(event["details_json"]), {"texto": "ação"})


if __name__ == "__main__":
    unittest.main()
