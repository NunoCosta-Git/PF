# E.N.A. — Análise Forense Digital

Protótipo académico de uma aplicação desktop para abrir imagens forenses, calcular hashes e navegar nos ficheiros quando o sistema de ficheiros é reconhecido pelo The Sleuth Kit (`pytsk3`). A interface desktop usa Qt através de PySide6.

## Estado atual (MVP inicial)

- Abre imagens RAW (`.dd`, `.raw`, `.img`) em modo de leitura.
- Deteta sistema de ficheiros direto ou em partições quando suportado pelo `pytsk3`.
- Calcula MD5 e SHA-256 por streaming, sem carregar a imagem toda em memória.
- Lista diretórios e assinala entradas marcadas como eliminadas pelo sistema de ficheiros.
- Mantém hashing e operações de leitura fora da thread da interface.
- Abre imagens E01 através de `libewf-python` (que fornece o módulo `pyewf`).
- Procura assinaturas JPEG, PNG e PDF em blocos e extrai metadados EXIF/GPS de JPEGs recuperados.
- Gera relatórios PDF com hashes, lista da raiz, offsets/tamanhos do carving, EXIF e limitações.
- Regista casos, evidências, hashes e ações numa base SQLite local em `dados/ena.sqlite3`.
- Protege os registos persistidos contra UPDATE/DELETE pela aplicação e por triggers SQLite.

A imagem `teste.dd` existente no workspace não tem um sistema de ficheiros/tabela de partições reconhecido pelo backend testado. A aplicação consegue abri-la para hashing, mas não consegue mostrar ficheiros dessa imagem.

Antes de abrir uma imagem, cria ou seleciona um caso e indica o operador. A abertura, os hashes e as operações de análise ficam associados ao caso na base local `dados/ena.sqlite3`, criada automaticamente. A base contém caminhos de evidências e resultados de análise; mantém-na protegida e fora de cópias públicas. A imutabilidade ao nível da aplicação/SQLite não impede a alteração ou substituição do ficheiro por alguém com acesso ao sistema de ficheiros.

## Windows

1. Criar/ativar um ambiente virtual.
2. Instalar as dependências: `pip install -r requirements.txt` (inclui `libewf-python` para imagens E01).
3. Executar: `python interface.py`.
4. Executar os testes: `python -m unittest discover -s tests -v`.

Foi validado neste workspace com Python 3.13 e as dependências do ambiente `venv`. Seleciona `venv\Scripts\python.exe` como interpretador do VS Code ou usa diretamente esse executável nos comandos.
O suporte E01 foi testado com `ntfs1-gen2.E01` neste workspace.

## Linux

Instalar Python 3, `python3-venv` e as dependências de sistema necessárias para instalar `PySide6`, `pytsk3` e `libewf-python` na distribuição utilizada. Depois, criar um ambiente virtual, instalar `requirements.txt` e executar `python interface.py`. A instalação nativa das bibliotecas deve ser confirmada na versão de Linux alvo antes de declarar paridade entre plataformas.

## Limites importantes

O carving atual é heurístico: percorre a imagem lógica completa, não apenas blocos não alocados; pode encontrar ficheiros alocados, falsos positivos ou conteúdo incompleto, e limita cada candidato a 128 MiB. Não é recuperação avançada de ficheiros eliminados. Este protótipo também **não** faz aquisição de discos físicos, não implementa bloqueio físico de escrita nem uma cadeia de custódia criptograficamente inviolável, validação formal, análise de RAM, parsers de artefactos, indexação ou timeline. Não deve ser apresentado como ferramenta validada para uso probatório. A imagem deve ser uma cópia forense já adquirida, e os testes devem usar imagens de laboratório.

## Próximas fases

O plano recomendado é faseado para estabilizar a integridade antes de aumentar a complexidade:

1. **Consolidar a interface Qt/PySide6:** manter o núcleo forense e a persistência independentes da GUI e validar os fluxos migrados.
2. **Consolidar MVP/integridade:** comparar hashes com referência e completar proveniência persistida para cada operação.
3. **Validar sistemas de ficheiros:** testar NTFS/FAT32/ext4 com imagens-fixture e resultados conhecidos; separar listagem de eliminados de recuperação.
4. **Aquisição delimitada:** implementar aquisição verificada apenas se o âmbito e os recursos de teste forem definidos; caso contrário, manter importação de imagens externas.
5. **Parsers de artefactos:** adicionar Registry, EVTX ou logs Linux um a um, com testes e referência de origem.
6. **Pesquisa e timeline:** construir sobre artefactos normalizados e testados.
7. **Memória e entrega:** integrar Volatility 3 isoladamente e validar instalação, operação offline, backup/restauro e comportamento em Windows/Linux.

Cada fase tem critérios de conclusão, riscos e justificação em [docs/planeamento-arquitetura.md](docs/planeamento-arquitetura.md). Se o prazo limitar o âmbito, priorizar uma base pequena testada e identificar claramente o restante como trabalho futuro.

O relatório de projeto descreve também aquisição, análise RAM com Volatility 3, dfVFS e controlo de acesso. A interface agora usa Qt/PySide6; dfVFS, aquisição, RAM e controlo de acesso ainda não estão implementados. A análise começa a partir de imagens já adquiridas; “operador” não significa autenticação, e o uso local/offline ainda não foi validado por teste formal de isolamento de rede.

A proposta detalhada de requisitos, planeamento e arquitetura está em `docs/requisitos.md` e `docs/planeamento-arquitetura.md`.

Os passos reprodutíveis para configurar o ambiente e testar a aplicação, imagens E01, carving, EXIF e PDF em Windows estão em `docs/testes-windows.md`.
O texto técnico para as secções de desenvolvimento e testes do relatório está em `docs/desenvolvimento-carving-exif-relatorio.md`.
