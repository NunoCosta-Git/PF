import hashlib
import os

import pytsk3

try:
    import pyewf
except ImportError:
    pyewf = None


CHUNK_SIZE = 1024 * 1024


class EWFImgInfo(pytsk3.Img_Info):
    """Adaptador read-only para disponibilizar segmentos E01 ao pytsk3."""

    def __init__(self, ewf_handle):
        self._ewf_handle = ewf_handle
        super().__init__(url="", type=pytsk3.TSK_IMG_TYPE_EXTERNAL)

    def close(self):
        self._ewf_handle.close()

    def read(self, offset, size):
        self._ewf_handle.seek(offset)
        return self._ewf_handle.read(size)

    def get_size(self):
        obter_tamanho = getattr(self._ewf_handle, "get_media_size", None)
        if callable(obter_tamanho):
            return obter_tamanho()
        tamanho = self._ewf_handle.media_size
        return tamanho() if callable(tamanho) else tamanho


class ForenseCore:
    """Operações de leitura e verificação de imagens de evidência."""

    def __init__(self):
        self.img = None
        self.fs = None
        self.caminho_imagem = None
        self.tamanho_imagem = 0
        self.particoes = []
        self.sistema_ficheiros = None

    def abrir_imagem(self, caminho_imagem):
        """Abre uma imagem sem escrita e tenta localizar um sistema de ficheiros."""
        self.fechar()
        caminho_imagem = os.path.abspath(caminho_imagem)

        if not os.path.isfile(caminho_imagem):
            return False, "O ficheiro de imagem não existe ou não é um ficheiro regular."

        try:
            if caminho_imagem.lower().endswith((".e01", ".ex01")):
                if pyewf is None:
                    return False, (
                        "Suporte E01 indisponível: instale pyewf ou use uma imagem RAW "
                        "(.dd/.raw)."
                    )
                ewf_handle = pyewf.handle()
                ewf_handle.open(pyewf.glob(caminho_imagem))
                self.img = EWFImgInfo(ewf_handle)
                self.tamanho_imagem = self.img.get_size()
            else:
                self.img = pytsk3.Img_Info(caminho_imagem)
                self.tamanho_imagem = os.path.getsize(caminho_imagem)

            self.caminho_imagem = caminho_imagem

            try:
                self.fs = pytsk3.FS_Info(self.img)
                self.sistema_ficheiros = "Sistema de ficheiros na imagem"
                return True, "Imagem aberta em modo de leitura; sistema de ficheiros reconhecido."
            except Exception:
                pass

            self._detetar_particoes()
            if self.fs:
                return True, (
                    "Imagem aberta em modo de leitura; foi reconhecido um sistema de "
                    "ficheiros numa partição."
                )

            return True, (
                "Imagem aberta em modo de leitura. Não foi possível identificar um "
                "sistema de ficheiros; o cálculo de hash continua disponível."
            )
        except Exception as exc:
            self.fechar()
            return False, f"Não foi possível abrir a imagem: {exc}"

    def _detetar_particoes(self):
        """Procura partições e abre o primeiro sistema de ficheiros reconhecido."""
        try:
            volume = pytsk3.Volume_Info(self.img)
            tamanho_bloco = volume.info.block_size
            for particao in volume:
                descricao = particao.desc
                if isinstance(descricao, bytes):
                    descricao = descricao.decode("utf-8", errors="replace")

                registo = {
                    "numero": particao.addr,
                    "inicio_bytes": particao.start * tamanho_bloco,
                    "tamanho_bytes": particao.len * tamanho_bloco,
                    "descricao": str(descricao).strip(),
                    "sistema_ficheiros": None,
                }
                self.particoes.append(registo)

                try:
                    sistema_ficheiros = pytsk3.FS_Info(
                        self.img, offset=registo["inicio_bytes"]
                    )
                except Exception:
                    continue

                registo["sistema_ficheiros"] = "Reconhecido"
                if self.fs is None:
                    self.fs = sistema_ficheiros
                    self.sistema_ficheiros = "Reconhecido numa partição"
        except Exception:
            # Imagens sem tabela de partições continuam válidas para hashing.
            return

    def calcular_hash(self, caminho_imagem=None):
        """Calcula MD5 e SHA-256 em streaming sobre o conteúdo da evidência."""
        caminho_imagem = os.path.abspath(caminho_imagem or self.caminho_imagem or "")
        if not os.path.isfile(caminho_imagem):
            return False, "Selecione um ficheiro de imagem válido antes de calcular o hash."

        md5_hash = hashlib.md5()
        sha256_hash = hashlib.sha256()
        try:
            if caminho_imagem.lower().endswith((".e01", ".ex01")):
                if pyewf is None:
                    return False, "Não é possível calcular o hash E01 sem o pacote pyewf."
                handle = pyewf.handle()
                try:
                    handle.open(pyewf.glob(caminho_imagem))
                    for bloco in iter(lambda: handle.read(CHUNK_SIZE), b""):
                        md5_hash.update(bloco)
                        sha256_hash.update(bloco)
                finally:
                    handle.close()
            else:
                with open(caminho_imagem, "rb") as ficheiro:
                    for bloco in iter(lambda: ficheiro.read(CHUNK_SIZE), b""):
                        md5_hash.update(bloco)
                        sha256_hash.update(bloco)

            return True, {
                "md5": md5_hash.hexdigest(),
                "sha256": sha256_hash.hexdigest(),
            }
        except Exception as exc:
            return False, f"Erro ao calcular os hashes: {exc}"

    def listar_diretorio(self, caminho="/"):
        """Lista entradas do sistema de ficheiros atualmente reconhecido."""
        if not self.img:
            return False, "Nenhuma imagem carregada."
        if not self.fs:
            return False, "A imagem está carregada, mas não tem um sistema de ficheiros reconhecido."

        try:
            ficheiros = []
            diretorio = self.fs.open_dir(path=caminho)
            for entrada in diretorio:
                if not entrada.info.meta or not entrada.info.name.name:
                    continue
                nome = entrada.info.name.name.decode("utf-8", errors="replace")
                if nome in (".", ".."):
                    continue
                ficheiros.append({
                    "nome": nome,
                    "tamanho": entrada.info.meta.size,
                    "diretorio": entrada.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR,
                    "eliminado": bool(
                        entrada.info.meta.flags & pytsk3.TSK_FS_META_FLAG_UNALLOC
                    ),
                })
            return True, ficheiros
        except Exception as exc:
            return False, f"Erro ao listar o diretório: {exc}"

    def fechar(self):
        """Liberta handles sem alterar os ficheiros de evidência."""
        if self.img is not None:
            try:
                self.img.close()
            except Exception:
                pass
        self.img = None
        self.fs = None
        self.caminho_imagem = None
        self.tamanho_imagem = 0
        self.particoes = []
        self.sistema_ficheiros = None