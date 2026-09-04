# Contribuindo com skills

[English](../../../CONTRIBUTING.md) | [Русский](../ru/CONTRIBUTING.md) | [Español](../es/CONTRIBUTING.md) | [Français](../fr/CONTRIBUTING.md) | [Deutsch](../de/CONTRIBUTING.md) | Português (Brasil) | [日本語](../ja/CONTRIBUTING.md) | [Italiano](../it/CONTRIBUTING.md) | [한국어](../ko/CONTRIBUTING.md) | [简体中文](../zh-CN/CONTRIBUTING.md) | [Türkçe](../tr/CONTRIBUTING.md) | [Polski](../pl/CONTRIBUTING.md) | [Українська](../uk/CONTRIBUTING.md)

Esta é uma tradução para português do Brasil. Em caso de divergência, a [versão em inglês](../../../CONTRIBUTING.md) é a referência oficial.

Este repositório é a fonte canônica das skills reutilizáveis de kolabse. Mantenha
cada skill focada, portável, com autoria identificável e instalável de forma independente.

## Antes de adicionar uma skill

1. Identifique a fonte canônica. Decida se este repositório será responsável pela
   skill ou se espelhará outra fonte.
2. Comprove o direito de redistribuir cada instrução, script, referência e recurso
   copiado. Contribuições originais são aceitas sob a licença Apache-2.0 do
   repositório, salvo indicação explícita em contrário. Preserve arquivos de
   licença de terceiros, avisos de direitos autorais, atribuições e avisos de
   modificação; registre sua expressão SPDX no catálogo. Não publique material
   de terceiros cuja licença não esteja esclarecida.
3. Pesquise descrições existentes para identificar sobreposição nos critérios de
   acionamento. Amplie uma skill existente quando o fluxo de trabalho tiver o
   mesmo propósito; adicione uma nova quando ela tiver um critério de acionamento
   e um critério de conclusão úteis de forma independente.
4. Escolha um nome em minúsculas, iniciado por verbo, separado por hífens e com
   no máximo 63 caracteres.

Critério de conclusão: responsabilidade, proveniência, licença, escopo e nome da
skill são conhecidos antes de copiar os arquivos.

## Acompanhe uma candidata até a implementação

Quando uma skill nova ou ampliada se originar de uma Issue do GitHub, mantenha
essa Issue como item de trabalho canônico até que a implementação esteja
representada na branch principal.

1. Registre a Issue de origem no pull request de implementação.
2. Inclua `Closes #<issue-number>` no corpo do pull request. Se a alteração não
   deve fechar a Issue, declare explicitamente o motivo e o encaminhamento previsto.
3. Após o merge, inspecione a Issue em vez de presumir que a palavra-chave de
   fechamento foi aplicada. Se ela permanecer aberta inesperadamente, feche-a
   como concluída com links para o pull request de implementação e, quando
   disponível, para a release.
4. Se a implementação for rejeitada, substituída ou apenas parcialmente entregue,
   deixe um comentário explicativo e use o encaminhamento correspondente para a
   Issue; nunca informe que uma candidata foi concluída apenas porque existiu
   uma branch ou um pull request.

Critério de conclusão: cada candidata implementada é rastreável desde a Issue de
origem até o pull request integrado, e a Issue tem um estado final verificado,
com uma explicação da implementação ou da não conclusão.

## Adicione ou migre a skill

1. Sincronize os repositórios de origem e destino sem sobrescrever trabalho local.
2. Crie `skills/<skill-name>/SKILL.md`. Mantenha apenas `name` e `description` no
   cabeçalho YAML e faça o nome da pasta corresponder a `name`.
3. Coloque auxiliares determinísticos em `scripts/`, detalhes destinados ao agente
   em `references/`, materiais de saída em `assets/` e metadados opcionais de UI
   em `agents/openai.yaml`. Mantenha a configuração do projeto fora da pasta da skill.
4. Escreva etapas no imperativo com critérios de conclusão verificáveis. Mantenha
   o corpo com menos de 500 linhas; apresente detalhes específicos de cada
   ramificação do fluxo por meio de referências diretas.
5. Adicione uma entrada a `skill-catalog.json`:
   - `name` e `path` relativo ao repositório;
   - exatamente uma `category` principal, seguindo a ordem de prioridade documentada;
   - uma ou mais `tags` controladas para fase do ciclo de vida, escopo,
     comportamento e integrações;
   - `status`: `experimental`, `stable` ou `deprecated`;
   - identificadores do GitHub em `maintainers`;
   - `platforms` compatíveis;
   - expressão SPDX em `license`;
   - tipo de proveniência, fonte, nomes anteriores e repositório canônico.
   Valide os valores de categoria e tags com
   `schemas/skill-catalog.schema.json`; o status de maturidade é independente de ambos.
6. Adicione a skill ao catálogo do README com seu propósito, notas de instalação
   e ação obrigatória na primeira execução.
7. Adicione testes para scripts determinísticos e prompts realistas que devem e
   não devem acionar a skill. Armazene pelo menos três casos positivos e três
   negativos próximos em `evals/<skill-name>.json` e referencie esse arquivo em
   `skill-catalog.json` como `trigger_evals`.

Para uma skill migrada, preserve seu histórico no catálogo mesmo depois que este
repositório se tornar canônico. Para uma skill incorporada de terceiros, registre
uma revisão imutável da fonte, mantenha sua licença e seus avisos na pasta da
skill e separe alterações upstream de patches locais. Confirme a compatibilidade
de licenças antes de combinar conteúdo de terceiros com conteúdo Apache-2.0.

Critério de conclusão: o leitor pode determinar a origem da skill, quem é
responsável por ela, sua licença, onde ela funciona e como validá-la.

## Contrato de configuração

Toda skill configurável declara um objeto `configuration` em
`skill-catalog.json` e segue estas regras:

- `configure` é um array argv, pode ser repetido com segurança, preserva conteúdo
  não relacionado do projeto e informa ausência de alterações em uma segunda
  execução idêntica;
- `status` é somente leitura, aceita JSON legível por máquina, termina com código
  zero apenas quando a configuração declarada está presente e válida e nunca
  imprime segredos;
- os escopos de projeto e usuário são explícitos; a configuração permanece fora
  do diretório da skill instalada;
- configurações JSON e YAML têm uma versão inteira positiva, um JSON Schema
  incluído que descreve o documento decodificado e um comando de migração que
  bloqueia a operação em caso de falha ou incerteza;
- texto gerenciado usa marcadores pareados e específicos da skill, rejeita
  marcadores malformados ou duplicados e não reescreve texto fora de seu bloco.
- skills sem estado usam o formato `none`, expõem apenas um comando de status
  somente leitura e não devem inventar artefatos de configuração fictícios.

Os comandos são armazenados como arrays, não como strings de shell. Use
marcadores como `<project-root>` para valores fornecidos por quem chama e nunca
inclua credenciais em um comando do catálogo. Mantenha as etapas de migração
incrementais e idempotentes; rejeite uma versão mais recente desconhecida em vez
de tentar adivinhar como rebaixá-la.

Critério de conclusão: repetir configure produz uma saída idêntica byte a byte
onde já existe configuração, status não faz escritas, as migrações preservam
entradas compatíveis e os testes cobrem configuração ausente, malformada, atual e legada.

## Preserve o caminho de atualização das instalações de agentes

- Mantenha idênticas, em uma release, as versões de `.codex-plugin/plugin.json`,
  `.claude-plugin/plugin.json`, `skill-catalog.json.collection_version` e de cada
  `skills/*/collection-metadata.json`.
- Teste a instalação por cópia e uma atualização desde a release anterior mais
  antiga compatível usando a versão fixada da CLI `skills`, tanto para `codex`
  quanto para `claude-code`.
- Instale globalmente a coleção para cada agente. Mantenha a configuração, as regras
  gerenciadas e os ajustes intencionais do projeto fora das pastas de skills instaladas.
  Nunca permita que um atualizador crie silenciosamente configuração para uma
  skill não utilizada.
- Detecte cópias antigas no projeto após uma atualização e mostre um aviso de
  centralização. A migração deve planejar sem gravar, verificar as cópias globais
  antes da remoção, preservar skills não relacionadas e a configuração, manter um
  backup recuperável e exigir aprovação vinculada ao plano revisado.
- Documente as migrações necessárias e as limitações de reversão no README e no
  changelog. Considere o rebaixamento de configuração não suportado, salvo se testado.
- Preserve entradas não relacionadas ao alterar o marketplace pessoal. Aplique
  um sufixo de invalidação de cache à cópia instalada do plugin e exija uma nova
  tarefa Codex após a ativação.

Critério de conclusão: quem usa uma instalação de agente pode identificar as
versões instaladas, atualizar, migrar configurações existentes, diagnosticar
versões misturadas e reinstalar uma tag anterior sem depender de conhecimento
privado do repositório.

## Preserve o comportamento entre agentes

Mantenha portáveis as instruções e os auxiliares compartilhados de `SKILL.md`.
Codex continua sendo o padrão das interfaces de linha de comando existentes;
um destino explícito Claude Code usa `.claude/skills`, `CLAUDE.md` e
`/skill-name`. Não substitua APIs de configuração `.agents` existentes apenas
para renomeá-las para outro agente de destino.

Trate `agents/openai.yaml` como metadados de UI da OpenAI e `.codex-plugin` como
empacotamento do Codex. O empacotamento do Claude pertence a `.claude-plugin`;
nenhum manifesto pode substituir silenciosamente a validação do outro. Quando
um agente não tiver uma capacidade, como a enumeração de tarefas do Codex Desktop,
informe que essa operação delimitada não é suportada, preservando o subconjunto portável.

Critério de conclusão: ambas as instalações globais de agentes contêm conteúdos idênticos
de skills, suas estruturas nativas de regras de projeto e skills são respeitadas,
os padrões do Codex permanecem inalterados e as evidências de smoke tests das
instalações identificam explicitamente ambos os agentes.

## Componha skills por capacidade

Declare nomes curtos de capacidades em `provides`, pré-requisitos obrigatórios
em `requires` e integrações não bloqueantes em `optional_integrations`. Adicione
uma composição nomeada da coleção apenas para um fluxo recorrente com pelo menos
duas skills. Seus `required_steps` são ordenados; `optional_steps` são executados
somente quando o projeto ou usuário tiver habilitado sua capacidade.

Não copie o fluxo de trabalho de uma skill para outra. Invoque a skill exigida,
use seu resultado de conclusão observável e pare quando uma capacidade
obrigatória estiver indisponível. Notificações ou registros opcionais nunca
devem transformar a operação principal em um falso sucesso nem ocultar sua falha.

Critério de conclusão: cada capacidade obrigatória tem um provedor, as etapas
da composição referenciam skills existentes uma única vez e a ordem tem um teste
de integração ou um critério de conclusão executável.

## Gerencie o status do ciclo de vida

- Mantenha uma skill nova ou substancialmente reformulada como `experimental`
  até que seus metadados, auxiliares determinísticos, testes multiplataforma,
  corpus de acionamento de desenvolvimento, teste prospectivo independente,
  smoke test de instalação por cópia e conjunto reservado de avaliação de release
  tenham passado. Requisitos que não se aplicam, como scripts incluídos em um
  fluxo apenas textual, podem ser registrados como não aplicáveis.
- Marque uma skill como `stable` somente em uma release versionada da coleção.
  Adicione `stable_since` com a versão dessa release. Estável significa que as
  entradas documentadas, os locais de configuração, os limites de segurança e o
  comportamento da CLI permanecerão compatíveis na versão principal atual da
  coleção ou receberão orientações de migração.
- Marque uma skill como `deprecated` antes de removê-la. Indique sua substituta
  suportada ou o caminho de migração na skill e no changelog e mantenha-a por
  pelo menos uma versão menor (minor), salvo se um problema urgente de segurança
  exigir remoção antecipada.

Critério de conclusão: o status do ciclo de vida tem respaldo em validação
observável e comunica uma expectativa clara de compatibilidade.

## Preserve a proveniência instalada

Trate um nome conhecido de skill apenas como candidato, nunca como identidade
da coleção. Correlacione a fonte do arquivo de lock externo com o
`collection-metadata.json` instalado. Normalize as formas de URL do GitHub
suportadas para `https://github.com/kolabse/skills`; verifique fontes locais de
desenvolvimento por seu manifesto de plugin, catálogo e conteúdo da skill
solicitada, sem depender do nome do diretório do checkout.

Bloqueie a operação diante de uma skill de mesmo nome de outra fonte ou de
metadados contraditórios. Mantenha explícita a adoção legada e permita-a somente
quando a própria fonte do lock tiver sido verificada; uma adoção bem-sucedida
deve terminar com metadados atuais e um diagnóstico saudável após a atualização.

Critério de conclusão: status expõe a classificação de proveniência, update
seleciona apenas skills verificadas (ou legadas adotadas explicitamente) e os
testes cobrem colisões de fonte, referências de release, checkouts locais
renomeados e instalações legadas.

## Mantenha inspecionável a automação das instalações de agentes

Mantenha `plan` somente leitura: ele não deve invocar instaladores, migrações ou
operações de rede. Publique JSON Schemas versionados para os dados de plano e
resultado e diferencie estados inalterado, atualizado, migrado, ignorado,
bloqueado e falhou sem analisar a saída da CLI destinada a humanos.

Limite a descoberta global às raízes documentadas de lock e instalação. Não
vasculhe o diretório pessoal em busca de possíveis instalações. Aplique as
mesmas regras de proveniência, seleção explícita e diagnóstico após atualização
no escopo global.

O bootstrap independente deve verificar o checksum do arquivo antes da extração,
verificar a proveniência de build do GitHub antes da execução, rejeitar entradas
de arquivo com travessia de diretórios ou links simbólicos, usar um diretório
temporário e propagar o código de saída do gerenciador. Exija uma opção explícita
de modo degradado para execução offline sem atestação.

Critério de conclusão: os schemas são analisáveis, a simulação mantém fixtures
idênticas byte a byte, as fixtures globais cobrem estruturas suportadas e
ambíguas e o smoke test de bootstrap passa em todos os sistemas operacionais
de CI suportados.

## Valide a alteração

Execute:

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py --agent codex
python scripts/smoke_install.py --agent claude-code
```

Exercite o corpus de acionamento com um agente real, incluindo o caminho de
primeira execução da skill. As verificações estruturais de CI mantêm o corpus
completo, mas não substituem a observação da invocação pelo modelo. Inclua os
prompts e o resultado observado no pull request.

Para a avaliação de acionamento de toda a coleção, prepare uma suíte cega e
pontue as observações do seletor:

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

Os seletores podem escolher várias skills ou nenhuma. Não exponha ao seletor
arquivos de avaliação de origem, rótulos esperados, justificativas dos autores,
falhas suspeitas ou relatórios anteriores. Registre a identidade do provedor e
do modelo nos metadados das previsões, mantenha as previsões brutas junto às
evidências de revisão e inspecione cada falso positivo e falso negativo antes
de alterar uma descrição. Uma pontuação maior não é motivo suficiente para
ampliar um critério de acionamento se isso tornar fluxos próximos ambíguos.

Trate `evals/release-holdout-vN.json` como evidência de release que só admite
acréscimos. Não leia nem execute o conjunto reservado ativo enquanto ajusta
descrições. As versões existentes desse conjunto são imutáveis: crie `vN+1`,
atualize o nome, o caminho e o digest canônico no catálogo e retenha todas as
versões publicadas. Execute o conjunto reservado ativo somente depois que as
descrições candidatas estiverem congeladas e compare seu relatório com uma
baseline gerada com a mesma versão do conjunto e a mesma configuração de seletor.
Nunca compare relatórios com digests de asserções diferentes. Após a release,
retenha o relatório aceito em `evals/baselines/` e atualize o ponteiro da baseline
no catálogo; arquivos de baseline são evidências de release e não devem ser
reescritos. Quando o seletor não for determinístico, use um número ímpar de pelo
menos três execuções cegas independentes e compare o agregado por voto majoritário.
Não repita uma observação individual até que ela passe nem descarte observações
válidas de falha.

Critério de conclusão: todos os comandos passam em cada sistema operacional
suportado e a lista de verificação do pull request contém evidências para a skill afetada.

## Proteja a cadeia de release

- Fixe cada GitHub Action externa em um SHA completo de commit e mantenha sua
  versão de release em um comentário. Deixe o Dependabot propor atualizações de
  SHA sujeitas a revisão.
- Conceda a cada workflow somente as permissões de `GITHUB_TOKEN` necessárias.
- Gere os arquivos de release com `scripts/build_release.py`; verifique
  `SHA256SUMS` antes de enviar os artefatos.
- Publique atestações de artefatos do GitHub para cada artefato de release e
  verifique-as com `gh attestation verify <artifact> --repo kolabse/skills`.
- Nunca substitua um artefato de release existente. Uma reexecução do workflow
  deve verificar que os bytes publicados são idênticos ou falhar.
- Mantenha tags de versão imutáveis. Publique uma correção como nova versão, em
  vez de mover uma tag existente ou substituir seu commit de origem.

Critério de conclusão: a tag aponta para o commit revisado, os artefatos enviados
correspondem a `SHA256SUMS` e as dependências dos workflows são referências imutáveis.
