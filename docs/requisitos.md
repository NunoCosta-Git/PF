# Levantamento de requisitos — E.N.A.

## Objetivo e âmbito

Desenvolver, no contexto académico, uma aplicação desktop de análise forense digital compatível com Windows e Linux. A solução organiza a análise de imagens previamente adquiridas; não substitui ferramentas de aquisição nem bloqueadores físicos de escrita.

## Utilizadores

- **Analista/perito:** abre a imagem, verifica os hashes, navega nos dados suportados e regista observações.
- **Orientador/validador:** reproduz testes com imagens de referência e revê os resultados e limitações documentadas.

## Requisitos funcionais

| ID | Requisito | Prioridade | Estado |
|---|---|---|---|
| RF-01 | Abrir imagens RAW (`.dd`, `.raw`, `.img`) em modo de leitura. | Essencial | Implementado |
| RF-02 | Calcular MD5 e SHA-256 por streaming e apresentar os resultados. | Essencial | Implementado |
| RF-03 | Tentar reconhecer sistemas de ficheiros e partições suportados pelo `pytsk3`. | Essencial | Parcial |
| RF-04 | Navegar em diretórios e apresentar nome, tipo, tamanho e estado alocado/eliminado. | Essencial | Implementado para FS reconhecido |
| RF-05 | Abrir imagens E01 segmentadas através de `libewf-python` (`pyewf`). | Desejável | Implementado e testado com ntfs1-gen2.E01 |
| RF-06 | Procurar assinaturas JPEG, PNG e PDF em blocos e guardar candidatos com offset e tamanho de origem. | Desejável | Implementado; pesquisa heurística na imagem lógica completa, não apenas em espaço não alocado |
| RF-07 | Extrair metadados EXIF comuns e coordenadas GPS de imagens compatíveis. | Desejável | Implementado com Pillow |
| RF-08 | Gerar relatório PDF com hashes, listagem da raiz, resultados de carving, EXIF e limitações. | Essencial, MVP | Implementado |
| RF-09 | Registar casos, evidências, operador, datas, hashes e ações de forma append-only. | Essencial, fase seguinte | Por fazer |
| RF-10 | Adicionar parsers (Registry, EVTX, logs Linux), timeline e pesquisa como módulos independentes. | Futuro | Por fazer |

## Requisitos não funcionais

- **RNF-01 — Integridade:** a análise não deve escrever na imagem de evidência; a origem deve ser preservada e os resultados devem ser reproduzíveis.
- **RNF-02 — Multiplataforma:** validar instalação, abertura, hashing e navegação em Windows e numa distribuição Linux definida pelo projeto.
- **RNF-03 — Responsividade:** hashing e operações potencialmente demoradas não devem bloquear a interface.
- **RNF-04 — Memória:** processar hashes em blocos; não carregar imagens completas em RAM.
- **RNF-05 — Operação offline:** as funções essenciais não podem depender de serviços cloud ou enviar evidências para a rede.
- **RNF-06 — Rastreabilidade:** cada resultado futuro deve identificar evidência, operação, versão do software e referência de origem sempre que possível.
- **RNF-07 — Honestidade de suporte:** não declarar suporte a um formato/sistema de ficheiros sem testes de referência documentados.

## Critérios de aceitação do MVP

1. Abrir uma imagem RAW válida sem escrita na origem.
2. Calcular hashes MD5 e SHA-256 iguais aos valores de referência.
3. Manter a interface responsiva durante o hashing.
4. Navegar num sistema de ficheiros de teste suportado e distinguir diretórios/ficheiros.
5. Quando não houver sistema de ficheiros reconhecido, apresentar essa limitação sem impedir o hashing.
6. Encontrar e extrair assinaturas JPEG/PNG/PDF de uma imagem de teste, anotando offsets e limites; confirmar a limitação de pesquisa em espaço alocado e não alocado.
7. Extrair tags EXIF de uma imagem com metadados conhecidos e gerar um PDF legível com hashes, resultados e limitações.
8. Executar os mesmos testes em Windows e Linux e guardar resultados, versões e imagens de teste utilizadas.
