# Levantamento de requisitos — E.N.A.

## Objetivo e âmbito

Desenvolver, no contexto académico, uma aplicação desktop de análise forense digital com objetivo de execução em Windows e Linux. A versão atual foi validada em Windows; a validação em Linux continua pendente. A solução organiza a análise de imagens previamente adquiridas; não substitui ferramentas de aquisição nem bloqueadores físicos de escrita.

O âmbito verificável da versão atual é um MVP de análise local de imagens RAW e E01 já adquiridas. O objetivo amplo descrito no relatório final — aquisição, análise de RAM, parsers de artefactos, pesquisa indexada e timeline — não deve ser apresentado como funcionalidade concluída. A matriz abaixo regista explicitamente essa diferença.

## Utilizadores

- **Analista/perito:** abre a imagem, calcula hashes, navega nos dados suportados e consulta os resultados registados.
- **Orientador/validador:** reproduz testes com imagens de referência e revê os resultados e limitações documentadas.

## Requisitos funcionais

| ID | Requisito | Prioridade | Estado |
|---|---|---|---|
| RF-01 | Abrir imagens RAW (`.dd`, `.raw`, `.img`) em modo de leitura. | Essencial | Implementado; a aplicação não adquire discos físicos |
| RF-02 | Calcular MD5 e SHA-256 por streaming e apresentar os resultados. | Essencial | Implementado; não compara automaticamente com um hash de referência fornecido pelo operador |
| RF-03 | Tentar reconhecer sistemas de ficheiros e partições suportados pelo `pytsk3`. | Essencial | Parcial; depende do suporte do backend e carece de fixtures de integração versionadas |
| RF-04 | Navegar em diretórios e apresentar nome, tipo, tamanho e estado alocado/eliminado. | Essencial | Implementado quando o FS é reconhecido; marcar eliminado não equivale a recuperar o conteúdo |
| RF-05 | Abrir imagens E01 segmentadas através de `libewf-python` (`pyewf`). | Desejável | Implementado e testado com ntfs1-gen2.E01 |
| RF-06 | Procurar assinaturas JPEG, PNG e PDF em blocos e guardar candidatos com offset e tamanho de origem. | Desejável | Implementado; pesquisa heurística na imagem lógica completa, não apenas em espaço não alocado |
| RF-07 | Extrair metadados EXIF comuns e coordenadas GPS de imagens compatíveis. | Desejável | Implementado com Pillow |
| RF-08 | Gerar relatório PDF com hashes, listagem da raiz, resultados de carving, EXIF e limitações. | Essencial, MVP | Implementado |
| RF-09 | Registar casos, evidências, operador, datas, hashes e ações de forma append-only. | Essencial | Implementado parcialmente: SQLite local e triggers contra UPDATE/DELETE; ainda sem proteção contra adulteração externa |
| RF-10 | Adicionar parsers (Registry, EVTX, logs Linux), timeline e pesquisa como módulos independentes. | Futuro | Por fazer; não consta do MVP executável |
| RF-11 | Comparar o hash calculado com um valor de referência fornecido/obtido na aquisição. | Essencial no objetivo amplo do relatório | Por fazer; atualmente os hashes são calculados e apresentados, sem fluxo de comparação |
| RF-12 | Adquirir imagens de disco e analisar imagens de memória com Volatility 3. | Futuro / fora do MVP | Por fazer; o projeto abre imagens existentes e não implementa aquisição nem análise RAM |

## Confronto com os objetivos do relatório final

| Declaração/objetivo no DOCX | Estado real no repositório | Ajuste recomendado ao relatório |
|---|---|---|
| Aplicação nativa Windows/Linux | Interface migrada para PySide6; dependências instaladas e suite testada em Windows neste workspace. Linux ainda não validado. | Descrever suporte pretendido e apresentar Linux como validação pendente, não como paridade demonstrada. |
| Aquisição, preservação e análise num único fluxo | Abre imagens já adquiridas; não adquire discos nem fornece bloqueio físico de escrita. | Substituir “aquisição” por “abertura/análise de imagens previamente adquiridas” na descrição do MVP. |
| Hash SHA-256 e comparação de integridade | Calcula MD5 e SHA-256; não recebe nem compara um hash original. | Distinguir cálculo de hash de verificação por comparação; declarar esta última como trabalho futuro até existir. |
| NTFS, FAT32, ext4 e ficheiros eliminados | `pytsk3` tenta reconhecer FS suportados; a suite não inclui imagens-fixture de integração para demonstrar cobertura dos três FS. A listagem assinala flags de não alocado, mas não recupera esses ficheiros por esse mecanismo. | Indicar exatamente os FS exercitados com imagens de referência e descrever o carving como heurística, não como recuperação geral de eliminados. |
| Parsing de artefactos, pesquisa indexada e timeline | Não implementados. | Mover para objetivos futuros ou implementar módulos e testes próprios antes de os apresentar como resultados. |
| Interface Qt, dfVFS e análise RAM com Volatility 3 | A interface foi migrada para PySide6. O código ainda não usa dfVFS nem Volatility. | Descrever PySide6 como implementado e manter dfVFS e Volatility como planeados até serem integrados e testados. |
| Controlo de acesso | O campo operador identifica quem foi indicado no caso, mas não existe autenticação nem autorização de utilizadores. | Não descrever o operador como controlo de acesso; registar a limitação ou implementar autenticação se for requisito avaliado. |
| Operação air-gapped | A análise é local e não requer serviços remotos; não existe teste formal de isolamento de rede. | Descrever como arquitetura offline por conceção, sem afirmar certificação/validação air-gapped. |
| Relatório completo de desenvolvimento, testes, manutenção e conclusão | Os capítulos 4–7 do DOCX ainda contêm instruções-modelo. | Substituir os marcadores por implementação efetiva, resultados reprodutíveis, limitações, manutenção/backup da base local e avaliação objetivo a objetivo; completar referências APA 7. |

## Requisitos não funcionais

- **RNF-01 — Integridade:** a análise não deve escrever na imagem de evidência; a origem deve ser preservada e os resultados devem ser reproduzíveis.
- **RNF-02 — Multiplataforma:** validar instalação, abertura, hashing e navegação em Windows e numa distribuição Linux definida pelo projeto.
- **RNF-03 — Responsividade:** hashing e operações potencialmente demoradas não devem bloquear a interface.
- **RNF-04 — Memória:** processar hashes em blocos; não carregar imagens completas em RAM.
- **RNF-05 — Operação offline:** as funções essenciais não podem depender de serviços cloud ou enviar evidências para a rede.
- **RNF-06 — Rastreabilidade:** cada resultado futuro deve identificar evidência, operação, versão do software e referência de origem sempre que possível.
- **RNF-07 — Honestidade de suporte:** não declarar suporte a um formato/sistema de ficheiros sem testes de referência documentados.
- **RNF-08 — Controlo de acesso:** não implementado; selecionar um operador no caso não autentica a identidade nem restringe ações.

## Critérios de aceitação do MVP

| # | Critério | Estado/evidência atual |
|---|---|---|
| 1 | Abrir uma imagem RAW válida sem a alterar. | Teste unitário abre, calcula hash e compara os bytes da origem antes/depois; não equivale a teste com bloqueador físico de escrita. |
| 2 | Calcular MD5 e SHA-256 iguais aos valores de referência. | Teste unitário compara com hashes de referência calculados sobre bytes conhecidos; a aplicação ainda não permite introduzir/comparar um hash de aquisição. |
| 3 | Manter a interface responsiva durante hashing e operações longas. | Hashing, navegação, carving, EXIF e relatório são executados em threads de trabalho; falta teste automatizado de responsividade da GUI. |
| 4 | Navegar num FS de teste suportado e distinguir diretórios/ficheiros. | Implementado no código; manter evidência de integração reproduzível com imagem-fixture e respetivas limitações antes de declarar cobertura por FS. |
| 5 | Se não houver FS reconhecido, informar sem impedir hashing. | Coberto por teste unitário com imagem RAW sem FS reconhecido. |
| 6 | Carving JPEG/PNG/PDF com offsets e limites documentados. | Coberto por testes unitários de conteúdo/offset, inclusive assinatura entre blocos; é heurística da imagem lógica inteira, não recuperação validada de eliminados. |
| 7 | Extrair EXIF conhecido e gerar PDF com resultados/limitações. | Coberto por testes unitários de EXIF e geração de PDF. |
| 8 | Executar os mesmos testes em Windows e Linux e guardar versões/resultados. | Windows validado neste workspace; Linux, imagem de integração versionada e registo formal de resultados ainda pendentes. |

O relatório final também apresenta objetivos além destes critérios (aquisição, memória, parsers, pesquisa e timeline). Esses objetivos devem permanecer identificados como não implementados/futuros, salvo se forem desenvolvidos e validados separadamente.
