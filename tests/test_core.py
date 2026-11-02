import hashlib
import tempfile
import unittest
from pathlib import Path

from core import ForenseCore


class ForenseCoreTests(unittest.TestCase):
    def test_hash_calculates_md5_and_sha256_in_streams(self):
        dados = bytes(range(256)) * 4096
        with tempfile.TemporaryDirectory() as pasta:
            imagem = Path(pasta) / "amostra.dd"
            imagem.write_bytes(dados)

            sucesso, resultado = ForenseCore().calcular_hash(str(imagem))

        self.assertTrue(sucesso)
        self.assertEqual(resultado["md5"], hashlib.md5(dados).hexdigest())
        self.assertEqual(resultado["sha256"], hashlib.sha256(dados).hexdigest())

    def test_raw_image_without_recognized_filesystem_stays_open_for_hashing(self):
        with tempfile.TemporaryDirectory() as pasta:
            imagem = Path(pasta) / "sem_sistema_ficheiros.dd"
            imagem.write_bytes(b"ENA-raw-test-" * 8192)
            core = ForenseCore()
            try:
                sucesso, mensagem = core.abrir_imagem(str(imagem))
                self.assertTrue(sucesso, mensagem)
                self.assertIsNone(core.fs)
                self.assertTrue(core.calcular_hash()[0])
                self.assertFalse(core.listar_diretorio("/")[0])
            finally:
                core.fechar()

    def test_listing_without_an_open_image_returns_clear_error(self):
        sucesso, mensagem = ForenseCore().listar_diretorio("/")

        self.assertFalse(sucesso)
        self.assertIn("Nenhuma imagem", mensagem)


if __name__ == "__main__":
    unittest.main()
