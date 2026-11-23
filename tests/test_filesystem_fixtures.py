"""Testes de integração opcionais com imagens-fixture de sistemas de ficheiros.

Configurar ENA_FS_FIXTURE_MANIFEST para um JSON externo com imagens de laboratório.
O manifesto e os formatos esperados estão documentados em docs/testes-windows.md.
"""

import hashlib
import json
import os
import unittest
from pathlib import Path

import pytsk3

from core import ForenseCore


EXPECTED_FS_TYPES = {
    "NTFS": "TSK_FS_TYPE_NTFS",
    "FAT32": "TSK_FS_TYPE_FAT32",
    "EXT4": "TSK_FS_TYPE_EXT4",
}
CHUNK_SIZE = 1024 * 1024


def _sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


class FilesystemFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest_path = os.environ.get("ENA_FS_FIXTURE_MANIFEST")
        if not manifest_path:
            raise unittest.SkipTest(
                "Define ENA_FS_FIXTURE_MANIFEST para executar testes de integração FS."
            )

        cls.manifest_path = Path(manifest_path).resolve()
        if not cls.manifest_path.is_file():
            raise AssertionError(f"Manifesto de fixtures não encontrado: {cls.manifest_path}")
        try:
            cls.manifest = json.loads(cls.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AssertionError(f"Não foi possível ler o manifesto de fixtures: {exc}") from exc

        fixtures = cls.manifest.get("fixtures")
        if not isinstance(fixtures, list) or not fixtures:
            raise AssertionError("O manifesto tem de incluir uma lista 'fixtures' não vazia.")
        for fixture in fixtures:
            cls._validate_fixture(fixture)

    @staticmethod
    def _validate_fixture(fixture):
        if not isinstance(fixture, dict):
            raise AssertionError("Cada fixture tem de ser um objeto JSON.")
        for required in ("name", "image", "filesystem", "directories"):
            if required not in fixture:
                raise AssertionError(f"Fixture sem campo obrigatório: {required}.")
        if fixture["filesystem"] not in EXPECTED_FS_TYPES:
            raise AssertionError(
                f"Sistema de ficheiros não suportado no manifesto: {fixture['filesystem']}"
            )
        if not isinstance(fixture["directories"], dict) or not fixture["directories"]:
            raise AssertionError("Cada fixture tem de declarar diretórios e entradas esperadas.")

    def test_reference_filesystems_are_detected_and_listed_read_only(self):
        for fixture in self.manifest["fixtures"]:
            with self.subTest(fixture=fixture["name"]):
                image_path = (self.manifest_path.parent / fixture["image"]).resolve()
                self.assertTrue(image_path.is_file(), f"Imagem-fixture inexistente: {image_path}")
                source_hash_before = _sha256_file(image_path)
                core = ForenseCore()
                try:
                    opened, message = core.abrir_imagem(str(image_path))
                    self.assertTrue(opened, message)
                    self.assertIsNotNone(core.fs, message)

                    expected_type = int(
                        getattr(pytsk3, EXPECTED_FS_TYPES[fixture["filesystem"]])
                    )
                    actual_type = int(core.fs.info.ftype)
                    self.assertTrue(
                        actual_type & expected_type,
                        f"Esperado {fixture['filesystem']} ({expected_type}); "
                        f"pytsk3 reportou ftype={actual_type}.",
                    )

                    for directory_path, expected_entries in fixture["directories"].items():
                        with self.subTest(directory=directory_path):
                            listed, entries_or_error = core.listar_diretorio(directory_path)
                            self.assertTrue(listed, entries_or_error)
                            actual_entries = {
                                entry["nome"]: entry for entry in entries_or_error
                            }
                            expected_by_name = {
                                entry["name"]: entry for entry in expected_entries
                            }
                            self.assertEqual(
                                set(actual_entries),
                                set(expected_by_name),
                                f"Entradas inesperadas em {directory_path}",
                            )
                            for name, expected in expected_by_name.items():
                                actual = actual_entries[name]
                                self.assertEqual(
                                    actual["diretorio"], expected["directory"], name
                                )
                                self.assertEqual(actual["eliminado"], expected["deleted"], name)
                                if not expected["directory"]:
                                    self.assertEqual(actual["tamanho"], expected["size_bytes"], name)
                finally:
                    core.fechar()

                self.assertEqual(
                    _sha256_file(image_path),
                    source_hash_before,
                    "A imagem-fixture foi alterada durante os testes.",
                )


if __name__ == "__main__":
    unittest.main()
