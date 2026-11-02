# Guia de testes no Windows

Este guia valida o MVP com imagens de laboratório. Não uses discos físicos nem a única cópia de uma evidência.

## 1. Preparar o ambiente

Abre o PowerShell na pasta do projeto e ativa o ambiente virtual usado pela aplicação:

```powershell
.\venv\Scripts\Activate.ps1
```

Se a política de execução bloquear a ativação, não alteres a política do sistema: usa diretamente o executável do ambiente nos comandos seguintes.

Instala as dependências e confirma os módulos, usando sempre o mesmo Python:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -c "import customtkinter, pytsk3, pyewf, PIL, reportlab; print('Dependências OK')"
```

No VS Code, seleciona `venv\Scripts\python.exe` como interpretador do workspace. O projeto também pode ter um `.venv` diferente; se selecionares esse ambiente sem dependências, a aplicação pode falhar ao importar os módulos.

## 2. Testes automatizados

Executa a partir da raiz do projeto:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

O resultado esperado é `OK` para todos os testes. A suite verifica hashes conhecidos, carving de JPEG/PNG/PDF (incluindo assinatura dividida entre blocos), offset e conteúdo extraído, tags EXIF de referência, PDF válido, abertura RAW sem sistema de ficheiros e mensagens de erro.

## 3. Teste manual da interface e de E01

1. Inicia a aplicação: `.\venv\Scripts\python.exe .\interface.py`.
2. Escolhe **Abrir imagem de evidência** e seleciona um conjunto E01 de laboratório. Se a imagem tiver segmentos (`.E01`, `.E02`, …), mantém todos os segmentos na mesma pasta.
3. Confirma no registo que a imagem foi aberta e que o sistema de ficheiros foi reconhecido, se suportado.
4. Confirma que a lista mostra os nomes, tipos e tamanhos. Abre uma pasta com duplo clique e regressa com **Acima**.
5. Seleciona **Calcular MD5 + SHA-256** e confirma que os dois valores aparecem no registo. Compara-os com hashes calculados por uma segunda ferramenta independente, aplicada à mesma representação dos dados.
6. Escolhe uma pasta de trabalho separada da evidência e inicia **Carving JPEG / PNG / PDF**. Regista quantos candidatos foram extraídos, os offsets e os tamanhos; confirma que os ficheiros exportados abrem quando aplicável.
7. Usa **Extrair EXIF de imagem** num JPEG de laboratório com fabricante/modelo conhecidos e, se existir, GPS de teste. Confirma os campos no registo da aplicação.
8. Seleciona **Gerar relatório PDF** e guarda-o na pasta de resultados. Confirma que inclui caminho/tamanho, hashes, listagem da raiz quando disponível, carving, EXIF e notas de limitação.
9. Fecha a aplicação e volta a abri-la antes de testar outra imagem.

Uma imagem RAW de bytes aleatórios pode abrir para hashing e, ainda assim, não ter tabela de partições nem sistema de ficheiros reconhecível. Nesse caso, a mensagem de limitação é o resultado esperado; não é uma falha do hashing. O carving percorre a imagem lógica completa e não distingue ainda espaço alocado de não alocado: resultados são candidatos por assinatura, não prova de eliminação ou de recuperação completa. Cada candidato tem um limite de 128 MiB.

## 4. Registo dos resultados

Para cada execução, anota no relatório: data/hora e fuso horário, operador, Windows e arquitetura, versão de Python, versões das dependências, nome e tamanho da imagem de teste, hashes de referência, passos realizados, resultado esperado, resultado obtido, divergências e limitações. Usa imagens de teste com resultados conhecidos e guarda o relatório fora da pasta da evidência.

## 5. Limites deste teste

Estes passos verificam a execução funcional do protótipo; não demonstram certificação ISO/IEC 17025, conformidade integral com o NIST CFTT/SWGDE, admissibilidade judicial ou proteção por bloqueador físico de escrita. A aplicação atual analisa ficheiros de imagem e não adquire discos físicos.
