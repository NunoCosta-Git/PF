# Planeamento e arquitetura — texto para o relatório

## Planeamento

O desenvolvimento será organizado em quatro fases. Na primeira fase será fechado o âmbito do MVP e serão definidos os requisitos funcionais, os requisitos de integridade e os critérios de aceitação. Na segunda fase será implementado o fluxo base de abertura de imagem, cálculo de hashes e navegação, mantendo as operações longas fora da interface gráfica. Na terceira fase serão realizados testes com imagens de referência em Windows e Linux, registando versões, resultados esperados e obtidos e limitações. Na quarta fase serão priorizadas as extensões — persistência de casos e cadeia de custódia, relatório, parsers de artefactos e timeline — com testes próprios antes da integração.

A prioridade inicial é demonstrar um fluxo pequeno e verificável: abrir uma imagem RAW/E01, calcular MD5/SHA-256, consultar o sistema de ficheiros quando suportado, procurar assinaturas JPEG/PNG/PDF, extrair EXIF e exportar um relatório PDF. A pesquisa por assinaturas é uma heurística aplicada à imagem lógica completa; não identifica por si só se os dados encontrados estão eliminados e pode produzir falsos positivos ou ficheiros incompletos. Aquisição física, análise de memória, carving avançado e validado, indexação em larga escala e inteligência artificial ficam fora do MVP.

## Arquitetura proposta

A aplicação segue uma arquitetura em camadas. A camada de apresentação, implementada com CustomTkinter, recolhe ações do utilizador e apresenta estado, ficheiros e resultados. A camada de aplicação coordena tarefas em segundo plano e impede que operações demoradas bloqueiem a interface. O núcleo forense (`ForenseCore`) abre imagens em modo de leitura, comunica com o The Sleuth Kit através de `pytsk3`, reconhece sistemas de ficheiros/partições suportados e calcula hashes por blocos. Uma camada de persistência, prevista para uma fase posterior, guardará casos, evidências, eventos de auditoria e resultados numa base de dados local. Os relatórios e parsers serão módulos independentes para permitir testar cada funcionalidade sem alterar o núcleo.

O fluxo de dados previsto é: seleção da imagem → validação do caminho e abertura read-only → cálculo/verificação de hashes → deteção do sistema de ficheiros → navegação e análise → carving por assinaturas e extração opcional de EXIF → exportação de relatório. A imagem original não deve ser modificada; quaisquer artefactos extraídos e relatórios devem ser guardados numa área de trabalho separada.

## Tecnologias e justificação

- **Python:** permite reutilizar bibliotecas forenses e manter uma base de código comum em Windows e Linux.
- **CustomTkinter:** fornece a interface desktop atual com baixo custo de implementação.
- **The Sleuth Kit / `pytsk3`:** usado para ler imagens e analisar sistemas de ficheiros suportados, evitando implementar formatos de disco do zero.
- **`hashlib`:** biblioteca padrão usada para MD5 e SHA-256 em streaming.
- **`pyewf` (opcional):** adaptador para imagens E01; a disponibilidade e instalação devem ser verificadas separadamente em cada sistema operativo.
- **Pillow:** leitura de metadados EXIF em imagens compatíveis.
- **ReportLab:** criação local de relatórios PDF com paginação e tabelas.
- **`unittest`:** testes automatizados para hashing, abertura e comportamento quando o sistema de ficheiros não é reconhecido.

## Segurança, validação e limitações

A abertura read-only feita pela biblioteca não equivale a um bloqueador físico de escrita e não protege contra todos os riscos de aquisição de discos físicos. Por isso, o MVP deve trabalhar apenas sobre imagens já adquiridas, preservadas e armazenadas em suporte controlado. A validação académica deve usar imagens de teste conhecidas, comparar os resultados com valores de referência e registar sistema operativo, versão do Python, bibliotecas e passos executados. O projeto não deve afirmar conformidade com ISO/IEC 17025 nem admissibilidade judicial; pode documentar testes inspirados em boas práticas e explicitar que uma certificação exige um processo laboratorial mais amplo.

## Plano de testes

Os testes unitários verificam hashes conhecidos, carving de JPEG/PNG/PDF incluindo assinaturas que atravessam limites de bloco, offsets e bytes extraídos, EXIF conhecido, PDF gerado, mensagens de erro e imagens sem sistema de ficheiros reconhecido. Os testes de integração devem usar imagens de referência com sistemas de ficheiros identificados e estruturas de diretórios conhecidas. A mesma bateria deve ser executada em Windows e Linux. Cada execução deve guardar os resultados, as versões do software, a imagem utilizada e qualquer divergência observada.
