import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
from core import ForenseCore # Importa a classe que criámos acima

# Configuração visual
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AppEna(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("E.N.A - Ferramenta de Análise Forense")
        self.geometry("800x600")
        self.core = ForenseCore()
        self.caminho_imagem = ""

        # --- Elementos da UI ---
        self.label_titulo = ctk.CTkLabel(self, text="E.N.A - Análise Forense", font=("Roboto", 24, "bold"))
        self.label_titulo.pack(pady=20)

        # Botão para selecionar imagem
        self.btn_selecionar = ctk.CTkButton(self, text="Selecionar Imagem (.dd / .raw)", command=self.selecionar_imagem)
        self.btn_selecionar.pack(pady=10)

        # Botão de Hash
        self.btn_hash = ctk.CTkButton(self, text="Verificar Integridade (SHA-256)", command=self.iniciar_hash_thread, state="disabled")
        self.btn_hash.pack(pady=10)

        # Caixa de texto para mostrar logs/resultados
        self.txt_log = ctk.CTkTextbox(self, width=700, height=300)
        self.txt_log.pack(pady=20)

    def selecionar_imagem(self):
        caminho = filedialog.askopenfilename(title="Selecione a imagem forense", filetypes=[("Imagens Forenses", "*.dd *.raw *.E01")])
        if caminho:
            self.caminho_imagem = caminho
            self.log(f"Imagem selecionada: {caminho}")
            
            # Tenta abrir a imagem
            sucesso, msg = self.core.abrir_imagem(caminho)
            self.log(msg)
            
            if sucesso:
                self.btn_hash.configure(state="normal")
                # Lista os ficheiros da raiz
                sucesso_lista, ficheiros = self.core.listar_diretorio("/")
                if sucesso_lista:
                    self.log(f"Ficheiros encontrados na raiz: {len(ficheiros)}")
                    for f in ficheiros[:5]: # Mostra apenas os primeiros 5 para não encher
                        self.log(f" - {f['nome']} ({f['tamanho']} bytes)")

    def iniciar_hash_thread(self):
        """Inicia o hashing numa thread separada para a UI não bloquear"""
        self.btn_hash.configure(state="disabled", text="A calcular...")
        self.log("A calcular hash SHA-256... (isto pode demorar)")
        # Cria uma thread para correr o hash
        thread = threading.Thread(target=self.executar_hash)
        thread.start()

    def executar_hash(self):
        sucesso, resultado = self.core.calcular_hash(self.caminho_imagem)
        if sucesso:
            self.log(f"HASH SHA-256: {resultado}")
        else:
            self.log(resultado)
        
        # Reativa o botão na thread principal (thread-safe)
        self.after(0, lambda: self.btn_hash.configure(state="normal", text="Verificar Integridade (SHA-256)"))

    def log(self, mensagem):
        """Adiciona texto à caixa de logs"""
        self.txt_log.insert("end", mensagem + "\n")
        self.txt_log.see("end")

if __name__ == "__main__":
    app = AppEna()
    app.mainloop()