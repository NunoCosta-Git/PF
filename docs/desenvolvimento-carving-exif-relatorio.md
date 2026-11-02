# Texto para o relatório — carving, EXIF e relatório PDF

## 4.3 Pesquisa por assinaturas e análise de metadados

Foi implementada uma funcionalidade experimental de carving por assinaturas para JPEG, PNG e PDF. A aplicação lê a imagem em blocos, identifica padrões de início e procura o terminador correspondente para extrair candidatos para uma pasta de resultados separada. Cada resultado regista tipo, nome, offset e tamanho na imagem lógica, permitindo localizar a origem dos bytes. A leitura em blocos evita carregar a evidência completa na memória; os ficheiros temporários são substituídos pelo resultado final apenas depois da extração terminar. Para limitar consumo de espaço, cada candidato tem um limite configurável, com valor predefinido de 128 MiB.

Esta implementação é uma prova de conceito e **não** realiza ainda carving exclusivamente em espaço não alocado. A pesquisa percorre toda a imagem lógica, podendo detetar dados alocados, falsos positivos, dados fragmentados ou ficheiros truncados pelo limite. Assim, um resultado não demonstra que o ficheiro foi eliminado nem que foi recuperado integralmente. A validação do protótipo deve comparar cada candidato com os dados de referência e registar as limitações observadas; a recuperação de ficheiros eliminados exigirá, numa fase posterior, correlacionar os offsets com os blocos não alocados do sistema de ficheiros e tratar fragmentação.

Para os JPEG e PNG encontrados, ou selecionados manualmente, a aplicação tenta obter campos EXIF comuns — fabricante, modelo, datas e software — e coordenadas GPS quando presentes. A ausência de metadados é apresentada como tal; os dados EXIF são valores declarados no próprio ficheiro e não constituem, isoladamente, prova da localização ou do momento em que a imagem foi criada.

## 4.4 Relatório de análise

O módulo de relatório gera localmente um PDF paginado com a identificação da imagem, tamanho lógico, sistema de ficheiros reconhecido, hashes MD5/SHA-256, listagem disponível na raiz, candidatos do carving com offsets e tamanhos, metadados EXIF recolhidos e limitações do protótipo. O PDF é guardado pelo utilizador numa pasta separada da evidência. Os hashes são recalculados no momento da geração para reduzir o risco de apresentar um valor desatualizado. O documento é um resumo automático dos resultados e não uma certificação, validação laboratorial ou parecer pericial.

## 5. Registo de testes — modelo

Preencher os resultados efetivamente observados em cada execução. Usar imagens de laboratório com resultados esperados conhecidos e guardar a versão da aplicação, sistema operativo, Python e dependências.

| Teste | Evidência/dados | Resultado esperado | Resultado observado |
|---|---|---|---|
| Hash MD5/SHA-256 | Ficheiro pequeno com conteúdo conhecido | Ambos os hashes coincidem com o cálculo independente | Automatizado: passou |
| Carving dos três formatos | Fixture de teste JPEG, PNG e PDF, com assinatura JPEG atravessada pelo limite de bloco | Extrair os bytes exatos e indicar os offsets de origem | Automatizado: passou |
| Carving E01 | `ntfs1-gen2.E01`, paragem no limite de cinco resultados | Extrair candidatos suportados, registar offset/tamanho e manter a interface utilizável | Execução técnica: cinco candidatos; inclui JPEG e PDF. Esta execução não prova recuperação completa nem validação de ficheiros eliminados |
| EXIF | JPEG com fabricante/modelo de referência | Identificar os campos inseridos no fixture | Automatizado: passou |
| Relatório PDF | Imagem de laboratório com hashes | Criar ficheiro PDF que inicia com assinatura `%PDF-` | Automatizado: passou; também gerado após o carving E01 |
| Interface Windows | Abrir imagem, navegar, carving, EXIF e exportar PDF | Concluir as operações sem bloquear a janela | Preencher após ensaio manual local |

Os testes automatizados são funcionais e usam fixtures sintéticas; não substituem validação com conjuntos de referência independentes, revisão por outro examinador ou validação de laboratório segundo procedimentos aplicáveis.
