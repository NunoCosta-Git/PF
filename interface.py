import os
import posixpath
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from core import ForenseCore


def _configurar_tcl_tk():
    """Localiza os scripts Tcl/Tk da instalação Python no Windows."""
    if os.name != "nt":
        return

    prefixos = (
        Path(sys.base_prefix) / "tcl",
        Path(sys.base_prefix) / "Library" / "lib",
    )
    bibliotecas = (
        ("TCL_LIBRARY", "tcl", "init.tcl"),
        ("TK_LIBRARY", "tk", "tk.tcl"),
    )

    for variavel, prefixo, ficheiro_necessario in bibliotecas:
        atual = os.environ.get(variavel)
        if atual and (Path(atual) / ficheiro_necessario).is_file():
            continue

        for raiz in prefixos:
            candidatos = [raiz, *raiz.glob(f"{prefixo}*")] if raiz.is_dir() else []
            biblioteca = next(
                (
                    candidato
                    for candidato in candidatos
                    if (candidato / ficheiro_necessario).is_file()
                ),
                None,
            )
            if biblioteca is not None:
                os.environ[variavel] = str(biblioteca)
                break


_configurar_tcl_tk()


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class AppEna(ctk.CTk):
    """Interface inicial da aplicação E.N.A."""

    def __init__(self):
        super().__init__()
        self.title("E.N.A. | Análise Forense Digital")
        self.geometry("1120x760")
        self.minsize(900, 620)

        self.core = ForenseCore()
        self.caminho_imagem = None
        self.caminho_atual = "/"
        self._ocupado = False
        self._a_fechar = False

        self._configurar_estilo_tabela()
        self._construir_interface()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._log_main("Pronto. Abra uma imagem RAW (.dd/.raw) ou E01 para começar.")

    def _configurar_estilo_tabela(self):
        estilo = ttk.Style(self)
        estilo.theme_use("clam")
        estilo.configure(
            "Treeview",
            background="#161b22",
            foreground="#e6edf3",
            fieldbackground="#161b22",
            rowheight=30,
            borderwidth=0,
        )
        estilo.configure(
            "Treeview.Heading",
            background="#212936",
            foreground="#e6edf3",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
        )
        estilo.map("Treeview", background=[("selected", "#1f6feb")])

    def _construir_interface(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        cabecalho = ctk.CTkFrame(self, fg_color="transparent")
        cabecalho.grid(row=0, column=0, sticky="ew", padx=26, pady=(22, 12))
        cabecalho.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            cabecalho,
            text="E.N.A.",
            font=ctk.CTkFont(family="Segoe UI", size=30, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            cabecalho,
            text="Análise Forense Digital  •  versão de desenvolvimento",
            text_color="#9aa7b5",
            font=ctk.CTkFont(size=13),
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        barra = ctk.CTkFrame(self, corner_radius=12)
        barra.grid(row=1, column=0, sticky="ew", padx=26, pady=(0, 14))
        self.btn_selecionar = ctk.CTkButton(
            barra,
            text="Abrir imagem de evidência",
            command=self.selecionar_imagem,
            width=220,
            height=38,
        )
        self.btn_selecionar.pack(side="left", padx=(14, 8), pady=12)
        self.btn_hash = ctk.CTkButton(
            barra,
            text="Calcular MD5 + SHA-256",
            command=self.iniciar_hash_thread,
            state="disabled",
            width=210,
            height=38,
            fg_color="#238636",
            hover_color="#2ea043",
        )
        self.btn_hash.pack(side="left", padx=8, pady=12)
        self.label_estado = ctk.CTkLabel(
            barra,
            text="Sem evidência aberta",
            text_color="#9aa7b5",
            anchor="w",
        )
        self.label_estado.pack(side="left", fill="x", expand=True, padx=14)

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.grid(row=2, column=0, sticky="nsew", padx=26, pady=(0, 12))
        corpo.grid_rowconfigure(0, weight=3)
        corpo.grid_rowconfigure(1, weight=2)
        corpo.grid_columnconfigure(0, weight=1)

        painel_ficheiros = ctk.CTkFrame(corpo, corner_radius=12)
        painel_ficheiros.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        painel_ficheiros.grid_rowconfigure(2, weight=1)
        painel_ficheiros.grid_columnconfigure(0, weight=1)

        topo_ficheiros = ctk.CTkFrame(painel_ficheiros, fg_color="transparent")
        topo_ficheiros.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        topo_ficheiros.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(
            topo_ficheiros, text="Conteúdo da imagem", font=ctk.CTkFont(size=15, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=(0, 14))
        self.btn_acima = ctk.CTkButton(
            topo_ficheiros, text="↑ Acima", width=82, command=self.ir_para_pasta_pai
        )
        self.btn_acima.grid(row=0, column=1, padx=(0, 10))
        self.label_caminho = ctk.CTkLabel(
            topo_ficheiros, text="/", text_color="#9aa7b5", anchor="w"
        )
        self.label_caminho.grid(row=0, column=2, sticky="ew")

        self.label_metadados = ctk.CTkLabel(
            painel_ficheiros,
            text="Os detalhes da evidência aparecerão aqui.",
            text_color="#9aa7b5",
            anchor="w",
        )
        self.label_metadados.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))

        tabela_frame = ctk.CTkFrame(painel_ficheiros, fg_color="transparent")
        tabela_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        tabela_frame.grid_rowconfigure(0, weight=1)
        tabela_frame.grid_columnconfigure(0, weight=1)
        self.tabela = ttk.Treeview(
            tabela_frame,
            columns=("tipo", "tamanho", "estado"),
            show="tree headings",
            selectmode="browse",
        )
        self.tabela.heading("#0", text="Nome")
        self.tabela.column("#0", width=440, minwidth=180, anchor="w")
        self.tabela.heading("tipo", text="Tipo")
        self.tabela.heading("tamanho", text="Tamanho")
        self.tabela.heading("estado", text="Estado")
        self.tabela.column("tipo", width=110, anchor="w")
        self.tabela.column("tamanho", width=140, anchor="e")
        self.tabela.column("estado", width=110, anchor="center")
        self.tabela.bind("<Double-1>", self.abrir_entrada_selecionada)
        barra_vertical = ttk.Scrollbar(tabela_frame, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=barra_vertical.set)
        self.tabela.grid(row=0, column=0, sticky="nsew")
        barra_vertical.grid(row=0, column=1, sticky="ns")
        self.tabela.tag_configure("pasta", foreground="#79c0ff")
        self.tabela.tag_configure("eliminado", foreground="#ff7b72")

        painel_log = ctk.CTkFrame(corpo, corner_radius=12)
        painel_log.grid(row=1, column=0, sticky="nsew")
        painel_log.grid_rowconfigure(1, weight=1)
        painel_log.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            painel_log, text="Registo de atividade", font=ctk.CTkFont(size=15, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 6))
        self.txt_log = ctk.CTkTextbox(painel_log, height=125, font=ctk.CTkFont(size=12))
        self.txt_log.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        ctk.CTkLabel(
            self,
            text="Protótipo: trabalha sobre ficheiros de imagem; não substitui bloqueador físico de escrita nem validação forense formal.",
            text_color="#7d8590",
            font=ctk.CTkFont(size=11),
        ).grid(row=3, column=0, sticky="w", padx=28, pady=(0, 12))

    def log(self, mensagem):
        if not self._a_fechar:
            self.after(0, self._log_main, mensagem)

    def _log_main(self, mensagem):
        if self._a_fechar:
            return
        self.txt_log.insert("end", mensagem + "\n")
        self.txt_log.see("end")

    def _definir_ocupado(self, ocupado, texto_botao=None):
        self._ocupado = ocupado
        self.btn_selecionar.configure(
            state="disabled" if ocupado else "normal",
            text=texto_botao or "Abrir imagem de evidência",
        )
        if ocupado:
            self.btn_hash.configure(state="disabled")

    def selecionar_imagem(self):
        if self._ocupado:
            return
        caminho = filedialog.askopenfilename(
            title="Selecione uma imagem forense",
            filetypes=[
                ("Imagens RAW/EWF", "*.dd *.raw *.img *.e01 *.ex01"),
                ("Todos os ficheiros", "*.*"),
            ],
        )
        if not caminho:
            return

        self.core.fechar()
        self.caminho_imagem = caminho
        self.caminho_atual = "/"
        self._limpar_tabela()
        self.label_estado.configure(text="A abrir imagem…", text_color="#e3b341")
        self.label_metadados.configure(text=caminho)
        self._definir_ocupado(True, "A abrir…")
        self._log_main(f"A abrir imagem: {caminho}")
        threading.Thread(target=self._abrir_e_listar, args=(caminho,), daemon=True).start()

    def _abrir_e_listar(self, caminho):
        sucesso, mensagem = self.core.abrir_imagem(caminho)
        if not sucesso:
            self.after(0, self._finalizar_abertura, False, mensagem, [])
            return

        sucesso_lista, resultado = self.core.listar_diretorio("/")
        entradas = resultado if sucesso_lista else []
        detalhe = mensagem if sucesso_lista else f"{mensagem} {resultado}"
        self.after(0, self._finalizar_abertura, True, detalhe, entradas)

    def _finalizar_abertura(self, sucesso, mensagem, entradas):
        if self._a_fechar:
            return
        self._definir_ocupado(False)
        self._log_main(mensagem)
        if sucesso:
            self.btn_hash.configure(state="normal")
            self.label_estado.configure(text="Evidência aberta", text_color="#3fb950")
            tamanho_mb = self.core.tamanho_imagem / (1024 * 1024)
            sistema = self.core.sistema_ficheiros or "não identificado"
            self.label_metadados.configure(
                text=f"{self.caminho_imagem}   •   {tamanho_mb:,.2f} MiB   •   FS: {sistema}"
            )
            self._mostrar_entradas(entradas)
            if self.core.particoes:
                self._log_main(f"Partições detetadas: {len(self.core.particoes)}")
        else:
            self.btn_hash.configure(state="disabled")
            self.label_estado.configure(text="Não foi possível abrir", text_color="#ff7b72")
            self.label_metadados.configure(text=mensagem)

    def _limpar_tabela(self):
        for item in self.tabela.get_children():
            self.tabela.delete(item)

    def _mostrar_entradas(self, entradas):
        self._limpar_tabela()
        for entrada in sorted(entradas, key=lambda item: (not item["diretorio"], item["nome"].casefold())):
            tipo = "Pasta" if entrada["diretorio"] else "Ficheiro"
            tamanho = "—" if entrada["diretorio"] else f"{entrada['tamanho']:,} B"
            estado = "Eliminado" if entrada["eliminado"] else "Alocado"
            tag = "pasta" if entrada["diretorio"] else "eliminado" if entrada["eliminado"] else ""
            self.tabela.insert(
                "", "end", text=entrada["nome"], values=(tipo, tamanho, estado), tags=(tag,)
            )
        self.label_caminho.configure(text=self.caminho_atual)

    def abrir_entrada_selecionada(self, _evento=None):
        selecionados = self.tabela.selection()
        if not selecionados:
            return
        item = self.tabela.item(selecionados[0])
        if item["values"] and item["values"][0] == "Pasta":
            self._navegar(posixpath.normpath(posixpath.join(self.caminho_atual, item["text"])))

    def ir_para_pasta_pai(self):
        if self.caminho_atual != "/":
            self._navegar(posixpath.dirname(self.caminho_atual.rstrip("/")) or "/")

    def _navegar(self, caminho):
        if self._ocupado:
            return
        self._definir_ocupado(True, "A listar…")
        threading.Thread(
            target=self._listar_diretorio_thread, args=(caminho,), daemon=True
        ).start()

    def _listar_diretorio_thread(self, caminho):
        sucesso, resultado = self.core.listar_diretorio(caminho)
        self.after(0, self._finalizar_navegacao, caminho, sucesso, resultado)

    def _finalizar_navegacao(self, caminho, sucesso, resultado):
        if self._a_fechar:
            return
        self._definir_ocupado(False)
        self.btn_hash.configure(state="normal" if self.core.img else "disabled")
        if not sucesso:
            self._log_main(resultado)
            return
        self.caminho_atual = caminho
        self._mostrar_entradas(resultado)
        self._log_main(f"Diretório aberto: {caminho} ({len(resultado)} entradas)")

    def iniciar_hash_thread(self):
        if self._ocupado or not self.caminho_imagem:
            return
        self._definir_ocupado(True, "A calcular hashes…")
        self._log_main("A calcular MD5 e SHA-256 por leitura sequencial…")
        threading.Thread(target=self._executar_hash, args=(self.caminho_imagem,), daemon=True).start()

    def _executar_hash(self, caminho):
        sucesso, resultado = self.core.calcular_hash(caminho)
        self.after(0, self._finalizar_hash, sucesso, resultado)

    def _finalizar_hash(self, sucesso, resultado):
        if self._a_fechar:
            return
        self._definir_ocupado(False)
        self.btn_hash.configure(state="normal", text="Calcular MD5 + SHA-256")
        if sucesso:
            self._log_main(f"MD5:    {resultado['md5']}")
            self._log_main(f"SHA256: {resultado['sha256']}")
            self.label_estado.configure(text="Hash calculado", text_color="#3fb950")
        else:
            self._log_main(resultado)
            self.label_estado.configure(text="Falha no cálculo do hash", text_color="#ff7b72")

    def on_close(self):
        if self._ocupado:
            messagebox.showwarning(
                "Operação em curso",
                "Aguarde a operação terminar antes de fechar a aplicação.",
                parent=self,
            )
            return
        self._a_fechar = True
        self.core.fechar()
        self.destroy()


if __name__ == "__main__":
    app = AppEna()
    app.mainloop()