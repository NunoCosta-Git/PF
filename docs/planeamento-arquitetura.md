# Planeamento e arquitetura — texto para o relatório

## Planeamento

O desenvolvimento será incremental, orientado a riscos e dividido em fases com critérios de passagem. Cada funcionalidade deve ser implementada verticalmente — requisito, interface/API, persistência quando necessária, testes e documentação — antes de se avançar para a seguinte. Assim, funcionalidades ainda não validadas não são confundidas com suporte concluído e os defeitos são localizados antes de se acumularem na integração.

### Fase 0 — Fechar o âmbito e as decisões de arquitetura

**Trabalho:** aprovar a matriz de requisitos; classificar cada objetivo como essencial, desejável ou futuro; definir sistemas operativos/versões alvo, formatos de evidência, operador/utilizadores e significado de “aquisição”. A decisão de interface está tomada: a aplicação usa Qt através de PySide6.

**Porquê primeiro:** a escolha de Qt afeta a interface, o ciclo de eventos, o modelo de concorrência, os diálogos, a distribuição e as dependências. Declarar a decisão agora evita manter duas arquiteturas em paralelo. A fronteira entre aquisição física e análise de imagens já adquiridas também tem de ficar explícita, pois envolve riscos e critérios de teste distintos.

**Critério de saída:** requisitos com estado e critérios de aceitação aprovados; arquitetura e tecnologias descritas no relatório correspondem a uma decisão única; tarefas por fazer estão identificadas sem serem apresentadas como implementadas.

### Fase 1 — Consolidar a interface Qt/PySide6

**Trabalho:** validar a camada de apresentação PySide6, mantendo `ForenseCore` e `PersistenceStore` independentes da interface. Confirmar janela principal, seleção/criação de caso, abertura RAW/E01, navegação, hashing, carving, EXIF, relatório e consulta da auditoria. Usar sinais/slots e workers Qt (`QThread` ou `QThreadPool`) para operações longas, sem aceder a widgets fora da thread principal. Acrescentar testes da interface e confirmar que os fluxos existentes não regridem.

**Porquê nesta ordem:** a equipa decidiu que Qt é a interface final e o relatório já a apresenta como tecnologia do projeto. A migração aconteceu antes de construir módulos novos, evitando duplicar funcionalidades na interface antiga e na nova. Manter o núcleo e a persistência sem dependências gráficas reduz o risco e permite testar esses componentes sem iniciar a GUI.

**Critério de saída:** a aplicação arranca com PySide6 e executa todos os fluxos existentes; hashing e operações demoradas não bloqueiam a janela; testes do núcleo, persistência e interface passam; instalação limpa inclui PySide6 e não depende de CustomTkinter.

### Fase 2 — Consolidar o MVP e a integridade da evidência

**Trabalho:** manter abertura read-only de imagens existentes, hashing por streaming, navegação suportada, carving heurístico, EXIF e PDF; comparar hashes MD5/SHA-256 com uma referência introduzida pelo operador; associar resultados ao caso/evidência; persistir proveniência normalizada (versão da aplicação, parâmetros e resultado); corrigir falhas de persistência de forma visível. A comparação e a estrutura comum de proveniência dos eventos estão implementadas; falta validar manualmente os fluxos completos e a resposta a falhas de persistência.

**Porquê nesta ordem:** após a migração estabilizada, hashing e proveniência são a base para confiar nos resultados das fases posteriores. Parsers, indexação e relatórios sem uma referência consistente à evidência de origem tornam-se difíceis de reproduzir ou auditar.

**Critério de saída:** testes demonstram hashes de referência corretos, comparação igual/diferente, ausência de escrita nos bytes da imagem, erros visíveis e persistência de resultados e eventos com versão, parâmetros e resultado. Documentar expressamente que SQLite append-only com triggers não é proteção contra adulteração externa.

### Fase 3 — Validar leitura e sistemas de ficheiros com imagens de referência

**Trabalho:** criar ou selecionar imagens-fixture pequenas, legais e reproduzíveis com estruturas conhecidas; usar o harness opcional `tests/test_filesystem_fixtures.py` para testar deteção, navegação, tamanhos e estado alocado/não alocado para cada sistema de ficheiros que se queira declarar suportado (por exemplo NTFS, FAT32 e ext4). Separar o teste de listagem de entradas eliminadas da recuperação efetiva do seu conteúdo. O harness está implementado; falta executá-lo com fixtures reais e documentar os resultados por formato.

**Porquê antes de adicionar mais análise:** os parsers e a timeline dependem de leitura previsível e de metadados coerentes. Declarar suporte com base apenas na biblioteca não demonstra que o fluxo da aplicação funciona para aquele formato.

**Critério de saída:** para cada FS declarado, há fixture identificada, resultados esperados, teste de integração reproduzível e limitações registadas. Se o sistema não puder testar um FS, o suporte fica marcado como não validado.

### Fase 4 — Implementar aquisição de forma delimitada e segura

**Trabalho:** só depois de decidir o âmbito exato, implementar aquisição de fontes autorizadas para um destino de imagem definido (por exemplo RAW ou E01), registo de operador e tempos, erros/leituras parciais, hashes da origem e destino quando aplicável, verificação pós-aquisição e proteção contra escolha acidental do mesmo ficheiro como origem e destino. Se aquisição física for demasiado ampla para o projeto, integrar um fluxo de importação de imagem produzida por ferramenta externa e descrever corretamente essa fronteira.

**Porquê depois da fase de integridade:** aquisição é mais arriscada do que abrir uma imagem existente; requer critérios próprios para origem, destino, falha, capacidade, permissões e verificação. Não se deve apresentar uma cópia comum de ficheiro como aquisição forense segura.

**Critério de saída:** testes com fontes controladas confirmam conteúdo e hashes esperados, tratamento de erros e registo rastreável; não usar discos físicos reais como fixtures. Se este critério não for exequível, manter aquisição física fora do produto e declarar a limitação.

### Fase 5 — Desenvolver parsers de artefactos como módulos independentes

**Trabalho:** priorizar um parser de cada vez (por exemplo Windows Registry, EVTX ou logs Linux), definir formato/versões suportadas, extrair os campos necessários e preservar a referência de origem (evidência, caminho/offset, identificador do registo e timestamps/fuso horário quando disponíveis). Expor resultados por uma interface comum sem colocar lógica específica de parser no núcleo.

**Porquê antes da pesquisa/timeline:** a indexação e a timeline necessitam de resultados normalizados e com proveniência. Fazer primeiro os parsers permite validar a semântica dos dados antes de os consolidar numa vista agregada.

**Critério de saída:** cada parser tem fixtures de referência, casos válidos/inválidos, testes de regressão, versão suportada e rastreabilidade até à origem.

### Fase 6 — Pesquisa indexada e timeline

**Trabalho:** definir um modelo comum de resultado/artefacto; indexar campos explicitamente escolhidos e texto autorizado; implementar pesquisa filtrável e timeline com normalização de fuso horário, ordenação estável, proveniência e prevenção de duplicados. Medir tempo e uso de armazenamento em conjuntos de teste antes de aumentar a escala.

**Porquê nesta fase:** pesquisa e timeline dependem de parsers testados e de um esquema de proveniência estável. Implementá-las antes obrigaria a reindexar e migrar resultados quando cada parser mudasse.

**Critério de saída:** testes verificam termos e filtros esperados, ordenação temporal/fusos, ligação ao artefacto de origem e comportamento em casos sem dados ou com timestamps incompletos.

### Fase 7 — Análise de memória com Volatility 3

**Trabalho:** manter a análise RAM num módulo/adaptador separado do núcleo de imagens de disco; definir formatos de dump, sistemas/perfis suportados, plugins autorizados, configuração offline e forma de guardar saída estruturada e logs. Não executar plugins arbitrários como entrada não validada nem bloquear a interface durante a análise.

**Porquê depois dos fluxos de disco:** memória tem formatos, dependências, requisitos de ambiente e resultados diferentes. Isolá-la reduz o risco de tornar instável a abertura e análise de imagens já funcionais.

**Critério de saída:** dumps de referência documentados produzem resultados esperados; erros de perfil/plugin são explícitos; execução e resultados ficam associados ao caso e à versão/configuração da ferramenta.

### Fase 8 — Integração, validação multiplataforma e entrega

**Trabalho:** executar testes unitários e de integração em Windows e numa distribuição Linux definida; verificar instalação limpa, operação sem rede, responsividade, backup/restauro da base local, criação de relatórios e atualização de dependências. Registar versões exatas, comandos, resultados obtidos, limitações e evidências; atualizar o relatório final e preparar uma demonstração repetível.

**Porquê no fim e continuamente:** a validação cruzada cobre as combinações reais de GUI e dependências nativas, mas precisa de módulos suficientemente estáveis para que as falhas sejam atribuíveis. Smoke tests de cada fase continuam a ser necessários; esta fase não substitui testes durante o desenvolvimento.

**Critério de saída:** matriz de validação preenchida para cada sistema operativo suportado; nenhum objetivo é declarado concluído sem teste correspondente; documentação de instalação, utilização, backup/restauro e limitações está atualizada.

#### Regras de priorização e gestão de âmbito

1. Bloqueios de integridade, perda de dados ou falhas silenciosas têm prioridade sobre novas funcionalidades.
2. Em cada fase, selecionar primeiro um incremento pequeno com fixture e resultado esperado; evitar desenvolver vários parsers ou formatos em simultâneo.
3. Só iniciar uma fase dependente quando os critérios de saída da fase anterior estiverem demonstrados ou quando a exceção estiver registada e aceite.
4. Manter funções de hash e leitura em segundo plano; nunca escrever artefactos na imagem original.
5. Se o prazo não permitir concluir tudo, entregar o núcleo validado e apresentar fases não concluídas como trabalho futuro, não como funcionalidades simuladas.

O MVP atual constitui a base das Fases 1 e 2: abre imagens RAW/E01 já adquiridas, calcula hashes, tenta reconhecer sistemas de ficheiros, navega quando possível, procura assinaturas JPEG/PNG/PDF, extrai EXIF, gera PDF e guarda dados locais de casos. A verificação com hash de referência e os testes de integração completos por sistema de ficheiros continuam pendentes. O carving percorre a imagem lógica completa e não identifica por si só dados apagados; pode produzir falsos positivos ou ficheiros incompletos.

## Arquitetura proposta

A arquitetura segue camadas. A apresentação Qt/PySide6 recolhe ações e apresenta estado, ficheiros e resultados, comunicando com a camada de aplicação por sinais/slots. A camada de aplicação coordena tarefas em segundo plano com workers Qt e impede que operações demoradas bloqueiem a interface. O núcleo forense (`ForenseCore`) permanece independente da GUI, abre imagens em modo de leitura, comunica com o The Sleuth Kit através de `pytsk3`, reconhece sistemas de ficheiros/partições suportados e calcula hashes por blocos. A camada inicial de persistência usa SQLite local em `dados/ena.sqlite3` para casos, evidências, hashes e eventos de auditoria; os registos são append-only através da aplicação e de triggers, sem garantia contra adulteração externa do ficheiro. Os relatórios e parsers serão módulos independentes para permitir testar cada funcionalidade sem alterar o núcleo.

O fluxo de dados previsto é: seleção da imagem → validação do caminho e abertura read-only → cálculo de hashes → deteção do sistema de ficheiros → navegação e análise → carving por assinaturas e extração opcional de EXIF → exportação de relatório. A comparação com um hash de referência fornecido pelo operador ainda não está implementada. A imagem original não deve ser modificada; quaisquer artefactos extraídos e relatórios devem ser guardados numa área de trabalho separada.

## Tecnologias e justificação

- **Python:** permite reutilizar bibliotecas forenses e manter uma base de código comum em Windows e Linux.
- **PySide6 / Qt:** binding Qt usado na interface desktop atual.
- **The Sleuth Kit / `pytsk3`:** usado para ler imagens e analisar sistemas de ficheiros suportados, evitando implementar formatos de disco do zero.
- **`hashlib`:** biblioteca padrão usada para MD5 e SHA-256 em streaming.
- **`pyewf` (opcional):** adaptador para imagens E01; a disponibilidade e instalação devem ser verificadas separadamente em cada sistema operativo.
- **Pillow:** leitura de metadados EXIF em imagens compatíveis.
- **ReportLab:** criação local de relatórios PDF com paginação e tabelas.
- **`unittest`:** testes automatizados para hashing, abertura e comportamento quando o sistema de ficheiros não é reconhecido.

## Segurança, validação e limitações

A abertura read-only feita pela biblioteca não equivale a um bloqueador físico de escrita e não protege contra todos os riscos de aquisição de discos físicos. Por isso, o MVP deve trabalhar apenas sobre imagens já adquiridas, preservadas e armazenadas em suporte controlado. A validação académica deve usar imagens de teste conhecidas, comparar os resultados com valores de referência e registar sistema operativo, versão do Python, bibliotecas e passos executados. O projeto não deve afirmar conformidade com ISO/IEC 17025 nem admissibilidade judicial; pode documentar testes inspirados em boas práticas e explicitar que uma certificação exige um processo laboratorial mais amplo.

## Plano de testes

Os testes unitários verificam hashes conhecidos, ausência de alteração dos bytes da imagem RAW durante abertura/hash/listagem, carving de JPEG/PNG/PDF incluindo assinaturas que atravessam limites de bloco, offsets e bytes extraídos, EXIF conhecido, PDF gerado, mensagens de erro, imagens sem sistema de ficheiros reconhecido, persistência de casos/eventos e inicialização/estado básico da interface PySide6. Acrescentar teste de responsividade da GUI durante operações demoradas. Os testes de integração ainda devem usar e identificar imagens de referência com sistemas de ficheiros e estruturas de diretórios conhecidos. A suite atual foi executada em Windows neste workspace; a mesma bateria deve ser executada em Linux. Cada execução deve guardar os resultados, as versões do software, a imagem utilizada e qualquer divergência observada.

## Alinhamento com o relatório final

O relatório final descreve um âmbito mais amplo que o MVP existente. A interface já usa Qt/PySide6. Para evitar apresentar proposta como implementação, devem ser tratados como trabalho futuro até existirem código e testes próprios: aquisição de dispositivos, comparação com hash de referência introduzido pelo operador, análise RAM/Volatility, suporte comprovado a NTFS/FAT32/ext4, recuperação geral de ficheiros eliminados, parsers Registry/EVTX/logs Linux, indexação/pesquisa full-text, timeline, autenticação/controlo de acesso e garantias formais air-gapped. A implementação não inclui dfVFS.

No DOCX, atualizar também o diagrama/tecnologias para a implementação real e substituir os marcadores dos capítulos de desenvolvimento, testes, manutenção e conclusão. Registar o que foi testado efetivamente, incluindo sistema operativo, versão do Python e dependências; não declarar paridade Linux/Windows até executar a bateria nos dois sistemas. O campo “operador” é um dado de auditoria, não autenticação. Os triggers SQLite dificultam alterações acidentais via SQL normal, mas não protegem contra substituição/edição externa da base e não constituem cadeia de custódia inviolável.
