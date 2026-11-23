import hashlib
import os
import tempfile
import threading
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QComboBox, QMainWindow, QPushButton

from core import ForenseCore
from interface import AppEna
from persistence import PersistenceStore


class AppEnaInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database = Path(self.temporary_directory.name) / "ena.sqlite3"
        self.store = PersistenceStore(database)
        self.window = AppEna(core=ForenseCore(), store=self.store)

    def tearDown(self):
        self.window.close()
        self.temporary_directory.cleanup()

    def test_main_window_uses_qt_and_disables_evidence_actions_until_open(self):
        self.assertIsInstance(self.window, QMainWindow)
        self.assertIsInstance(self.window.combo_casos, QComboBox)
        self.assertIsInstance(self.window.btn_hash, QPushButton)
        self.assertFalse(self.window.btn_hash.isEnabled())
        self.assertFalse(self.window.btn_comparar_hash.isEnabled())
        self.assertFalse(self.window.btn_carving.isEnabled())

    def test_case_creation_and_selection_update_case_controls(self):
        case_id = self.store.create_case("Caso teste", "Operador teste")

        self.window._atualizar_casos(selecionar_id=case_id)
        self.assertEqual(self.window._case_id, case_id)
        self.assertTrue(self.window.btn_auditoria.isEnabled())

    def test_worker_returns_results_to_the_gui_thread(self):
        loop = QEventLoop()
        main_thread = threading.current_thread()
        result = []

        def finish(value):
            result.append((value, threading.current_thread()))
            self.window._definir_ocupado(False)
            loop.quit()

        self.window._definir_ocupado(True)
        self.window._start_worker(lambda: ("success", 42), finish)
        QTimer.singleShot(5000, loop.quit)
        loop.exec()

        self.assertEqual(result[0][0], ("success", 42))
        self.assertIs(result[0][1], main_thread)

    def test_hash_comparison_calculates_persists_and_audits_reference(self):
        image = Path(self.temporary_directory.name) / "evidencia.dd"
        image.write_bytes(b"conteudo de teste")
        case_id = self.store.create_case("Caso", "Operador")
        evidence_id = self.store.register_evidence(case_id, image, image.stat().st_size)
        self.window.core.img = object()
        self.window._definir_ocupado(False)

        self.assertTrue(self.window.btn_comparar_hash.isEnabled())
        success, result = self.window._executar_comparacao_hash(
            str(image), case_id, evidence_id,
            hashlib.sha256(image.read_bytes()).hexdigest(),
        )

        self.assertTrue(success, result)
        self.assertTrue(result["comparacao"]["matches"])
        self.assertEqual(result["comparacao"]["algorithm"], "sha256")
        events = self.store.list_events(case_id)
        self.assertEqual(events[-2]["action"], "hashes_calculated")
        self.assertEqual(events[-1]["action"], "hash_reference_compared")
        comparison_details = events[-1]["details"]
        self.assertEqual(comparison_details["parameters"]["algorithm"], "sha256")
        self.assertTrue(comparison_details["result"]["matches"])


if __name__ == "__main__":
    unittest.main()
