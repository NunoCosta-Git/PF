import os
import posixpath
import sys

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QInputDialog,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import ForenseCore
from persistence import PersistenceStore


class WorkerSignals(QObject):
    result = Signal(object)


class WorkerError(Exception):
    pass


class Worker(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.function()
        except Exception as exc:
            result = WorkerError(f"Erro inesperado na operação: {exc}")
        self.signals.result.emit((self, result))


class AppEna(QMainWindow):
    """Interface desktop Qt para os fluxos de análise E.N.A."""

    def __init__(self, core=None, store=None):
        super().__init__()
        self.setWindowTitle("E.N.A. | Análise Forense Digital")
        self.resize(1120, 760)
        self.setMinimumSize(900, 620)

        self.core = core or ForenseCore()
        self.store = store or PersistenceStore()
        self.thread_pool = QThreadPool.globalInstance()
        self._workers = {}
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

        self._construir_interface()
        self._atualizar_casos()
        self._log_main(
            "Pronto. Crie ou selecione um caso antes de abrir uma imagem RAW (.dd/.raw) ou E01."
        )

    def _construir_interface(self):
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(22, 18, 22, 14)
        layout.setSpacing(12)
        self.setCentralWidget(central)

        titulo = QLabel("E.N.A.  |  Análise Forense Digital")
        titulo.setObjectName("title")
        layout.addWidget(titulo)

        barra = QHBoxLayout()
        barra.addWidget(QLabel("Caso:"))
        self.combo_casos = QComboBox()
        self.combo_casos.setMinimumWidth(190)
        self.combo_casos.currentIndexChanged.connect(self._selecionar_caso)
        barra.addWidget(self.combo_casos)
        self.btn_novo_caso = QPushButton("Novo caso")
        self.btn_novo_caso.clicked.connect(self.criar_caso)
        barra.addWidget(self.btn_novo_caso)
        self.btn_selecionar = QPushButton("Abrir imagem de evidência")
        self.btn_selecionar.clicked.connect(self.selecionar_imagem)
        barra.addWidget(self.btn_selecionar)
        self.btn_hash = QPushButton("Calcular MD5 + SHA-256")
        self.btn_hash.clicked.connect(self.iniciar_hash_thread)
        barra.addWidget(self.btn_hash)
        self.label_estado = QLabel("Sem evidência aberta")
        self.label_estado.setObjectName("status")
        barra.addWidget(self.label_estado, 1)
        layout.addLayout(barra)

        acoes = QHBoxLayout()
        self.btn_carving = QPushButton("Carving JPEG / PNG / PDF")
        self.btn_carving.clicked.connect(self.iniciar_carving)
        acoes.addWidget(self.btn_carving)
        self.btn_exif = QPushButton("Extrair EXIF de imagem")
        self.btn_exif.clicked.connect(self.iniciar_extracao_exif)
        acoes.addWidget(self.btn_exif)
        self.btn_relatorio = QPushButton("Gerar relatório PDF")
        self.btn_relatorio.clicked.connect(self.iniciar_relatorio)
        acoes.addWidget(self.btn_relatorio)
        self.btn_comparar_hash = QPushButton("Comparar hash de referência")
        self.btn_comparar_hash.clicked.connect(self.iniciar_comparacao_hash)
        acoes.addWidget(self.btn_comparar_hash)
        self.btn_auditoria = QPushButton("Ver auditoria do caso")
        self.btn_auditoria.clicked.connect(self.ver_auditoria)
        acoes.addWidget(self.btn_auditoria)
        acoes.addStretch(1)
        layout.addLayout(acoes)

        painel = QWidget()
        painel_layout = QVBoxLayout(painel)
        painel_layout.setContentsMargins(0, 0, 0, 0)
        painel_layout.setSpacing(8)
        topo = QHBoxLayout()
        label_ficheiros = QLabel("Conteúdo da imagem")
        label_ficheiros.setObjectName("sectionTitle")
        topo.addWidget(label_ficheiros)
        self.btn_acima = QPushButton("↑ Acima")
        self.btn_acima.clicked.connect(self.ir_para_pasta_pai)
        topo.addWidget(self.btn_acima)
        self.label_caminho = QLabel("/")
        self.label_caminho.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        topo.addWidget(self.label_caminho, 1)
        painel_layout.addLayout(topo)
        self.label_metadados = QLabel("Os detalhes da evidência aparecerão aqui.")
        self.label_metadados.setWordWrap(True)
        self.label_metadados.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        painel_layout.addWidget(self.label_metadados)

        self.tabela = QTableWidget(0, 4)
        self.tabela.setHorizontalHeaderLabels(["Nome", "Tipo", "Tamanho", "Estado"])
        self.tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabela.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela.horizontalHeader().setStretchLastSection(True)
        self.tabela.horizontalHeader().setSectionResizeMode(0, self.tabela.horizontalHeader().ResizeMode.Stretch)
        self.tabela.cellDoubleClicked.connect(self.abrir_entrada_selecionada)
        painel_layout.addWidget(self.tabela, 1)

        log_panel = QWidget()
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(0, 0, 0, 0)
        label_log = QLabel("Registo de atividade")
        label_log.setObjectName("sectionTitle")
        log_layout.addWidget(label_log)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMinimumHeight(130)
        log_layout.addWidget(self.txt_log)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(painel)
        splitter.addWidget(log_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        rodape = QLabel(
            "Protótipo: trabalha sobre ficheiros de imagem; não substitui bloqueador físico "
            "de escrita nem validação forense formal."
        )
        rodape.setObjectName("footer")
        layout.addWidget(rodape)
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #0d1117; color: #e6edf3; }
            QLineEdit, QComboBox, QTableWidget, QTextEdit {
                background: #161b22; color: #e6edf3; border: 1px solid #30363d;
                border-radius: 5px; padding: 5px;
            }
            QPushButton {
                background: #212936; border: 1px solid #30363d; border-radius: 6px;
                padding: 8px 11px; min-height: 20px;
            }
            QPushButton:hover { background: #303b4b; }
            QPushButton:disabled { color: #7d8590; background: #161b22; }
            QHeaderView::section {
                background: #212936; color: #e6edf3; padding: 7px;
                border: 1px solid #30363d;
            }
            QLabel#title { font-size: 25px; font-weight: bold; color: #f0f6fc; }
            QLabel#sectionTitle { font-size: 15px; font-weight: bold; }
            QLabel#status { color: #9aa7b5; }
            QLabel#footer { color: #7d8590; font-size: 10px; }
            """
        )
        self._definir_ocupado(False)

    def _log_main(self, mensagem):
        self.txt_log.append(mensagem)

    def _start_worker(self, function, callback):
        worker = Worker(function)
        self._workers[worker] = callback
        worker.signals.result.connect(self._handle_worker_result)
        self.thread_pool.start(worker)

    def _handle_worker_result(self, payload):
        worker, resultado = payload
        callback = self._workers.pop(worker, None)
        if callback is None:
            return
        if isinstance(resultado, WorkerError):
            self._definir_ocupado(False)
            self._set_estado("Falha na operação", "#ff7b72")
            self._log_main(str(resultado))
            QMessageBox.critical(self, "Erro", str(resultado))
            return
        callback(resultado)

    def _set_estado(self, texto, cor=None):
        self.label_estado.setText(texto)
        self.label_estado.setStyleSheet(f"color: {cor};" if cor else "")

    def _definir_ocupado(self, ocupado, texto_botao=None):
        self._ocupado = ocupado
        self.combo_casos.setEnabled(not ocupado)
        self.btn_novo_caso.setEnabled(not ocupado)
        self.btn_selecionar.setEnabled(not ocupado)
        self.btn_selecionar.setText(texto_botao or "Abrir imagem de evidência")
        evidencia_disponivel = not ocupado and self.core.img is not None
        self.btn_hash.setEnabled(evidencia_disponivel)
        self.btn_comparar_hash.setEnabled(evidencia_disponivel)
        self.btn_carving.setEnabled(evidencia_disponivel)
        self.btn_relatorio.setEnabled(evidencia_disponivel)
        self.btn_exif.setEnabled(not ocupado)
        self.btn_auditoria.setEnabled(not ocupado and self._case_id is not None)
        self.btn_acima.setEnabled(not ocupado and self.core.fs is not None)

    def _atualizar_casos(self, selecionar_id=None):
        casos = self.store.list_cases()
        self._casos_por_rotulo = {
            f"{caso['name']} [{caso['id'][:8]}]": caso["id"] for caso in casos
        }
        self.combo_casos.blockSignals(True)
        self.combo_casos.clear()
        self.combo_casos.addItem("")
        for rotulo in self._casos_por_rotulo:
            self.combo_casos.addItem(rotulo)
        if selecionar_id:
            rotulo = next(
                (nome for nome, case_id in self._casos_por_rotulo.items()
                 if case_id == selecionar_id),
                None,
            )
            if rotulo:
                self.combo_casos.setCurrentText(rotulo)
                self._case_id = selecionar_id
        elif self._case_id not in self._casos_por_rotulo.values():
            self._case_id = None
        elif self._case_id:
            rotulo = next(
                nome for nome, case_id in self._casos_por_rotulo.items()
                if case_id == self._case_id
            )
            self.combo_casos.setCurrentText(rotulo)
        self.combo_casos.blockSignals(False)
        self._definir_ocupado(self._ocupado)

    def _selecionar_caso(self, _indice=None):
        self._case_id = self._casos_por_rotulo.get(self.combo_casos.currentText())
        if self._case_id:
            self._log_main(f"Caso selecionado: {self.combo_casos.currentText()}")
        self._definir_ocupado(self._ocupado)

    def criar_caso(self):
        nome, aceite = QInputDialog.getText(
            self, "Novo caso", "Nome ou referência do caso:"
        )
        if not aceite or not nome.strip():
            return
        operador, aceite = QInputDialog.getText(self, "Novo caso", "Nome do operador:")
        if not aceite:
            return
        try:
            case_id = self.store.create_case(nome.strip(), operador.strip())
            self._atualizar_casos(selecionar_id=case_id)
        except Exception as exc:
            QMessageBox.critical(self, "Novo caso", f"Não foi possível guardar o caso: {exc}")
            return
        self._log_main(f"Caso criado: {nome.strip()} | operador: {operador.strip()}")

    def ver_auditoria(self):
        if not self._case_id:
            QMessageBox.warning(self, "Auditoria", "Selecione um caso para consultar o histórico.")
            return
        try:
            eventos = self.store.list_events(self._case_id)
        except Exception as exc:
            QMessageBox.critical(self, "Auditoria", f"Não foi possível ler o histórico: {exc}")
            return
        janela = QDialog(self)
        janela.setWindowTitle("Auditoria do caso")
        janela.resize(900, 480)
        layout = QVBoxLayout(janela)
        texto = QTextEdit()
        texto.setReadOnly(True)
        for evento in eventos:
            texto.append(
                f"{evento['occurred_at']} | {evento['operator']} | {evento['action']}\n"
                f"  Evidência: {evento['evidence_id'] or '—'}\n"
                f"  Detalhes: {evento['details_json']}\n"
            )
        layout.addWidget(texto)
        janela.exec()

    def selecionar_imagem(self):
        if self._ocupado:
            return
        if not self._case_id:
            QMessageBox.warning(
                self, "Caso obrigatório", "Crie ou selecione um caso antes de abrir uma evidência."
            )
            return
        caminho, _ = QFileDialog.getOpenFileName(
            self,
            "Selecione uma imagem forense",
            "",
            "Imagens RAW/EWF (*.dd *.raw *.img *.e01 *.ex01);;Todos os ficheiros (*)",
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
        self.label_metadados.setText(caminho)
        self._set_estado("A abrir imagem…", "#e3b341")
        self._definir_ocupado(True, "A abrir…")
        self._log_main(f"A abrir imagem: {caminho}")
        case_id = self._case_id
        self._start_worker(
            lambda: self._abrir_e_listar(caminho, case_id),
            self._finalizar_abertura,
        )

    def _abrir_e_listar(self, caminho, case_id):
        sucesso, mensagem = self.core.abrir_imagem(caminho)
        if not sucesso:
            erro = self._registar_evento(
                case_id,
                None,
                "image_open_failed",
                {"parameters": {"path": caminho}, "result": {"error": mensagem}},
            )
            if erro:
                mensagem += f" Falha ao registar a auditoria: {erro}"
            return False, mensagem, [], None, None

        try:
            evidence_id = self.store.register_evidence(
                case_id, caminho, self.core.tamanho_imagem
            )
        except Exception as exc:
            self.core.fechar()
            return (
                False,
                f"A imagem abriu, mas não foi possível registar a evidência; "
                f"a análise foi interrompida: {exc}",
                [],
                None,
                None,
            )

        sucesso_lista, resultado = self.core.listar_diretorio("/")
        entradas = resultado if sucesso_lista else []
        mensagem_lista = mensagem if sucesso_lista else f"{mensagem} {resultado}"
        acao = "directory_listed" if sucesso_lista else "directory_list_unavailable"
        detalhes = (
            {
                "parameters": {"path": "/"},
                "result": {"entry_count": len(entradas)},
            }
            if sucesso_lista
            else {"parameters": {"path": "/"}, "result": {"error": resultado}}
        )
        erro = self._registar_evento(case_id, evidence_id, acao, detalhes)
        if erro:
            self.core.fechar()
            return (
                False,
                f"A evidência foi registada, mas a auditoria da listagem falhou: {erro}",
                [],
                None,
                None,
            )
        return True, mensagem_lista, entradas, evidence_id, case_id

    def _finalizar_abertura(self, resultado):
        sucesso, mensagem, entradas, evidence_id, case_id = resultado
        self._definir_ocupado(False)
        self._log_main(mensagem)
        if sucesso:
            self._evidence_id = evidence_id
            self._evidence_case_id = case_id
            self._set_estado("Evidência aberta", "#3fb950")
            tamanho_mb = self.core.tamanho_imagem / (1024 * 1024)
            sistema = self.core.sistema_ficheiros or "não identificado"
            self.label_metadados.setText(
                f"{self.caminho_imagem}   •   {tamanho_mb:,.2f} MiB   •   FS: {sistema}"
            )
            self._mostrar_entradas(entradas)
            if self.core.particoes:
                self._log_main(f"Partições detetadas: {len(self.core.particoes)}")
        else:
            self.caminho_imagem = None
            self._evidence_id = None
            self._evidence_case_id = None
            self._set_estado("Não foi possível abrir", "#ff7b72")
            self.label_metadados.setText(mensagem)

    def _limpar_tabela(self):
        self.tabela.setRowCount(0)

    def _mostrar_entradas(self, entradas):
        self._limpar_tabela()
        entradas_ordenadas = sorted(
            entradas, key=lambda item: (not item["diretorio"], item["nome"].casefold())
        )
        for entrada in entradas_ordenadas:
            linha = self.tabela.rowCount()
            self.tabela.insertRow(linha)
            tipo = "Pasta" if entrada["diretorio"] else "Ficheiro"
            tamanho = "—" if entrada["diretorio"] else f"{entrada['tamanho']:,} B"
            estado = "Eliminado" if entrada["eliminado"] else "Alocado"
            for coluna, valor in enumerate((entrada["nome"], tipo, tamanho, estado)):
                item = QTableWidgetItem(valor)
                item.setData(Qt.ItemDataRole.UserRole, entrada)
                self.tabela.setItem(linha, coluna, item)
        self.label_caminho.setText(self.caminho_atual)

    def abrir_entrada_selecionada(self, linha, _coluna):
        item = self.tabela.item(linha, 0)
        entrada = item.data(Qt.ItemDataRole.UserRole) if item else None
        if entrada and entrada["diretorio"]:
            self._navegar(posixpath.normpath(posixpath.join(self.caminho_atual, entrada["nome"])))

    def ir_para_pasta_pai(self):
        if self.caminho_atual != "/":
            self._navegar(posixpath.dirname(self.caminho_atual.rstrip("/")) or "/")

    def _navegar(self, caminho):
        if self._ocupado:
            return
        self._definir_ocupado(True, "A listar…")
        self._start_worker(
            lambda: self._listar_diretorio_thread(caminho),
            lambda resultado: self._finalizar_navegacao(caminho, resultado),
        )

    def _listar_diretorio_thread(self, caminho):
        sucesso, resultado = self.core.listar_diretorio(caminho)
        if sucesso:
            erro = self._registar_evento(
                self._evidence_case_id,
                self._evidence_id,
                "directory_listed",
                {
                    "parameters": {"path": caminho},
                    "result": {"entry_count": len(resultado)},
                },
            )
            if erro:
                return False, f"Diretório lido, mas a auditoria falhou: {erro}"
        else:
            erro = self._registar_evento(
                self._evidence_case_id,
                self._evidence_id,
                "directory_list_failed",
                {"parameters": {"path": caminho}, "result": {"error": resultado}},
            )
            if erro:
                resultado += f" Falha ao registar a auditoria: {erro}"
        return sucesso, resultado

    def _finalizar_navegacao(self, caminho, resultado):
        sucesso, entradas = resultado
        self._definir_ocupado(False)
        if not sucesso:
            self._log_main(entradas)
            return
        self.caminho_atual = caminho
        self._mostrar_entradas(entradas)
        self._log_main(f"Diretório aberto: {caminho} ({len(entradas)} entradas)")

    def iniciar_hash_thread(self):
        if self._ocupado or not self.caminho_imagem:
            return
        self._definir_ocupado(True, "A calcular hashes…")
        self._log_main("A calcular MD5 e SHA-256 por leitura sequencial…")
        caminho = self.caminho_imagem
        case_id, evidence_id = self._evidence_case_id, self._evidence_id
        self._start_worker(
            lambda: self._executar_hash(caminho, case_id, evidence_id),
            self._finalizar_hash,
        )

    def _executar_hash(self, caminho, case_id, evidence_id):
        sucesso, resultado = self.core.calcular_hash(caminho)
        if sucesso:
            try:
                self.store.record_hashes(
                    case_id, evidence_id, resultado["md5"], resultado["sha256"]
                )
            except Exception as exc:
                return False, f"Hashes calculados, mas não foi possível persistir o resultado: {exc}"
        else:
            erro = self._registar_evento(
                case_id,
                evidence_id,
                "hash_calculation_failed",
                {
                    "parameters": {"algorithms": ["MD5", "SHA-256"]},
                    "result": {"error": resultado},
                },
            )
            if erro:
                resultado += f" Falha ao registar a auditoria: {erro}"
        return sucesso, resultado

    def _finalizar_hash(self, resultado):
        sucesso, hashes = resultado
        self._definir_ocupado(False)
        if sucesso:
            self._log_main(f"MD5:    {hashes['md5']}")
            self._log_main(f"SHA256: {hashes['sha256']}")
            self._set_estado("Hash calculado", "#3fb950")
        else:
            self._log_main(hashes)
            self._set_estado("Falha no cálculo do hash", "#ff7b72")

    def iniciar_comparacao_hash(self):
        if self._ocupado or not self.caminho_imagem:
            return
        referencia, aceite = QInputDialog.getText(
            self,
            "Comparar hash de referência",
            "Cole um hash MD5 (32 caracteres) ou SHA-256 (64 caracteres), "
            "calculado sobre a mesma representação lógica da evidência:",
        )
        if not aceite:
            return
        try:
            algoritmo, referencia = self.store.normalize_reference_hash(referencia)
        except ValueError as exc:
            QMessageBox.warning(self, "Hash inválido", str(exc))
            return

        self._definir_ocupado(True, "A comparar hash…")
        self._log_main(f"A calcular e comparar {algoritmo.upper()} de referência…")
        caminho = self.caminho_imagem
        case_id, evidence_id = self._evidence_case_id, self._evidence_id
        self._start_worker(
            lambda: self._executar_comparacao_hash(
                caminho, case_id, evidence_id, referencia
            ),
            self._finalizar_comparacao_hash,
        )

    def _executar_comparacao_hash(
        self, caminho, case_id, evidence_id, referencia
    ):
        sucesso, resultado = self.core.calcular_hash(caminho)
        if not sucesso:
            erro = self._registar_evento(
                case_id,
                evidence_id,
                "hash_calculation_failed",
                {
                    "parameters": {
                        "algorithms": ["MD5", "SHA-256"],
                        "operation": "reference_comparison",
                        "reference_hash": referencia,
                    },
                    "result": {"error": resultado},
                },
            )
            if erro:
                resultado += f" Falha ao registar a auditoria: {erro}"
            return False, resultado
        try:
            self.store.record_hashes(
                case_id, evidence_id, resultado["md5"], resultado["sha256"]
            )
            comparacao = self.store.record_hash_comparison(
                case_id, evidence_id, referencia, resultado
            )
        except Exception as exc:
            return False, f"Hash calculado, mas não foi possível registar a comparação: {exc}"
        return True, {"hashes": resultado, "comparacao": comparacao}

    def _finalizar_comparacao_hash(self, resultado):
        sucesso, dados = resultado
        self._definir_ocupado(False)
        if not sucesso:
            self._log_main(dados)
            self._set_estado("Falha na comparação do hash", "#ff7b72")
            return

        hashes = dados["hashes"]
        comparacao = dados["comparacao"]
        algoritmo = comparacao["algorithm"].upper()
        self._log_main(f"MD5:    {hashes['md5']}")
        self._log_main(f"SHA256: {hashes['sha256']}")
        self._log_main(
            f"Hash de referência ({algoritmo}): {comparacao['reference_hash']}"
        )
        if comparacao["matches"]:
            self._log_main(f"VERIFICADO: o hash {algoritmo} coincide com a referência.")
            self._set_estado("Hash de referência coincide", "#3fb950")
        else:
            self._log_main(f"DIVERGÊNCIA: o hash {algoritmo} não coincide com a referência.")
            self._set_estado("Hash de referência diferente", "#ff7b72")

    def iniciar_carving(self):
        if self._ocupado or not self.caminho_imagem:
            return
        pasta = QFileDialog.getExistingDirectory(
            self, "Escolha a pasta para guardar os ficheiros extraídos", os.getcwd()
        )
        if not pasta:
            return

        self.pasta_carving = pasta
        self.ficheiros_recuperados = []
        self._definir_ocupado(True, "A procurar assinaturas…")
        self._set_estado("A percorrer a imagem…", "#e3b341")
        self._log_main(
            "A procurar JPEG, PNG e PDF na imagem lógica completa; "
            "a pesquisa não se limita a blocos não alocados."
        )
        case_id, evidence_id = self._evidence_case_id, self._evidence_id
        self._start_worker(
            lambda: self._executar_carving(pasta, case_id, evidence_id),
            self._finalizar_carving,
        )

    def _executar_carving(self, pasta, case_id, evidence_id):
        sucesso, resultado = self.core.fazer_carving(pasta_saida=pasta)
        acao = "carving_completed" if sucesso else "carving_failed"
        detalhes = (
            {
                "parameters": {
                    "output_directory": pasta,
                    "max_files": 50,
                    "max_file_size_bytes": 128 * 1024 * 1024,
                    "signature_types": ["JPEG", "PNG", "PDF"],
                },
                "result": {
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
                    "file_count": len(resultado),
                },
            }
            if sucesso
            else {
                "parameters": {
                    "output_directory": pasta,
                    "max_files": 50,
                    "max_file_size_bytes": 128 * 1024 * 1024,
                    "signature_types": ["JPEG", "PNG", "PDF"],
                },
                "result": {"error": resultado},
            }
        )
        erro = self._registar_evento(case_id, evidence_id, acao, detalhes)
        if erro:
            return False, f"{resultado}; falha ao registar a auditoria: {erro}"
        return sucesso, resultado

    def _finalizar_carving(self, resultado):
        sucesso, recuperados = resultado
        self._definir_ocupado(False)
        if not sucesso:
            self._log_main(recuperados)
            self._set_estado("Falha no carving", "#ff7b72")
            return

        self.ficheiros_recuperados = recuperados
        self._set_estado(f"Carving concluído: {len(recuperados)} ficheiro(s)", "#3fb950")
        self._log_main(
            f"Carving concluído: {len(recuperados)} ficheiro(s) extraído(s) para "
            f"{self.pasta_carving}."
        )
        for item in recuperados[:20]:
            self._log_main(
                f"  - {item['tipo']} {item['nome']} | offset {item['offset']} "
                f"| {item['tamanho']} bytes"
            )
            if item.get("exif"):
                resumo = ", ".join(
                    f"{chave}: {valor}" for chave, valor in item["exif"].items()
                )
                self._log_main(f"    EXIF: {resumo}")
        if len(recuperados) > 20:
            self._log_main(f"  ... mais {len(recuperados) - 20} ficheiro(s).")
        self._log_main(
            "Nota: deteções por assinatura podem incluir dados alocados, falsos positivos "
            "ou ficheiros incompletos."
        )

    def iniciar_extracao_exif(self):
        if self._ocupado:
            return
        if not self._case_id:
            QMessageBox.warning(self, "Caso obrigatório", "Crie ou selecione um caso.")
            return
        caminho, _ = QFileDialog.getOpenFileName(
            self,
            "Selecione uma imagem para extrair metadados EXIF",
            self.pasta_carving or "",
            "Imagens (*.jpg *.jpeg *.png *.tif *.tiff);;Todos os ficheiros (*)",
        )
        if not caminho:
            return
        evidence_id = self._evidence_id if self._evidence_case_id == self._case_id else None
        self._definir_ocupado(True, "A ler metadados…")
        self._log_main(f"A extrair EXIF de {caminho}")
        self._start_worker(
            lambda: self._executar_extracao_exif(caminho, self._case_id, evidence_id),
            lambda resultado: self._finalizar_extracao_exif(caminho, resultado),
        )

    def _executar_extracao_exif(self, caminho, case_id, evidence_id):
        sucesso, resultado = self.core.extrair_exif(caminho)
        erro = self._registar_evento(
            case_id,
            evidence_id,
            "exif_extracted" if sucesso else "exif_extraction_failed",
            {
                "parameters": {"path": caminho},
                "result": {"metadata": resultado} if sucesso else {"error": resultado},
            },
        )
        if erro:
            return False, f"{resultado}; falha ao registar a auditoria: {erro}"
        return sucesso, resultado

    def _finalizar_extracao_exif(self, caminho, resultado):
        sucesso, metadados = resultado
        self._definir_ocupado(False)
        if not sucesso:
            self._log_main(metadados)
            QMessageBox.information(self, "Metadados EXIF", metadados)
            return
        self.metadados_exif[caminho] = metadados
        texto = "\n".join(f"{chave}: {valor}" for chave, valor in metadados.items())
        self._log_main(f"Metadados EXIF de {os.path.basename(caminho)}:")
        for linha in texto.splitlines():
            self._log_main(f"  {linha}")
        QMessageBox.information(self, "Metadados EXIF", texto)

    def iniciar_relatorio(self):
        if self._ocupado or not self.caminho_imagem:
            return
        caminho_pdf, _ = QFileDialog.getSaveFileName(
            self, "Guardar relatório forense", "relatorio_ena.pdf", "Documento PDF (*.pdf)"
        )
        if not caminho_pdf:
            return

        self._definir_ocupado(True, "A preparar relatório…")
        self._set_estado("A calcular hash para o relatório…", "#e3b341")
        self._log_main("A recalcular hashes e a preparar o relatório PDF…")
        parametros = (
            caminho_pdf,
            self.caminho_imagem,
            list(self.ficheiros_recuperados),
            dict(self.metadados_exif),
            self._evidence_case_id,
            self._evidence_id,
        )
        self._start_worker(
            lambda: self._executar_relatorio(*parametros),
            self._finalizar_relatorio,
        )

    def _executar_relatorio(
        self, caminho_pdf, caminho_imagem, recuperados, metadados_exif, case_id, evidence_id
    ):
        sucesso_hash, hashes = self.core.calcular_hash(caminho_imagem)
        if not sucesso_hash:
            erro = self._registar_evento(
                case_id,
                evidence_id,
                "report_generation_failed",
                {
                    "parameters": {"output_path": caminho_pdf},
                    "result": {"error": hashes},
                },
            )
            if erro:
                hashes += f" Falha ao registar a auditoria: {erro}"
            return False, hashes

        try:
            self.store.record_hashes(case_id, evidence_id, hashes["md5"], hashes["sha256"])
        except Exception as exc:
            return False, f"Não foi possível persistir os hashes calculados para o relatório: {exc}"

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
            {
                "parameters": {
                    "output_path": caminho_pdf,
                    "source_image": caminho_imagem,
                },
                "result": {
                    "md5": hashes["md5"],
                    "sha256": hashes["sha256"],
                },
            }
            if sucesso_pdf
            else {
                "parameters": {
                    "output_path": caminho_pdf,
                    "source_image": caminho_imagem,
                },
                "result": {"error": mensagem},
            }
        )
        erro = self._registar_evento(case_id, evidence_id, acao, detalhes)
        if erro:
            return False, f"{mensagem}; falha ao registar a auditoria: {erro}"
        return sucesso_pdf, mensagem

    def _finalizar_relatorio(self, resultado):
        sucesso, mensagem = resultado
        self._definir_ocupado(False)
        self._log_main(mensagem)
        if sucesso:
            self._set_estado("Relatório PDF criado", "#3fb950")
            QMessageBox.information(self, "Relatório PDF", mensagem)
        else:
            self._set_estado("Falha ao gerar relatório", "#ff7b72")
            QMessageBox.critical(self, "Relatório PDF", mensagem)

    def _registar_evento(self, case_id, evidence_id, action, details):
        if not case_id:
            return "não existe um caso selecionado"
        try:
            self.store.record_event(case_id, evidence_id, action, details)
        except Exception as exc:
            return str(exc)
        return None

    def closeEvent(self, evento):
        if self._ocupado:
            QMessageBox.warning(
                self,
                "Operação em curso",
                "Aguarde a operação terminar antes de fechar a aplicação.",
            )
            evento.ignore()
            return
        self.core.fechar()
        evento.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("E.N.A.")
    janela = AppEna()
    janela.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
