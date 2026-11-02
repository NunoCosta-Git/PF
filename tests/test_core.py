import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

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

    def test_carving_extracts_jpeg_png_and_pdf_with_source_offsets(self):
        jpeg_buffer = io.BytesIO()
        Image.new("RGB", (32, 24), color="red").save(jpeg_buffer, format="JPEG")
        png_buffer = io.BytesIO()
        Image.new("RGB", (16, 16), color="blue").save(png_buffer, format="PNG")
        jpeg = jpeg_buffer.getvalue()
        png = png_buffer.getvalue()
        pdf = b"%PDF-1.4\n1 0 obj <<>> endobj\n%%EOF"

        # Coloca a assinatura JPEG junto do limite de 1 MiB para validar a sobreposição.
        prefixo = b"X" * (1024 * 1024 - 2)
        dados = prefixo + jpeg + b"\x00\x00" + png + b"\x00\x00" + pdf
        with tempfile.TemporaryDirectory() as pasta:
            imagem = Path(pasta) / "evidencia.dd"
            saida = Path(pasta) / "carved"
            imagem.write_bytes(dados)
            core = ForenseCore()
            try:
                sucesso, mensagem = core.abrir_imagem(str(imagem))
                self.assertTrue(sucesso, mensagem)
                sucesso, recuperados = core.fazer_carving(str(saida))
                self.assertTrue(sucesso, recuperados)
                self.assertEqual([item["tipo"] for item in recuperados], ["JPEG", "PNG", "PDF"])
                self.assertEqual(
                    [item["offset"] for item in recuperados],
                    [len(prefixo), len(prefixo) + len(jpeg) + 2,
                     len(prefixo) + len(jpeg) + len(png) + 4],
                )
                self.assertEqual(Path(recuperados[0]["caminho"]).read_bytes(), jpeg)
                self.assertEqual(Path(recuperados[1]["caminho"]).read_bytes(), png)
                self.assertEqual(Path(recuperados[2]["caminho"]).read_bytes(), pdf)
            finally:
                core.fechar()

    def test_carving_requires_an_open_image(self):
        sucesso, mensagem = ForenseCore().fazer_carving()

        self.assertFalse(sucesso)
        self.assertIn("Abra uma imagem", mensagem)

    def test_exif_extracts_camera_make_and_model(self):
        exif = Image.Exif()
        exif[271] = "ENA Test Maker"
        exif[272] = "Laboratory Camera"
        with tempfile.TemporaryDirectory() as pasta:
            imagem = Path(pasta) / "com_exif.jpg"
            Image.new("RGB", (10, 10), color="green").save(imagem, exif=exif)

            sucesso, resultado = ForenseCore().extrair_exif(str(imagem))

        self.assertTrue(sucesso, resultado)
        self.assertEqual(resultado["Fabricante"], "ENA Test Maker")
        self.assertEqual(resultado["Modelo"], "Laboratory Camera")

    def test_pdf_report_is_created(self):
        with tempfile.TemporaryDirectory() as pasta:
            imagem = Path(pasta) / "evidencia.dd"
            imagem.write_bytes(b"not a filesystem")
            destino = Path(pasta) / "relatorio.pdf"
            core = ForenseCore()
            try:
                sucesso, mensagem = core.abrir_imagem(str(imagem))
                self.assertTrue(sucesso, mensagem)
                hash_ok, hashes = core.calcular_hash()
                self.assertTrue(hash_ok, hashes)
                sucesso, mensagem = core.gerar_relatorio_pdf(
                    str(destino), hashes=hashes, recuperados=[]
                )
            finally:
                core.fechar()

            self.assertTrue(sucesso, mensagem)
            self.assertTrue(destino.is_file())
            self.assertTrue(destino.read_bytes().startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
