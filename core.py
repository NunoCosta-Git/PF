import pytsk3
import hashlib
import os

class ForenseCore:
    def __init__(self):
        self.img = None
        self.fs = None

    def abrir_imagem(self, caminho_imagem):
        """Abre a imagem forense em modo read-only"""
        try:
            # pytsk3 abre a imagem. O modo read-only é implícito nesta biblioteca.
            self.img = pytsk3.Img_Info(caminho_imagem)
            # Tenta ler o sistema de ficheiros (NTFS, FAT, Ext4, etc)
            self.fs = pytsk3.FS_Info(self.img)
            return True, "Imagem carregada com sucesso."
        except Exception as e:
            return False, f"Erro ao abrir imagem: {str(e)}"

    def calcular_hash(self, caminho_imagem):
        """Calcula o hash SHA-256 em blocos para não sobrecarregar a RAM"""
        sha256_hash = hashlib.sha256()
        try:
            with open(caminho_imagem, "rb") as f:
                # Lê em blocos de 64KB
                for byte_block in iter(lambda: f.read(65536), b""):
                    sha256_hash.update(byte_block)
            return True, sha256_hash.hexdigest()
        except Exception as e:
            return False, f"Erro no hashing: {str(e)}"

    def listar_diretorio(self, caminho="/"):
        """Navega pela imagem forense e lista os ficheiros"""
        ficheiros = []
        if not self.fs:
            return False, "Nenhuma imagem carregada."
        
        try:
            diretorio = self.fs.open_dir(path=caminho)
            for entrada in diretorio:
                # Filtra entradas inválidas e ficheiros de sistema
                if entrada.info.meta and entrada.info.name.name:
                    nome = entrada.info.name.name.decode('utf-8', errors='ignore')
                    if nome not in ['.', '..']:
                        tamanho = entrada.info.meta.size
                        ficheiros.append({"nome": nome, "tamanho": tamanho})
            return True, ficheiros
        except Exception as e:
            return False, f"Erro ao listar: {str(e)}"

# Teste rápido (podes correr este ficheiro diretamente para testar)
if __name__ == "__main__":
    core = ForenseCore()
    # Substitui pelo caminho de uma imagem de teste .dd
    caminho_teste = "teste.dd" 
    print(core.abrir_imagem(caminho_teste))
    print(core.calcular_hash(caminho_teste))
    print(core.listar_diretorio("/"))