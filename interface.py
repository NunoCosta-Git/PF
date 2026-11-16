import os
import posixpath
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import customtkinter as ctk

from core import ForenseCore
from persistence import PersistenceStore


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
        self.grid_rowconfigure(3, weight=1)

        self.core = ForenseCore()
        self.store = PersistenceStore()
        self._casos_por_rotulo = {}
        self._case_id = None
        self._evidence_id = None
        self._evidence_case_id = None
        self.caminho_imagem = None
        self.caminho_atual = "/"
        self.pasta_carving = None
        self.ficheiros_recuperados = []
        self.metadados_exif = {}
        self._ocupado = False
        self._a_fechar = False

        self._configurar_estilo_tabela()
        self._construir_interface()
        self._atualizar_casos()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._log_main(
            "Pronto. Crie ou selecione um caso antes de abrir uma imagem RAW (.dd/.raw) ou E01."
        )

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
        ctk.CTkLabel(barra, text="Caso:").pack(side="left", padx=(14, 4), pady=12)
        self.combo_casos = ttk.Combobox(barra, state="readonly", width=17)
        self.combo_casos.pack(side="left", padx=(0, 6), pady=12)
        self.combo_casos.bind("<<ComboboxSelected>>", self._selecionar_caso)
        self.btn_novo_caso = ctk.CTkButton(
            barra, text="Novo caso", command=self.criar_caso, width=100, height=38
        )
        self.btn_novo_caso.pack(side="left", padx=(0, 8), pady=12)
        self.btn_selecionar = ctk.CTkButton(
            barra,
            text="Abrir imagem de evidência",
            command=self.selecionar_imagem,
            width=175,
            height=38,
        )
        self.btn_selecionar.pack(side="left", padx=(14, 8), pady=12)
        self.btn_hash = ctk.CTkButton(
            barra,
            text="Calcular MD5 + SHA-256",
            command=self.iniciar_hash_thread,
            state="disabled",
            width=175,
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

        acoes = ctk.CTkFrame(self, fg_color="transparent")
        acoes.grid(row=2, column=0, sticky="ew", padx=26, pady=(0, 10))
        self.btn_carving = ctk.CTkButton(
            acoes,
            text="Carving JPEG / PNG / PDF",
            command=self.iniciar_carving,
            state="disabled",
            width=205,
        )
        self.btn_carving.pack(side="left", padx=(0, 8))
        self.btn_exif = ctk.CTkButton(
            acoes,
            text="Extrair EXIF de imagem",
            command=self.iniciar_extracao_exif,
            width=190,
        )
        self.btn_exif.pack(side="left", padx=8)
        self.btn_relatorio = ctk.CTkButton(
            acoes,
            text="Gerar relatório PDF",
            command=self.iniciar_relatorio,
            state="disabled",
            width=175,
            fg_color="#6e40c9",
            hover_color="#8957e5",
        )
        self.btn_relatorio.pack(side="left", padx=8)
        self.btn_auditoria = ctk.CTkButton(
            acoes,
            text="Ver auditoria do caso",
            command=self.ver_auditoria,
            width=175,
        )
        self.btn_auditoria.pack(side="left", padx=8)

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.grid(row=3, column=0, sticky="nsew", padx=26, pady=(0, 12))
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
        ).grid(row=4, column=0, sticky="w", padx=28, pady=(0, 12))

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
        self.combo_casos.configure(state="disabled" if ocupado else "readonly")
        self.btn_novo_caso.configure(state="disabled" if ocupado else "normal")
        self.btn_selecionar.configure(
            state="disabled" if ocupado else "normal",
            text=texto_botao or "Abrir imagem de evidência",
        )
        estado_evidencia = "disabled" if ocupado or self.core.img is None else "normal"
        self.btn_hash.configure(state=estado_evidencia)
        self.btn_carving.configure(state=estado_evidencia)
        self.btn_relatorio.configure(state=estado_evidencia)
        self.btn_auditoria.configure(state="disabled" if ocupado else "normal")
        self.btn_exif.configure(state="disabled" if ocupado else "normal")

    def _atualizar_casos(self, selecionar_id=None):
        casos = self.store.list_cases()
        self._casos_por_rotulo = {
            f"{caso['name']} [{caso['id'][:8]}]": caso["id"] for caso in casos
        }
        rotulos = list(self._casos_por_rotulo)
        self.combo_casos.configure(values=rotulos)
        if selecionar_id:
            rotulo = next(
                (nome for nome, case_id in self._casos_por_rotulo.items()
                 if case_id == selecionar_id),
                None,
            )
            if rotulo:
                self.combo_casos.set(rotulo)
                self._case_id = selecionar_id
                return
        if self._case_id not in self._casos_por_rotulo.values():
            self._case_id = None
            self.combo_casos.set("")

    def _selecionar_caso(self, _evento=None):
        self._case_id = self._casos_por_rotulo.get(self.combo_casos.get())
        if self._case_id:
            self._log_main(f"Caso selecionado: {self.combo_casos.get()}")

    def criar_caso(self):
        nome = simpledialog.askstring("Novo caso", "Nome ou referência do caso:", parent=self)
        if nome is None:
            return
        operador = simpledialog.askstring("Novo caso", "Nome do operador:", parent=self)
        if operador is None:
            return
        try:
            case_id = self.store.create_case(nome, operador)
            self._atualizar_casos(selecionar_id=case_id)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Novo caso", str(exc), parent=self)
            return
        except Exception as exc:
            messagebox.showerror(
                "Novo caso", f"Não foi possível guardar o caso: {exc}", parent=self
            )
            return
        self._log_main(f"Caso criado: {nome.strip()} | operador: {operador.strip()}")

    def ver_auditoria(self):
        if not self._case_id:
            messagebox.showwarning(
                "Auditoria", "Selecione um caso para consultar o histórico.", parent=self
            )
            return
        try:
            eventos = self.store.list_events(self._case_id)
        except Exception as exc:
            messagebox.showerror(
                "Auditoria", f"Não foi possível ler o histórico: {exc}", parent=self
            )
            return

        janela = ctk.CTkToplevel(self)
        janela.title("Auditoria do caso")
        janela.geometry("900x480")
        janela.transient(self)
        texto = ctk.CTkTextbox(janela, wrap="word")
        texto.pack(fill="both", expand=True, padx=14, pady=14)
        for evento in eventos:
            texto.insert(
                "end",
                f"{evento['occurred_at']} | {evento['operator']} | {evento['action']}\n"
                f"  Evidência: {evento['evidence_id'] or '—'}\n"
                f"  Detalhes: {evento['details_json']}\n\n",
            )
        texto.configure(state="disabled")

    def selecionar_imagem(self):
        if self._ocupado:
            return
        if not self._case_id:
            messagebox.showwarning(
                "Caso obrigatório",
                "Crie ou selecione um caso antes de abrir uma evidência.",
                parent=self,
            )
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
        self._evidence_id = None
        self._evidence_case_id = None
        self.caminho_imagem = caminho
        self.caminho_atual = "/"
        self.pasta_carving = None
        self.ficheiros_recuperados = []
        self.metadados_exif = {}
        self._limpar_tabela()
        self.label_estado.configure(text="A abrir imagem…", text_color="#e3b341")
        self.label_metadados.configure(text=caminho)
        self._definir_ocupado(True, "A abrir…")
        self._log_main(f"A abrir imagem: {caminho}")
        threading.Thread(
            target=self._abrir_e_listar,
            args=(caminho, self._case_id),
            daemon=True,
        ).start()

    def _abrir_e_listar(self, caminho, case_id):
        sucesso, mensagem = self.core.abrir_imagem(caminho)
        if not sucesso:
            erro_auditoria = self._registar_evento(
                case_id, None, "image_open_failed", {"path": caminho, "error": mensagem}
            )
            if erro_auditoria:
                mensagem += f" Falha ao registar a auditoria: {erro_auditoria}"
            self.after(0, self._finalizar_abertura, False, mensagem, [], None, None)
            return

        try:
            evidence_id = self.store.register_evidence(
                case_id, caminho, self.core.tamanho_imagem
            )
        except Exception as exc:
            self.core.fechar()
            self.after(
                0,
                self._finalizar_abertura,
                False,
                f"A imagem abriu, mas não foi possível registar a evidência; "
                f"a análise foi interrompida: {exc}",
                [],
                None,
                None,
            )
            return

        sucesso_lista, resultado = self.core.listar_diretorio("/")
        entradas = resultado if sucesso_lista else []
        detalhe = mensagem if sucesso_lista else f"{mensagem} {resultado}"
        acao = "directory_listed" if sucesso_lista else "directory_list_unavailable"
        detalhes = (
            {"path": "/", "entries": len(entradas)}
            if sucesso_lista
            else {"path": "/", "reason": resultado}
        )
        erro_auditoria = self._registar_evento(
            case_id, evidence_id, acao, detalhes
        )
        if erro_auditoria:
            self.core.fechar()
            self.after(
                0,
                self._finalizar_abertura,
                False,
                f"A evidência foi registada, mas a auditoria da listagem falhou: "
                f"{erro_auditoria}",
                [],
                None,
                None,
            )
            return
        self.after(
            0, self._finalizar_abertura, True, detalhe, entradas, evidence_id, case_id
        )

    def _finalizar_abertura(self, sucesso, mensagem, entradas, evidence_id, case_id):
        if self._a_fechar:
            return
        self._definir_ocupado(False)
        self._log_main(mensagem)
        if sucesso:
            self._evidence_id = evidence_id
            self._evidence_case_id = case_id
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
            self.caminho_imagem = None
            self._evidence_id = None
            self._evidence_case_id = None
            self._definir_ocupado(False)
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
        if sucesso:
            erro_auditoria = self._registar_evento(
                self._evidence_case_id,
                self._evidence_id,
                "directory_listed",
                {"path": caminho, "entries": len(resultado)},
            )
            if erro_auditoria:
                sucesso = False
                resultado = f"Diretório lido, mas a auditoria falhou: {erro_auditoria}"
        else:
            erro_auditoria = self._registar_evento(
                self._evidence_case_id,
                self._evidence_id,
                "directory_list_failed",
                {"path": caminho, "error": resultado},
            )
            if erro_auditoria:
                resultado += f" Falha ao registar a auditoria: {erro_auditoria}"
        self.after(0, self._finalizar_navegacao, caminho, sucesso, resultado)

    def _finalizar_navegacao(self, caminho, sucesso, resultado):
        if self._a_fechar:
            return
        self._definir_ocupado(False)
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
        threading.Thread(
            target=self._executar_hash,
            args=(self.caminho_imagem, self._evidence_case_id, self._evidence_id),
            daemon=True,
        ).start()

    def _executar_hash(self, caminho, case_id, evidence_id):
        sucesso, resultado = self.core.calcular_hash(caminho)
        if sucesso:
            try:
                self.store.record_hashes(
                    case_id, evidence_id, resultado["md5"], resultado["sha256"]
                )
            except Exception as exc:
                sucesso = False
                resultado = f"Hashes calculados, mas não foi possível persistir o resultado: {exc}"
        else:
            erro_auditoria = self._registar_evento(
                case_id, evidence_id, "hash_calculation_failed", {"error": resultado}
            )
            if erro_auditoria:
                resultado += f" Falha ao registar a auditoria: {erro_auditoria}"
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

    def iniciar_carving(self):
        if self._ocupado or not self.caminho_imagem:
            return
        pasta = filedialog.askdirectory(
            title="Escolha a pasta para guardar os ficheiros extraídos",
            initialdir=os.getcwd(),
            mustexist=True,
        )
        if not pasta:
            return

        self.pasta_carving = pasta
        self.ficheiros_recuperados = []
        self._definir_ocupado(True, "A procurar assinaturas…")
        self.label_estado.configure(text="A percorrer a imagem…", text_color="#e3b341")
        self._log_main(
            "A procurar JPEG, PNG e PDF na imagem lógica completa; "
            "a pesquisa não se limita a blocos não alocados."
        )
        threading.Thread(
            target=self._executar_carving,
            args=(pasta, self._evidence_case_id, self._evidence_id),
            daemon=True,
        ).start()

    def _executar_carving(self, pasta, case_id, evidence_id):
        sucesso, resultado = self.core.fazer_carving(pasta_saida=pasta)
        acao = "carving_completed" if sucesso else "carving_failed"
        detalhes = (
            {
                "output_directory": pasta,
                "files": [
                    {
                        "type": item["tipo"],
                        "name": item["nome"],
                        "path": item["caminho"],
                        "offset": item["offset"],
                        "size": item["tamanho"],
                        "exif": item.get("exif", {}),
                    }
                    for item in resultado
                ],
            }
            if sucesso
            else {"error": resultado}
        )
        erro_auditoria = self._registar_evento(
            case_id, evidence_id, acao, detalhes
        )
        if erro_auditoria:
            sucesso = False
            resultado = f"{resultado}; falha ao registar a auditoria: {erro_auditoria}"
        self.after(0, self._finalizar_carving, sucesso, resultado)

    def _finalizar_carving(self, sucesso, resultado):
        if self._a_fechar:
            return
        self._definir_ocupado(False)
        if not sucesso:
            self._log_main(resultado)
            self.label_estado.configure(text="Falha no carving", text_color="#ff7b72")
            return

        self.ficheiros_recuperados = resultado
        self.label_estado.configure(
            text=f"Carving concluído: {len(resultado)} ficheiro(s)",
            text_color="#3fb950",
        )
        self._log_main(
            f"Carving concluído: {len(resultado)} ficheiro(s) extraído(s) "
            f"para {self.pasta_carving}."
        )
        for item in resultado[:20]:
            self._log_main(
                f"  - {item['tipo']} {item['nome']} | offset {item['offset']} "
                f"| {item['tamanho']} bytes"
            )
            if item.get("exif"):
                resumo = ", ".join(
                    f"{chave}: {valor}" for chave, valor in item["exif"].items()
                )
                self._log_main(f"    EXIF: {resumo}")
        if len(resultado) > 20:
            self._log_main(f"  ... mais {len(resultado) - 20} ficheiro(s).")
        self._log_main(
            "Nota: os resultados são deteções por assinatura; podem incluir dados "
            "alocados, falsos positivos ou ficheiros incompletos."
        )

    def iniciar_extracao_exif(self):
        if self._ocupado:
            return
        if not self._case_id:
            messagebox.showwarning(
                "Caso obrigatório",
                "Crie ou selecione um caso antes de extrair metadados.",
                parent=self,
            )
            return
        opcoes = {"title": "Selecione uma imagem para extrair metadados EXIF"}
        if self.pasta_carving and os.path.isdir(self.pasta_carving):
            opcoes["initialdir"] = self.pasta_carving
        opcoes["filetypes"] = [
            ("Imagens", "*.jpg *.jpeg *.png *.tif *.tiff"),
            ("Todos os ficheiros", "*.*"),
        ]
        caminho = filedialog.askopenfilename(**opcoes)
        if not caminho:
            return

        evidence_id = (
            self._evidence_id
            if self._evidence_case_id == self._case_id
            else None
        )
        self._definir_ocupado(True, "A ler metadados…")
        self._log_main(f"A extrair EXIF de {caminho}")
        threading.Thread(
            target=self._executar_extracao_exif,
            args=(caminho, self._case_id, evidence_id),
            daemon=True,
        ).start()

    def _executar_extracao_exif(self, caminho, case_id, evidence_id):
        sucesso, resultado = self.core.extrair_exif(caminho)
        erro_auditoria = self._registar_evento(
            case_id,
            evidence_id,
            "exif_extracted" if sucesso else "exif_extraction_failed",
            {"path": caminho, "metadata": resultado}
            if sucesso
            else {"path": caminho, "error": resultado},
        )
        if erro_auditoria:
            sucesso = False
            resultado = f"{resultado}; falha ao registar a auditoria: {erro_auditoria}"
        self.after(0, self._finalizar_extracao_exif, caminho, sucesso, resultado)

    def _finalizar_extracao_exif(self, caminho, sucesso, resultado):
        if self._a_fechar:
            return
        self._definir_ocupado(False)
        if not sucesso:
            self._log_main(resultado)
            messagebox.showinfo("Metadados EXIF", resultado, parent=self)
            return

        self.metadados_exif[caminho] = resultado
        texto = "\n".join(f"{chave}: {valor}" for chave, valor in resultado.items())
        self._log_main(f"Metadados EXIF de {os.path.basename(caminho)}:")
        for linha in texto.splitlines():
            self._log_main(f"  {linha}")
        messagebox.showinfo("Metadados EXIF", texto, parent=self)

    def iniciar_relatorio(self):
        if self._ocupado or not self.caminho_imagem:
            return
        caminho_pdf = filedialog.asksaveasfilename(
            title="Guardar relatório forense",
            defaultextension=".pdf",
            filetypes=[("Documento PDF", "*.pdf")],
            initialfile="relatorio_ena.pdf",
        )
        if not caminho_pdf:
            return

        self._definir_ocupado(True, "A preparar relatório…")
        self.label_estado.configure(text="A calcular hash para o relatório…", text_color="#e3b341")
        self._log_main("A recalcular hashes e a preparar o relatório PDF…")
        threading.Thread(
            target=self._executar_relatorio,
            args=(
                caminho_pdf,
                self.caminho_imagem,
                list(self.ficheiros_recuperados),
                dict(self.metadados_exif),
                self._evidence_case_id,
                self._evidence_id,
            ),
            daemon=True,
        ).start()

    def _executar_relatorio(
        self, caminho_pdf, caminho_imagem, recuperados, metadados_exif, case_id, evidence_id
    ):
        sucesso_hash, hashes = self.core.calcular_hash(caminho_imagem)
        if not sucesso_hash:
            erro_auditoria = self._registar_evento(
                case_id, evidence_id, "report_generation_failed", {"error": hashes}
            )
            if erro_auditoria:
                hashes += f" Falha ao registar a auditoria: {erro_auditoria}"
            self.after(0, self._finalizar_relatorio, False, hashes)
            return

        try:
            self.store.record_hashes(case_id, evidence_id, hashes["md5"], hashes["sha256"])
        except Exception as exc:
            self.after(
                0,
                self._finalizar_relatorio,
                False,
                f"Não foi possível persistir os hashes calculados para o relatório: {exc}",
            )
            return

        sucesso_lista, resultado_lista = self.core.listar_diretorio("/")
        ficheiros = resultado_lista if sucesso_lista else []
        sucesso_pdf, mensagem = self.core.gerar_relatorio_pdf(
            caminho_saida=caminho_pdf,
            info_imagem=caminho_imagem,
            lista_ficheiros=ficheiros,
            hashes=hashes,
            recuperados=recuperados,
            metadados_exif=metadados_exif,
        )
        if sucesso_pdf and not sucesso_lista:
            mensagem += (
                " A imagem não tinha sistema de ficheiros reconhecido; "
                "a lista da raiz ficou vazia."
            )
        acao = "report_created" if sucesso_pdf else "report_generation_failed"
        detalhes = (
            {"path": caminho_pdf, "md5": hashes["md5"], "sha256": hashes["sha256"]}
            if sucesso_pdf
            else {"path": caminho_pdf, "error": mensagem}
        )
        erro_auditoria = self._registar_evento(
            case_id, evidence_id, acao, detalhes
        )
        if erro_auditoria:
            sucesso_pdf = False
            mensagem = f"{mensagem}; falha ao registar a auditoria: {erro_auditoria}"
        self.after(0, self._finalizar_relatorio, sucesso_pdf, mensagem)

    def _registar_evento(self, case_id, evidence_id, action, details):
        if not case_id:
            return "não existe um caso selecionado"
        try:
            self.store.record_event(case_id, evidence_id, action, details)
        except Exception as exc:
            return str(exc)
        return None

    def _finalizar_relatorio(self, sucesso, mensagem):
        if self._a_fechar:
            return
        self._definir_ocupado(False)
        self._log_main(mensagem)
        if sucesso:
            self.label_estado.configure(text="Relatório PDF criado", text_color="#3fb950")
            messagebox.showinfo("Relatório PDF", mensagem, parent=self)
        else:
            self.label_estado.configure(text="Falha ao gerar relatório", text_color="#ff7b72")
            messagebox.showerror("Relatório PDF", mensagem, parent=self)

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