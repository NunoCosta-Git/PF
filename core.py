import hashlib
import os
import tempfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import pytsk3

try:
    import pyewf
except ImportError:
    pyewf = None


CHUNK_SIZE = 1024 * 1024
MAX_CARVED_FILE_SIZE = 128 * 1024 * 1024
CARVING_SIGNATURES = (
    {
        "tipo": "JPEG",
        "extensao": ".jpg",
        "inicio": b"\xff\xd8\xff",
        "fim": b"\xff\xd9",
        "tamanho_minimo": 64,
    },
    {
        "tipo": "PNG",
        "extensao": ".png",
        "inicio": b"\x89PNG\r\n\x1a\n",
        "fim": b"\x00\x00\x00\x00IEND\xaeB`\x82",
        "tamanho_minimo": 45,
    },
    {
        "tipo": "PDF",
        "extensao": ".pdf",
        "inicio": b"%PDF-",
        "fim": b"%%EOF",
        "tamanho_minimo": 32,
    },
)


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

    def _encontrar_assinatura(self, offset_inicial):
        """Procura a próxima assinatura sem carregar a imagem completa em RAM."""
        sobreposicao = max(len(item["inicio"]) for item in CARVING_SIGNATURES) - 1
        offset = offset_inicial
        pendente = b""

        while offset < self.tamanho_imagem:
            tamanho = min(CHUNK_SIZE, self.tamanho_imagem - offset)
            bloco = self.img.read(offset, tamanho)
            if not bloco:
                break

            dados = pendente + bloco
            base_offset = offset - len(pendente)
            encontrados = []
            for assinatura in CARVING_SIGNATURES:
                posicao = dados.find(assinatura["inicio"])
                if posicao >= 0:
                    encontrados.append((base_offset + posicao, assinatura))

            if encontrados:
                return min(encontrados, key=lambda item: item[0])

            pendente = dados[-sobreposicao:] if sobreposicao else b""
            offset += len(bloco)

        return None

    def _extrair_candidato(self, inicio, assinatura, pasta_saida, indice, limite_bytes):
        """Extrai um candidato até ao terminador, com limite e escrita em streaming."""
        prefixo = self.img.read(inicio, len(assinatura["inicio"]))
        if prefixo != assinatura["inicio"]:
            return None

        nome_base = f"recuperado_{indice:04d}_offset_{inicio:x}{assinatura['extensao']}"
        caminho_final = os.path.join(pasta_saida, nome_base)
        sufixo = 1
        while os.path.exists(caminho_final):
            caminho_final = os.path.join(
                pasta_saida,
                f"recuperado_{indice:04d}_offset_{inicio:x}_{sufixo}{assinatura['extensao']}",
            )
            sufixo += 1

        temporario = None
        try:
            ficheiro_completo = False
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=pasta_saida, prefix=".ena-", suffix=".part", delete=False
            ) as destino:
                temporario = destino.name
                destino.write(prefixo)
                total = len(prefixo)
                offset = inicio + len(prefixo)
                pendente = b""

                while total < limite_bytes and offset < self.tamanho_imagem:
                    tamanho = min(
                        CHUNK_SIZE,
                        limite_bytes - total,
                        self.tamanho_imagem - offset,
                    )
                    bloco = self.img.read(offset, tamanho)
                    if not bloco:
                        break

                    dados = pendente + bloco
                    indice_fim = dados.find(assinatura["fim"])
                    if indice_fim >= 0:
                        ate_fim = indice_fim + len(assinatura["fim"])
                        destino.write(dados[:ate_fim])
                        total += ate_fim
                        ficheiro_completo = True
                        break

                    margem = len(assinatura["fim"]) - 1
                    tamanho_seguro = max(0, len(dados) - margem)
                    if tamanho_seguro:
                        destino.write(dados[:tamanho_seguro])
                        total += tamanho_seguro
                    pendente = dados[tamanho_seguro:]
                    offset += len(bloco)

            if not ficheiro_completo or total < assinatura["tamanho_minimo"]:
                return None
            os.replace(temporario, caminho_final)
            temporario = None
            return {
                "tipo": assinatura["tipo"],
                "nome": os.path.basename(caminho_final),
                "caminho": caminho_final,
                "offset": inicio,
                "tamanho": total,
            }
        finally:
            if temporario and os.path.exists(temporario):
                os.remove(temporario)

    def fazer_carving(
        self,
        pasta_saida="carved",
        max_ficheiros=50,
        max_bytes_ficheiro=MAX_CARVED_FILE_SIZE,
    ):
        """Extrai JPEG, PNG e PDF por assinaturas, lendo a imagem em blocos.

        A pesquisa percorre a imagem lógica completa, e não apenas blocos
        não alocados; offsets e esta limitação são devolvidos para rastreabilidade.
        """
        if self.img is None:
            return False, "Abra uma imagem antes de iniciar o carving."
        if max_ficheiros < 1 or max_bytes_ficheiro < 1:
            return False, "Os limites de ficheiros e tamanho têm de ser positivos."

        try:
            pasta_saida = os.path.abspath(pasta_saida)
            os.makedirs(pasta_saida, exist_ok=True)
            if not os.path.isdir(pasta_saida):
                return False, "A pasta de saída não é um diretório válido."

            recuperados = []
            cursor = 0
            while cursor < self.tamanho_imagem and len(recuperados) < max_ficheiros:
                encontrado = self._encontrar_assinatura(cursor)
                if encontrado is None:
                    break

                inicio, assinatura = encontrado
                candidato = self._extrair_candidato(
                    inicio,
                    assinatura,
                    pasta_saida,
                    len(recuperados) + 1,
                    max_bytes_ficheiro,
                )
                if candidato:
                    if assinatura["tipo"] in ("JPEG", "PNG"):
                        sucesso_exif, metadados = self.extrair_exif(candidato["caminho"])
                        candidato["exif"] = metadados if sucesso_exif else {}
                    recuperados.append(candidato)
                    cursor = inicio + candidato["tamanho"]
                else:
                    cursor = inicio + len(assinatura["inicio"])

            return True, recuperados
        except Exception as exc:
            return False, f"Erro no carving: {exc}"

    def extrair_exif(self, caminho_ficheiro):
        """Extrai campos EXIF comuns e coordenadas GPS em graus decimais."""
        try:
            from PIL import ExifTags, Image

            with Image.open(caminho_ficheiro) as imagem:
                exif = imagem.getexif()
                if not exif:
                    return False, "A imagem não contém metadados EXIF."

                nomes = {
                    "Make": "Fabricante",
                    "Model": "Modelo",
                    "DateTime": "Data/hora",
                    "DateTimeOriginal": "Data/hora original",
                    "DateTimeDigitized": "Data/hora digitalizada",
                    "Software": "Software",
                    "ImageWidth": "Largura",
                    "ImageLength": "Altura",
                    "Orientation": "Orientação",
                }
                resultado = {}
                ids_por_nome = {nome: tag_id for tag_id, nome in ExifTags.TAGS.items()}
                for tag_id, nome in nomes.items():
                    valor = exif.get(ids_por_nome.get(tag_id))
                    if valor is not None:
                        resultado[nome] = str(valor)

                try:
                    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
                except (KeyError, AttributeError, TypeError):
                    gps = {}

                if gps:
                    gps_nomes = {ExifTags.GPSTAGS.get(chave, chave): valor for chave, valor in gps.items()}
                    latitude = self._coordenada_gps(
                        gps_nomes.get("GPSLatitude"), gps_nomes.get("GPSLatitudeRef")
                    )
                    longitude = self._coordenada_gps(
                        gps_nomes.get("GPSLongitude"), gps_nomes.get("GPSLongitudeRef")
                    )
                    if latitude is not None:
                        resultado["Latitude"] = f"{latitude:.7f}"
                    if longitude is not None:
                        resultado["Longitude"] = f"{longitude:.7f}"
                    altitude = gps_nomes.get("GPSAltitude")
                    if altitude is not None:
                        resultado["Altitude (m)"] = f"{float(altitude):.2f}"

                if not resultado:
                    return False, "Não foram encontrados campos EXIF relevantes."
                return True, resultado
        except Exception as exc:
            return False, f"Erro ao extrair EXIF: {exc}"

    @staticmethod
    def _coordenada_gps(coordenadas, referencia):
        if not coordenadas or len(coordenadas) != 3:
            return None

        def decimal(valor):
            return float(valor.numerator) / float(valor.denominator) if hasattr(valor, "denominator") else float(valor)

        graus, minutos, segundos = (decimal(valor) for valor in coordenadas)
        resultado = graus + minutos / 60 + segundos / 3600
        if referencia in ("S", "W"):
            resultado = -resultado
        return resultado

    def gerar_relatorio_pdf(
        self,
        caminho_saida,
        info_imagem=None,
        lista_ficheiros=None,
        hashes=None,
        recuperados=None,
        metadados_exif=None,
    ):
        """Gera um PDF com hashes, conteúdo listado, carving e limitações."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.platypus import (
                LongTable,
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                TableStyle,
            )

            ficheiros = lista_ficheiros or []
            hashes = hashes or {}
            recuperados = recuperados or []
            metadados_exif = metadados_exif or {}
            caminho_saida = os.path.abspath(caminho_saida)
            caminho_fonte = info_imagem or self.caminho_imagem or "Não indicado"

            fonte_normal, fonte_negrito = "Helvetica", "Helvetica-Bold"
            candidatos_fontes = (
                (Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf",
                 Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arialbd.ttf"),
                (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                 Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
            )
            for normal, negrito in candidatos_fontes:
                if normal.is_file() and negrito.is_file():
                    pdfmetrics.registerFont(TTFont("ENA-Regular", str(normal)))
                    pdfmetrics.registerFont(TTFont("ENA-Bold", str(negrito)))
                    fonte_normal, fonte_negrito = "ENA-Regular", "ENA-Bold"
                    break

            estilos = getSampleStyleSheet()
            estilos.add(ParagraphStyle(
                name="ENA_Title", parent=estilos["Title"], fontName=fonte_negrito,
                fontSize=18, leading=23, alignment=TA_CENTER, textColor=colors.HexColor("#17365D"),
            ))
            estilos.add(ParagraphStyle(
                name="ENA_Heading", parent=estilos["Heading2"], fontName=fonte_negrito,
                fontSize=12, leading=15, textColor=colors.HexColor("#17365D"), spaceBefore=12,
            ))
            estilos.add(ParagraphStyle(
                name="ENA_Body", parent=estilos["BodyText"], fontName=fonte_normal,
                fontSize=8.5, leading=12, wordWrap="CJK",
            ))
            estilos.add(ParagraphStyle(
                name="ENA_Small", parent=estilos["BodyText"], fontName=fonte_normal,
                fontSize=7, leading=9, wordWrap="CJK",
            ))

            documento = SimpleDocTemplate(
                caminho_saida,
                pagesize=A4,
                rightMargin=1.7 * cm,
                leftMargin=1.7 * cm,
                topMargin=1.7 * cm,
                bottomMargin=1.8 * cm,
                title="Relatório de análise forense — E.N.A.",
                author="E.N.A. — Ferramenta de análise forense",
            )
            conteudo = [
                Paragraph("Relatório de análise forense — E.N.A.", estilos["ENA_Title"]),
                Spacer(1, 0.35 * cm),
                Paragraph(
                    f"Gerado em: {escape(datetime.now().astimezone().isoformat(timespec='seconds'))}",
                    estilos["ENA_Body"],
                ),
                Paragraph(f"Imagem analisada: {escape(str(caminho_fonte))}", estilos["ENA_Body"]),
                Paragraph(f"Tamanho lógico: {self.tamanho_imagem:,} bytes", estilos["ENA_Body"]),
                Paragraph(
                    f"Sistema de ficheiros: {escape(self.sistema_ficheiros or 'Não identificado')}",
                    estilos["ENA_Body"],
                ),
                Paragraph("Integridade da evidência", estilos["ENA_Heading"]),
                Paragraph(f"MD5: {escape(str(hashes.get('md5', 'Não calculado')))}", estilos["ENA_Small"]),
                Paragraph(f"SHA-256: {escape(str(hashes.get('sha256', 'Não calculado')))}", estilos["ENA_Small"]),
                Paragraph("Conteúdo listado na raiz", estilos["ENA_Heading"]),
            ]

            linhas = [["Nome", "Tipo", "Tamanho (bytes)", "Estado"]]
            for entrada in ficheiros:
                linhas.append([
                    Paragraph(escape(str(entrada.get("nome", ""))), estilos["ENA_Small"]),
                    "Pasta" if entrada.get("diretorio") else "Ficheiro",
                    "—" if entrada.get("diretorio") else str(entrada.get("tamanho", 0)),
                    "Eliminado" if entrada.get("eliminado") else "Alocado",
                ])
            tabela = LongTable(linhas, colWidths=[8.0 * cm, 2.2 * cm, 3.0 * cm, 3.0 * cm], repeatRows=1)
            tabela.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), fonte_negrito),
                ("FONTNAME", (0, 1), (-1, -1), fonte_normal),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9d1d9")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6fa")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            conteudo.append(tabela)

            conteudo.append(Paragraph("Ficheiros encontrados por carving", estilos["ENA_Heading"]))
            conteudo.append(Paragraph(
                "A pesquisa por assinaturas percorreu a imagem lógica completa; não foi limitada "
                "a blocos não alocados. A presença de um ficheiro recuperado não prova, por si só, "
                "que estava eliminado. Podem existir falsos positivos e ficheiros truncados pelo limite configurado.",
                estilos["ENA_Body"],
            ))
            linhas_carving = [["Tipo", "Ficheiro", "Offset (bytes)", "Tamanho (bytes)", "EXIF/GPS"]]
            for item in recuperados:
                metadados = item.get("exif", {})
                resumo_exif = "; ".join(
                    f"{chave}: {valor}" for chave, valor in metadados.items()
                ) or "Sem EXIF relevante"
                linhas_carving.append([
                    item.get("tipo", ""),
                    Paragraph(escape(str(item.get("nome", ""))), estilos["ENA_Small"]),
                    str(item.get("offset", "")),
                    str(item.get("tamanho", "")),
                    Paragraph(escape(resumo_exif), estilos["ENA_Small"]),
                ])
            if len(linhas_carving) == 1:
                linhas_carving.append(["—", "Nenhum ficheiro extraído", "—", "—", "—"])
            tabela_carving = LongTable(
                linhas_carving,
                colWidths=[1.6 * cm, 4.3 * cm, 2.5 * cm, 2.5 * cm, 5.3 * cm],
                repeatRows=1,
            )
            tabela_carving.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), fonte_negrito),
                ("FONTNAME", (0, 1), (-1, -1), fonte_normal),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9d1d9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            conteudo.extend([
                tabela_carving,
            ])

            if metadados_exif:
                conteudo.append(Paragraph("Metadados EXIF analisados manualmente", estilos["ENA_Heading"]))
                for caminho, metadados in metadados_exif.items():
                    conteudo.append(Paragraph(escape(str(caminho)), estilos["ENA_Small"]))
                    for chave, valor in metadados.items():
                        conteudo.append(Paragraph(
                            f"{escape(str(chave))}: {escape(str(valor))}", estilos["ENA_Small"]
                        ))

            conteudo.extend([
                Spacer(1, 0.3 * cm),
                Paragraph(
                    "Nota: relatório gerado automaticamente por um protótipo académico. "
                    "Não constitui certificação ou validação pericial formal. Os hashes referem-se "
                    "ao conteúdo lógico da evidência lido pela aplicação.",
                    estilos["ENA_Small"],
                ),
            ])

            def rodape(canvas, doc):
                canvas.saveState()
                canvas.setFont(fonte_normal, 7)
                canvas.setFillColor(colors.HexColor("#6e7781"))
                canvas.drawString(1.7 * cm, 1.0 * cm, "E.N.A. — Relatório de análise (protótipo)")
                canvas.drawRightString(A4[0] - 1.7 * cm, 1.0 * cm, f"Página {doc.page}")
                canvas.restoreState()

            documento.build(conteudo, onFirstPage=rodape, onLaterPages=rodape)
            return True, f"Relatório PDF criado: {caminho_saida}"
        except Exception as exc:
            return False, f"Erro ao gerar PDF: {exc}"

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