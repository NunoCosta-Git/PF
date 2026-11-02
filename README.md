# E.N.A. — Análise Forense Digital

Protótipo académico de uma aplicação desktop multiplataforma para abrir imagens forenses, calcular hashes e navegar nos ficheiros quando o sistema de ficheiros é reconhecido pelo The Sleuth Kit (`pytsk3`). A interface usa CustomTkinter.

## Estado atual (MVP inicial)

- Abre imagens RAW (`.dd`, `.raw`, `.img`) em modo de leitura.
- Deteta sistema de ficheiros direto ou em partições quando suportado pelo `pytsk3`.
- Calcula MD5 e SHA-256 por streaming, sem carregar a imagem toda em memória.
- Lista diretórios e assinala entradas marcadas como eliminadas pelo sistema de ficheiros.
- Mantém hashing e operações de leitura fora da thread da interface.
- Abre imagens E01 através de `libewf-python` (que fornece o módulo `pyewf`).
- Procura assinaturas JPEG, PNG e PDF em blocos e extrai metadados EXIF/GPS de JPEGs recuperados.
- Gera relatórios PDF com hashes, lista da raiz, offsets/tamanhos do carving, EXIF e limitações.

A imagem `teste.dd` existente no workspace não tem um sistema de ficheiros/tabela de partições reconhecido pelo backend testado. A aplicação consegue abri-la para hashing, mas não consegue mostrar ficheiros dessa imagem.

## Windows

1. Criar/ativar um ambiente virtual.
2. Instalar as dependências: `pip install -r requirements.txt` (inclui `libewf-python` para imagens E01).
3. Executar: `python interface.py`.
4. Executar os testes: `python -m unittest discover -s tests -v`.

Foi validado neste workspace com Python 3.13 e as dependências do ambiente `venv`. O ambiente `.venv` também existe, mas está vazio; selecionar `venv` como interpretador do VS Code ou usar o caminho do Python desse ambiente.
No Windows, a aplicação tenta localizar automaticamente os scripts Tcl/Tk junto da instalação base do Python. O suporte E01 foi testado com `ntfs1-gen2.E01` neste workspace.

## Linux

Instalar Python 3, `python3-venv` e as dependências de sistema necessárias para compilar/instalar `pytsk3` e `libewf-python` na distribuição utilizada. Depois, criar um ambiente virtual, instalar `requirements.txt` e executar `python interface.py`. A instalação nativa das bibliotecas deve ser confirmada na versão de Linux alvo antes de declarar paridade entre plataformas.

## Limites importantes

O carving atual é heurístico: percorre a imagem lógica completa, não apenas blocos não alocados; pode encontrar ficheiros alocados, falsos positivos ou conteúdo incompleto, e limita cada candidato a 128 MiB. Não é recuperação avançada de ficheiros eliminados. Este protótipo também **não** faz aquisição de discos físicos, não implementa bloqueio físico de escrita, cadeia de custódia persistente, validação formal, análise de RAM, parsers de artefactos, indexação ou timeline. Não deve ser apresentado como ferramenta validada para uso probatório. A imagem deve ser uma cópia forense já adquirida, e os testes devem usar imagens de laboratório.

## Próximas fases

1. Distinguir blocos alocados e não alocados e validar recuperação contra imagens de referência antes de lhe chamar recuperação de apagados.
2. Persistência de casos e cadeia de custódia append-only, com operador, data/hora, ação e hashes.
3. Testes com imagens de referência conhecidas em Windows e Linux; relatório de validação e registo de versões.
4. Parsers adicionais (por exemplo EVTX/Registry), timeline e pesquisa, cada um com testes de regressão e proveniência.

A proposta detalhada de requisitos, planeamento e arquitetura está em `docs/requisitos.md` e `docs/planeamento-arquitetura.md`.

Os passos reprodutíveis para configurar o ambiente e testar a aplicação, imagens E01, carving, EXIF e PDF em Windows estão em `docs/testes-windows.md`.
O texto técnico para as secções de desenvolvimento e testes do relatório está em `docs/desenvolvimento-carving-exif-relatorio.md`.
