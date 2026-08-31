# kolabse/skills

[English](../../../README.md) | [Русский](../ru/README.md) | [Español](../es/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | Português (Brasil) | [日本語](../ja/README.md) | [Italiano](../it/README.md) | [한국어](../ko/README.md) | [简体中文](../zh-CN/README.md) | [Türkçe](../tr/README.md)

Esta é uma tradução para português do Brasil. Em caso de divergência, a [versão em inglês](../../../README.md) é a referência oficial.

Skills reutilizáveis para agentes, mantidas por kolabse.

Licenciado sob a [Licença Apache 2.0](../../../LICENSE). Copyright 2026 kolabse.

## Sumário

- [Instale skills](#instale-skills)
  - [Instale pelos marketplaces Git](#instale-pelos-marketplaces-git)
- [Atualize as skills instaladas](#atualize-as-skills-instaladas)
  - [Execute sem clonar o repositório](#execute-sem-clonar-o-repositório)
  - [Inspecione instalações globais](#inspecione-instalações-globais)
- [Instale ou atualize um plugin Codex de desenvolvimento local](#instale-ou-atualize-um-plugin-codex-de-desenvolvimento-local)
- [Skills disponíveis](#skills-disponíveis)
  - [Desenvolvimento e qualidade de código](#desenvolvimento-e-qualidade-de-código)
    - [`develop-with-test-first-evidence`](#develop-with-test-first-evidence-experimental)
    - [`review-code-changes`](#review-code-changes-experimental)
    - [`diagnose-software-defects`](#diagnose-software-defects-experimental)
    - [`resolve-git-conflicts`](#resolve-git-conflicts-experimental)
  - [Repositórios e entrega de alterações](#repositórios-e-entrega-de-alterações)
    - [`synchronize-git-repositories`](#synchronize-git-repositories)
    - [`verify-before-push`](#verify-before-push)
    - [`coordinate-code-documentation-repositories`](#coordinate-code-documentation-repositories-experimental)
    - [`execute-configured-gitflow-releases`](#execute-configured-gitflow-releases-experimental)
    - [`execute-verified-development-lifecycle`](#execute-verified-development-lifecycle-experimental)
  - [Conhecimento e continuidade do projeto](#conhecimento-e-continuidade-do-projeto)
    - [`maintain-work-log`](#maintain-work-log)
    - [`maintain-project-digest`](#maintain-project-digest-experimental)
    - [`sync-project-context`](#sync-project-context)
  - [Coordenação e comunicação](#coordenação-e-comunicação)
    - [`orchestrate-agent-work`](#orchestrate-agent-work-experimental)
    - [`synchronize-team-skills`](#synchronize-team-skills-experimental)
    - [`notify-via-telegram`](#notify-via-telegram)
  - [Infraestrutura e operações](#infraestrutura-e-operações)
    - [`operate-yandex-cloud`](#operate-yandex-cloud)
  - [Evolução da coleção de skills](#evolução-da-coleção-de-skills)
    - [`discover-skill-candidates`](#discover-skill-candidates-experimental)
    - [`release-skill-collection`](#release-skill-collection)
- [Composições suportadas](#composições-suportadas)
- [Adicione uma skill](#adicione-uma-skill)
- [Verifique uma release](#verifique-uma-release)

## Instale skills

Instale uma ou mais skills no projeto atual com a CLI multiagente
[`skills`](https://skills.sh):

```shell
npx skills@latest add kolabse/skills
```

A CLI descobre as pastas em `skills/`, permite selecionar quais skills instalar
e as copia para os agentes de programação selecionados. Ela é um instalador
externo; este repositório não publica nem executa um pacote npm próprio.

Usuários do Codex também podem pedir a `$skill-installer` que instale uma skill
deste repositório, por exemplo, a partir de:

```text
https://github.com/kolabse/skills/tree/main/skills/operate-yandex-cloud
```

Escolha explicitamente o agente de destino para uma instalação não interativa:

```shell
npx skills@1.5.22 add kolabse/skills --agent codex --copy -y
npx skills@1.5.22 add kolabse/skills --agent claude-code --copy -y
```

Para instalar no projeto, peça ao seu agente: "Instale as skills selecionadas e
inicialize os padrões de projeto ausentes sem substituir nossas regras existentes."
Após a conclusão do instalador externo, inicialize as regras Git para seu agente:

```shell
python .agents/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent codex --apply --yes --json
python .claude/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent claude-code --apply --yes --json
```

Convenções ausentes assumem os padrões `feature/`, `bugfix/`, `release/`, `hotfix/`
e os tipos de commit `feat`, `fix`, `refactor`, `docs`, `test`, `chore`. Prefixos,
papéis de branches e formatos de commit explícitos do projeto continuam tendo
precedência. Nenhuma branch persistente ou hook Git é criado. Atualizações
gerenciadas no escopo de projeto aplicam essa mesma inicialização às skills
relevantes; atualizações não confirmadas apenas a planejam.

Em uma instalação no escopo de projeto, inicialize imediatamente o contrato do
ciclo de vida quando seus padrões observáveis forem suficientes (use o caminho
do seu agente):

```shell
python .agents/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent codex --apply --yes --json
python .claude/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent claude-code --apply --yes --json
```

Instalações de marketplace/plugin são globais e não têm uma raiz de projeto
ativa; por isso, a skill faz essa mesma inicialização no primeiro uso em um projeto.

Codex descobre skills de projeto em `.agents/skills/` e as invoca como
`$skill-name`. Claude Code as descobre em `.claude/skills/` e as invoca como
`/skill-name`. As instruções das skills e os scripts incluídos são compartilhados;
os arquivos de regras específicos de cada agente de destino e a sintaxe de
invocação são selecionados na configuração.

O repositório também é empacotado como o plugin `kolabse-skills`, composto apenas
de skills, para ChatGPT/Codex e Claude Code. Todas as pastas em `skills/` são
incluídas. A instalação multiagente com `npx skills` continua disponível
independentemente dos dois formatos de plugin.

### Instale pelos marketplaces Git

Usuários do Codex podem registrar o marketplace do repositório e instalar a
coleção completa com:

```shell
codex plugin marketplace add kolabse/skills --ref main
codex plugin add kolabse-skills@kolabse
```

Atualize o snapshot Git e reinstale a versão atual do plugin com:

```shell
codex plugin marketplace upgrade kolabse
codex plugin add kolabse-skills@kolabse
```

Usuários do Claude Code podem registrar o mesmo repositório e instalar o plugin com:

```shell
claude plugin marketplace add kolabse/skills
claude plugin install kolabse-skills@kolabse
```

Atualize-o explicitamente com `claude plugin marketplace update kolabse` ou
habilite a atualização automática do marketplace no Claude Code. Inicie uma nova
sessão do agente após instalar ou atualizar para que ele descubra o conjunto atual
de skills.

Os catálogos dos marketplaces são
[`.agents/plugins/marketplace.json`](../../../.agents/plugins/marketplace.json) e
[`.claude-plugin/marketplace.json`](../../../.claude-plugin/marketplace.json).
Os conteúdos de seus plugins são descritos por
[`.codex-plugin/plugin.json`](../../../.codex-plugin/plugin.json) e
[`.claude-plugin/plugin.json`](../../../.claude-plugin/plugin.json). Ambos os
catálogos obtêm o repositório canônico `kolabse/skills` a partir de `main`; o
versionamento das releases continua sendo definido pelos manifestos dos plugins.

Os materiais de divulgação pública são mantidos junto ao código-fonte:
[suporte](SUPPORT.md), [política de privacidade](PRIVACY.md),
[termos de uso](TERMS.md) e o
[pacote reproduzível de submissão aos marketplaces](../../../docs/marketplace-submissions/).
A publicação em um diretório oficial continua sendo uma ação revisada dos
mantenedores; instalar pelos marketplaces Git não exige aprovação de diretório.

Claude Code pode carregar diretamente uma release extraída ou um checkout
confiável durante testes com `claude --plugin-dir <collection-root>`. Para uso
normal pessoal ou de projeto, prefira o marketplace Git ou o comando explícito
`npx skills ... --agent claude-code` acima. Claude Code lê `CLAUDE.md`, não
`AGENTS.md`; quando um projeto já tem regras compartilhadas em `AGENTS.md`, um
`CLAUDE.md` mínimo contendo `@AGENTS.md` preserva um único documento canônico de regras.

## Atualize as skills instaladas

A CLI `skills` registra a fonte GitHub e um hash de conteúdo em
`skills-lock.json`. Atualize todas as instalações do projeto a partir de sua
fonte registrada:

```shell
npx skills@1.5.22 update -p -y
```

Atualize uma skill ou as instalações globais com:

```shell
npx skills@1.5.22 update verify-before-push -p -y
npx skills@1.5.22 update -g -y
```

Um lock de `kolabse/skills` sem qualificação acompanha a branch padrão do
repositório; ele não fixa uma release da coleção. Não edite arquivos copiados em
`.agents/skills/`, pois uma atualização pode substituí-los. As configurações de
projeto e usuário permanecem fora das pastas de skills instaladas.

A partir de um checkout clonado ou arquivo de release, atualize e migre a
configuração de projeto suportada em uma única operação explícita:

```shell
python scripts/manage_installed_skills.py update --project-path . --yes --migrate
python scripts/manage_installed_skills.py doctor --project-path . --json
```

Pré-visualize a seleção exata sem invocar o instalador externo nem alterar a configuração:

```shell
python scripts/manage_installed_skills.py plan --project-path . --json
```

O plano informa a identidade da fonte, as versões atual e de destino, a
proveniência, os candidatos à migração e as ações `update`, `unchanged`,
`adopt-and-update` ou `blocked`. Seu schema é `schemas/manager-plan.schema.json`.
Adicione `--json` a `update`; os resultados de atualização e migração seguem
`schemas/manager-result.schema.json`.

Sem nomes informados, o gerenciador identifica as skills kolabse instaladas a
partir do lock do projeto e passa esses nomes explicitamente à CLI externa;
skills de projeto não relacionadas nunca fazem parte da atualização. Atualizações
globais exigem nomes explícitos de skills da coleção. Atualizações de projeto
terminam com o mesmo diagnóstico que bloqueia em caso de falha ou incerteza de
`doctor`. Quando `execute-verified-development-lifecycle` faz parte de uma
atualização de projeto, o gerenciador também inicializa sua configuração ausente
quando os fatos do projeto são suficientes e retorna um resultado de configuração
`created`, `configured` ou `blocked`.

Adicione `--include-user-config` somente quando a configuração de usuário do
Telegram também deve ser migrada. `status` e `doctor` são somente leitura.
`migrate` altera apenas arquivos de configuração já existentes; não configura
skills não utilizadas. Cada skill instalada inclui `collection-metadata.json`,
de modo que `status` informa sua versão da coleção mesmo que o formato do lock
externo não tenha campo de versão. Ele também informa `provenance_status`:
`verified` exige tanto metadados da coleção quanto uma fonte de lock canônica
do GitHub ou local verificada pelo conteúdo; `legacy-unverified` identifica uma
instalação anterior aos metadados; `mismatch` nunca é atualizado. Um checkout pode
ser renomeado porque sua identidade local vem do manifesto do plugin, do catálogo
e do conteúdo das skills, não do nome do diretório.

Adote uma instalação anterior à v1.2 sem metadados somente depois de revisar a
fonte informada:

```shell
python scripts/manage_installed_skills.py status --project-path . --json
python scripts/manage_installed_skills.py update --project-path . --yes --adopt-legacy
```

A opção de adoção não legitima arquivos arbitrários: a fonte já deve ser
normalizável para `kolabse/skills` ou passar pela validação de checkout local,
e o diagnóstico normal após a atualização deve verificar os metadados instalados.
A CLI externa não atualiza locks de desenvolvimento `sourceType: local` no
próprio local. O gerenciador trata essa ausência de ação da CLI como falha;
adicione novamente essas skills a partir de sua fonte local com as seleções
originais de `--skill` e `--agent`.

### Execute sem clonar o repositório

Baixe `scripts/bootstrap_update.py` de uma release confiável ou deste
repositório; deixe que ele identifique a release estável mais recente, verifique
o ZIP da release com `SHA256SUMS` e a proveniência de build do GitHub e execute
o gerenciador a partir de uma extração temporária isolada:

```shell
python bootstrap_update.py doctor --json
python bootstrap_update.py plan --json
python bootstrap_update.py update --yes --migrate --json
```

Use `--release v1.15.0` para fixar uma versão. O bootstrap exige `gh` para verificar
a atestação e remove seu diretório temporário ao terminar. Para um cache offline,
forneça tanto `--offline-archive` quanto `--offline-checksums`. A verificação de
proveniência continua obrigatória quando `gh` consegue acessar o GitHub.
`--allow-unattested-offline` é um modo degradado explícito: ele verifica apenas o
checksum em cache e só deve ser usado para artefatos transferidos por um canal
confiável de forma independente. Reverta selecionando uma release anterior e
usando o procedimento de reversão existente; as migrações de configuração
continuam sendo somente para frente.

### Inspecione instalações globais

O estado global suportado é deliberadamente limitado ao lock compartilhado v3
`~/.agents/.skill-lock.json`. Os conteúdos instalados ficam em `~/.agents/skills`
para Codex e em `~/.claude/skills` para Claude Code. O gerenciador não vasculha
outros diretórios do usuário. Codex continua sendo o padrão; passe
`--agent claude-code` para a estrutura de conteúdo do Claude:

```shell
python scripts/manage_installed_skills.py status --scope global --json
python scripts/manage_installed_skills.py doctor --scope global --json
python scripts/manage_installed_skills.py plan verify-before-push --scope global --json
python scripts/manage_installed_skills.py update verify-before-push --scope global --yes --json
python scripts/manage_installed_skills.py status --scope global --agent claude-code --json
```

Use `--global-root` para inspeção somente leitura de uma estrutura compatível
de teste ou explicitamente realocada. Raízes realocadas não podem ser atualizadas,
pois a CLI externa não consegue selecioná-las como destino. Formatos de lock
desconhecidos são informados sem alterações.

Para reverter os arquivos das skills, primeiro faça backup da configuração de
projeto/usuário e reinstale a tag da release necessária com as mesmas skills e
agentes de destino usados na instalação original, por exemplo:

```shell
npx skills@1.5.22 add kolabse/skills@v1.1.0 --skill verify-before-push --agent codex --copy -y
```

As migrações de configuração são somente para frente, salvo quando uma release
documentar explicitamente um rebaixamento. Restaurar arquivos de skills mais
antigos não rebaixa a configuração; restaure o backup de configuração
correspondente quando a release anterior não conseguir ler o formato mais recente.

## Instale ou atualize um plugin Codex de desenvolvimento local

Para desenvolver plugins localmente, crie ou atualize a entrada padrão do
marketplace pessoal, copie o plugin para o diretório local de plugins, adicione
um sufixo de invalidação de cache do Codex e ative-o:

```shell
python scripts/install_personal_plugin.py --activate
```

O instalador preserva outras entradas do marketplace pessoal e não edita o
manifesto do repositório. Esse é um caminho alternativo de desenvolvimento, não
a instalação normal pelo marketplace Git. Execute-o novamente após atualizar o
checkout e inicie uma nova tarefa Codex para carregar as skills atualizadas.
Use `--json` para registrar a versão instalada, o caminho do plugin, o caminho
do marketplace e o nome do marketplace.

## Skills disponíveis

As skills estáveis e as adições experimentais são identificadas em
`skill-catalog.json`. Seus caminhos de configuração voltados ao projeto, limites
de segurança e interfaces de comando documentadas seguem a política de
compatibilidade em [CONTRIBUTING.md](CONTRIBUTING.md).

Cada entrada do catálogo agora declara seu escopo de configuração, comando de
status JSON somente leitura, capacidades, pré-requisitos e integrações opcionais.
Skills com estado também declaram um comando de configuração idempotente;
configurações JSON/YAML versionadas publicam um JSON Schema e um comando de
migração junto à skill.

O catálogo é agrupado por seu propósito principal para o usuário, na ordem de
prioridade apresentada abaixo. Cada skill tem exatamente uma categoria principal.
Tags independentes descrevem sua fase do ciclo de vida, escopo, comportamento e
integrações; o status de maturidade permanece independente. As atribuições
oficiais legíveis por máquina e o vocabulário controlado ficam em
[`skill-catalog.json`](../../../skill-catalog.json), validado com
[`schemas/skill-catalog.schema.json`](../../../schemas/skill-catalog.schema.json).

Os eixos de tags controladas são:

- fase do ciclo de vida: `prepare`, `investigate`, `implement`, `verify`, `publish`,
  `operate`, `document` e `handoff`;
- escopo: `project`, `repository`, `multi-repository`, `workstation`,
  `external-service` e `skill-collection`;
- comportamento: `read-only-planning`, `mutation`, `evidence-producing`,
  `orchestration` e `notification`;
- integração: `git`, `github`, `telegram`, `google-drive` e `yandex-cloud`.

### Desenvolvimento e qualidade de código

#### `develop-with-test-first-evidence` (experimental)

Implemente comportamentos por meio de ciclos vermelho-verde-refatorar com respaldo
em evidências.

**O que faz:**

- registra um teste focado falhando pelo motivo comportamental pretendido antes
  da implementação;
- vincula resultados aprovados de testes focados e mais amplos ao estado final
  da alteração;
- valida evidências duráveis com seu schema e auxiliar incluídos.

**O que não faz:**

- fabricar uma falha quebrando comportamentos não relacionados;
- chamar testes escritos depois da implementação de desenvolvimento orientado
  por testes prévios;
- ocultar falhas preexistentes, ambientais ou do estado final.

**Como invocar:**

```text
$develop-with-test-first-evidence Implement this behavior with a recorded red-green-refactor cycle.
```

#### `review-code-changes` (experimental)

Revise uma alteração definida em busca de defeitos de correção, segurança,
confiabilidade e compatibilidade que possam ser corrigidos.

**O que faz:**

- identifica uma baseline exata e o estado alterado;
- relata achados respaldados por evidências, com impacto, condição de ocorrência,
  prioridade e localizações precisas;
- explicita incertezas e lacunas relevantes de testes.

**O que não faz:**

- relatar preferências de estilo ou especulação sem fundamento como defeitos;
- implementar achados, publicar comentários ou aprovar uma revisão sem
  autorização separada;
- substituir uma revisão com escopo definido por uma explicação geral do código.

**Como invocar:**

```text
$review-code-changes Review this branch against its declared baseline and report actionable findings.
```

#### `diagnose-software-defects` (experimental)

Investigue falhas e regressões para produzir uma explicação causal fundamentada
ou hipóteses ordenadas por plausibilidade.

**O que faz:**

- delimita e reproduz o sintoma com segurança quando possível;
- testa hipóteses concorrentes com evidências relevantes;
- relata a causa raiz, as condições contribuintes, o alcance do impacto, o grau
  de confiança e um plano de verificação da correção.

**O que não faz:**

- inferir causalidade a partir de correlação;
- alterar produção ou descartar evidências de falha;
- implementar uma correção especulativa quando apenas o diagnóstico foi solicitado.

**Como invocar:**

```text
$diagnose-software-defects Diagnose this regression and distinguish evidence from hypotheses.
```

#### `resolve-git-conflicts` (experimental)

Resolva semanticamente conflitos autorizados de merge, rebase ou cherry-pick,
preservando trabalho não relacionado.

**O que faz:**

- inspeciona a operação ativa, a base, os dois lados e cada caminho não integrado;
- concilia apenas conflitos cujo comportamento combinado pretendido é compreendido;
- valida os caminhos resolvidos e explicita a etapa restante da operação Git.

**O que não faz:**

- tratar divergência normal de repositório como tarefa de conflito de arquivos;
- executar automaticamente stash, reset, abort, continue ou force-push, nem
  preparar caminhos não relacionados para commit;
- adivinhar decisões ambíguas sobre arquivos gerados, binários, schemas ou produto.

**Como invocar:**

```text
$resolve-git-conflicts Resolve the active merge conflicts path by path and validate the result.
```

### Repositórios e entrega de alterações

#### `synchronize-git-repositories`

Estabeleça o estado remoto atual sem sobrescrever trabalho local.

**O que faz:**

- descobre somente repositórios relevantes para a tarefa e busca seus remotos rastreados;
- avança por fast-forward branches limpas que estão apenas atrás do remoto;
- informa estados com alterações locais, à frente, divergentes, detached, sem
  rastreamento e com operação em andamento;
- publica uma branch de funcionalidade autorizada a partir da `main` atual
  verificada antes da primeira edição quando a política do projeto exige isso.

**O que não faz:**

- executar automaticamente stash, reset, rebase, merge, clean, switch ou force-push;
- ocultar divergências ou tratar um fetch bem-sucedido como prova de que a branch
  local foi atualizada;
- vasculhar ou atualizar repositórios não relacionados.

**Como invocar:**

```text
$synchronize-git-repositories Configure this project's repository synchronization policy.
```

#### `verify-before-push`

Vincule as verificações declaradas pelo projeto ao estado Git exato a ser enviado.

**O que faz:**

- configura uma política de verificação pertencente ao repositório fora da
  pasta da skill instalada;
- executa as verificações declaradas e registra evidências para commits, árvores
  de trabalho, estado upstream e configuração de verificação exatos;
- bloqueia a operação quando as evidências exigidas para proteção estão ausentes,
  falharam, estão malformadas ou desatualizadas.

**O que não faz:**

- bloquear repositórios não relacionados que não estão cobertos pela política;
- analisar comandos arbitrários de shell ou instalar um hook específico de IDE
  ou agente;
- tratar uma verificação bem-sucedida de um estado Git anterior como evidência atual.

**Como invocar:**

```text
$verify-before-push Configure this project's verification policy and checks.
```

#### `coordinate-code-documentation-repositories` (experimental)

Coordene uma alteração auditável de projeto quando a implementação e a
documentação canônica estiverem em repositórios Git separados.

**O que faz:**

- identifica os papéis dos repositórios de implementação e documentação
  declarados pelo projeto;
- cria um plano somente leitura vinculado aos dois commits iniciais e às fontes
  oficiais de documentação;
- exige evidências de documentação para os tópicos configurados, como requisitos,
  comportamento, validação, impacto operacional e limitações;
- verifica a identidade dos dois commits publicados, as evidências de validação
  e a rastreabilidade entre repositórios antes de informar a conclusão conjunta.

**O que não faz:**

- inferir papéis de repositório a partir de nomes de diretórios ou repositórios;
- substituir a documentação canônica por um resumo diário;
- editar, criar commits, enviar, integrar ou reparar por conta própria
  repositórios com alterações locais e divergências;
- afirmar concordância semântica apenas porque existem os arquivos de
  documentação esperados.

**Como invocar:**

```text
$coordinate-code-documentation-repositories Implement this change across the declared code and canonical documentation repositories and verify both published outcomes.
```

#### `execute-configured-gitflow-releases` (experimental)

Execute rotas de release padrão e hotfix a partir de um contrato GitFlow
declarado pelo projeto.

**O que faz:**

- identifica desenvolvimento, produção, namespace de hotfix, remoto, etapas
  obrigatórias de verificação e política de rota padrão na configuração versionada
  do projeto;
- congela um plano somente leitura vinculado ao commit de origem e às
  identidades das branches remotas;
- aplica as mesmas verificações comuns declaradas às rotas padrão e hotfix;
- verifica a publicação revisada em produção, as evidências de implantação e a
  reintegração obrigatória do hotfix à linha de desenvolvimento.

**O que não faz:**

- inferir nomes convencionais de branches ou usar hotfix como rota padrão;
- oferecer suporte a entregas baseadas em trunk ou à cadeia de release
  especializada desta coleção;
- enviar diretamente à produção protegida, contornar verificações, reescrever
  o histórico ou reparar divergências silenciosamente;
- tratar um hotfix de produção como totalmente concluído antes de verificar
  sua reintegração.

**Como invocar:**

```text
$execute-configured-gitflow-releases Run the standard release route declared by this project and verify the resulting production identity.
$execute-configured-gitflow-releases Run an explicit hotfix release and verify its reintegration into the declared development line.
```

#### `execute-verified-development-lifecycle` (experimental)

Planeje e verifique um caminho declarado pelo projeto, desde a preparação da
funcionalidade até a integração revisada em desenvolvimento, a observação da
entrega, a documentação e a limpeza comprovada.

**O que faz:**

- congela um plano vinculado a um digest antes da edição e avança por pontos
  de controle ordenados usando evidências retidas;
- cria uma configuração conservadora do projeto durante uma atualização
  gerenciada ou no primeiro uso quando raízes de repositórios, upstreams
  rastreados, verificações e documentação são observáveis, e informa todos os
  padrões que aplicou;
- verifica as etapas obrigatórias de branch de funcionalidade antes da edição,
  testes prévios, pré-verificação do escopo alterado, revisão, push do estado
  exato, pipeline, documentação, integração em desenvolvimento, produção delegada,
  entrega, smoke test, notificação e limpeza;
- retorna a um ponto de controle declarado após uma falha e invalida evidências
  posteriores desatualizadas.

**O que não faz:**

- adivinhar adaptadores específicos de provedores, papéis de repositório,
  política de entrega ou autorização quando as evidências do projeto são ambíguas;
- enviar alterações, abrir ou integrar revisões, implantar, notificar, editar
  documentação ou excluir recursos por conta própria;
- executar a entrega em produção, que permanece delegada ao fluxo de release
  aprovado, como `$execute-configured-gitflow-releases`.

Instale e configure primeiro as skills obrigatórias:
`$synchronize-git-repositories`, `$develop-with-test-first-evidence`,
`$verify-before-push` e `$review-code-changes`. Um contrato de ciclo de vida de
versão 1, pertencente ao projeto e ainda ausente, é inicializado a partir de
fatos observáveis do projeto antes do primeiro plano; revise e refine os padrões
informados quando o projeto declarar uma política mais específica.
Instale skills opcionais somente quando o projeto habilitar os pontos de
controle correspondentes: `$orchestrate-agent-work`, `$diagnose-software-defects`,
`$resolve-git-conflicts`, `$coordinate-code-documentation-repositories`,
`$maintain-work-log`, `$maintain-project-digest`, `$notify-via-telegram` e
`$execute-configured-gitflow-releases`.

**Como invocar:**

```text
$execute-verified-development-lifecycle Plan and verify this change through the project's configured development lifecycle.
```

### Conhecimento e continuidade do projeto

#### `maintain-work-log`

Mantenha o diário canônico e datado do projeto em `docs/reports/work-log.md`.

**O que faz:**

- registra alterações relevantes, operações, diagnósticos, decisões, verificações,
  impedimentos e resultados de reversão;
- preserva o formato existente do diário do projeto;
- reconstrói o histórico ausente a partir das evidências disponíveis no Git e
  nas tarefas do projeto.

**O que não faz:**

- ativar-se para trabalho comum, salvo quando a política do projeto ou o usuário
  exigir isso;
- escrever segredos, logs de aplicação, controle de horas ou notas pessoais;
- afirmar eventos sem respaldo nas evidências disponíveis.

**Como invocar:**

```text
$maintain-work-log Configure this project to maintain its dated work log.
```

#### `maintain-project-digest` (experimental)

Mantenha um resumo diário das alterações concluídas do projeto, voltado ao
usuário, na documentação do projeto.

**O que faz:**

- agrupa as alterações concluídas sob a data de hoje como novas capacidades,
  melhorias, correções, segurança, documentação ou mudanças importantes de
  comportamento;
- escreve resultados curtos e não técnicos e omite categorias vazias;
- mantém as datas mais recentes primeiro e deixa todas as datas anteriores inalteradas;
- usa um plano vinculado ao conteúdo, um bloqueio cooperativo, substituição
  atômica e detecção de duplicatas para que vários desenvolvedores possam
  contribuir com segurança no mesmo dia.

**O que não faz:**

- escolher ou criar um local de documentação quando o projeto não o identifica
  de forma inequívoca;
- registrar planos, experimentos malsucedidos, atividades internas de
  implementação ou benefícios ao usuário sem comprovação;
- substituir o registro técnico de trabalho, as notas de release de versões
  ou um changelog convencional;
- reescrever períodos históricos do resumo durante uma atualização comum do mesmo dia.

**Como invocar:**

```text
$maintain-project-digest Add today's completed user-visible changes to the project digest.
```

#### `sync-project-context`

Sincronize entre computadores o estado privado e sanitizado de continuidade do
projeto e de cada conversa. A skill é estável depois que duas execuções
independentes com Google Drive em dispositivos reais passaram pelo seu critério
determinístico de promoção.

**O que faz:**

- armazena pontos de controle imutáveis em uma pasta sincronizada aprovada ou no
  Google Drive conectado, com configuração local da máquina fora do repositório;
- usa por padrão o Google Drive conectado para pedidos de sincronização sem
  qualificação, preservando um backend existente e exigindo adesão explícita
  antes de usar uma pasta sincronizada local;
- descobre em um computador novo um mapeamento existente e verificado do Google
  Drive pela impressão digital do repositório antes de criar qualquer pasta
  remota, e bloqueia diante de listagens incompletas, visibilidade não confiável
  ou correspondências duplicadas;
- mantém um fluxo opaco por tarefa de projeto: uma baseline detalhada seguida
  por deltas curtos, títulos visíveis exatos, decisões, verificações, questões
  em aberto, próximos passos e impressões digitais do Git;
- salva, restaura ou planeja bidirecionalmente todas as tarefas recentes e
  fixadas do projeto, ignorando tarefas inalteradas/ativas e expondo conflitos
  explicitamente;
- valida snapshots baixados, relê os uploads, impede restauração entre projetos
  e rejeita padrões de segredos identificados com alta confiança;
- registra um manifesto de ambiente separado para regras declaradas, skills,
  plugins e configurações escalares seguras que o Git ainda não fornece.

**O que não faz:**

- copiar arquivos-fonte, diffs, transcrições brutas, raciocínio oculto,
  credenciais, tokens OAuth ou instalações de skills/plugins;
- duplicar regras ou dependências já transportadas pelo Git;
- sobrescrever silenciosamente regras de destino pertencentes ao Git: a aplicação
  só pode criar um `AGENTS.md` ou `CLAUDE.md` ausente e não rastreado, selecionado
  para o agente ativo, após um plano explícito;
- incluir nomes de branches ou caminhos de arquivos no modo somente metadados;
  títulos visíveis de tarefas continuam incluídos intencionalmente.

Codex Desktop oferece suporte aos fluxos documentados de descoberta, criação e
renomeação de tarefas em lote e ao conector do Google Drive. Claude Code pode
usar o núcleo portável de pontos de controle, armazenamento em pasta local e
reconciliação de ambiente, mas seu armazenamento de sessões não é inspecionado
e operações de tarefas em lote exclusivas do Codex são bloqueadas como não suportadas.

**Como invocar:**

Configure cada computador uma vez:

```text
$sync-project-context Configure this clone in metadata-only mode. Use connected Google Drive by default unless I explicitly request another approved channel.
```

Depois, use comandos por tarefa ou em lote, por exemplo:

```text
$sync-project-context Save the current task state.
$sync-project-context Restore all project tasks on this computer.
$sync-project-context Synchronize all project tasks bidirectionally and show conflicts before applying changes.
```

No Claude Code, substitua o prefixo `$` desses exemplos por `/`.

### Coordenação e comunicação

#### `orchestrate-agent-work` (experimental)

Coordene subagentes explicitamente autorizados, mantendo a responsabilidade
pelo resultado integrado.

**O que faz:**

- divide o trabalho paralelo em atribuições delimitadas e sem sobreposição;
- acompanha e concilia os resultados dos agentes com as restrições compartilhadas;
- verifica o resultado combinado antes de informar a conclusão.

**O que não faz:**

- delegar sem que o usuário ou as instruções do projeto autorizem subagentes;
- transferir autoridade de aprovação, segredos, limpeza destrutiva ou alterações
  externas não aprovadas para outro agente;
- tratar subtarefas concluídas independentemente como prova de integração bem-sucedida.

**Como invocar:**

```text
$orchestrate-agent-work Delegate these independent subtasks to agents and verify the integrated result.
```

#### `synchronize-team-skills` (experimental)

Mantenha as skills de agente no escopo de projeto de cada integrante da equipe
alinhadas com um único manifesto revisado na documentação do projeto.

**O que faz:**

- cria ou lê `team-agent-skills.md` em uma raiz de documentação aprovada;
- compara as skills declaradas de Codex e Claude Code com cópias verificadas do projeto;
- informa estados ausente, desatualizado, mais recente, não verificado,
  substituição pelo projeto e extra preservado sem alterar o ambiente;
- cria um plano de instalação vinculado ao digest do manifesto para uma versão
  fixada da coleção;
- instala somente o conjunto revisado após aprovação e verifica o estado observável.

**O que não faz:**

- transformar automaticamente o estado acidental de uma estação de trabalho
  em política da equipe;
- armazenar segredos, configuração de usuário, caminhos da máquina ou
  autenticação de plugins;
- remover skills extras, rebaixar cópias mais recentes ou alterar instalações globais;
- afirmar que uma tarefa de agente em execução recarregou skills recém-instaladas.

**Como invocar:**

```text
$synchronize-team-skills Check this project's installed skills against the reviewed team manifest.
$synchronize-team-skills Align my project skills with the team documentation after showing the plan.
$synchronize-team-skills Add maintain-project-digest to the reviewed team skill set.
```

#### `notify-via-telegram`

Envie atualizações do ciclo de vida de tarefas longas de agentes pelo Telegram.

**O que faz:**

- informa início, marcos, resultados intermediários, problemas, impedimentos e conclusão;
- valida o bot interativamente e ajuda a descobrir uma conversa de destino;
- fornece um formulário de primeiro uso com dados mascarados e adequado para
  colagem no Codex Desktop no Windows;
- armazena credenciais no diretório de configuração do usuário e envia uma
  notificação de teste durante a configuração;
- oferece suporte a uma conversa ou tópico de fórum separado por projeto, com
  escolha explícita entre envio global mais projeto e envio somente ao projeto;
- exporta valores de roteamento do projeto sem segredos para reconciliação por
  meio de `sync-project-context`;
- funciona com a biblioteca padrão do Python 3 no Windows, macOS e Linux.

**O que não faz:**

- colocar o token do bot na conversa, no histórico do shell ou no repositório;
- copiar o token global do bot ou o estado de autenticação do Telegram entre computadores;
- enviar notificações quando o usuário pedir para manter o progresso na tarefa atual;
- funcionar como um framework geral de desenvolvimento de bots do Telegram.

**Como invocar:**

```text
$notify-via-telegram Configure Telegram notifications for long tasks.
$notify-via-telegram Configure this project to notify its team chat only, instead of the global destination.
```

### Infraestrutura e operações

#### `operate-yandex-cloud`

Opere infraestrutura Yandex Cloud explicitamente configurada e limitada ao
escopo do projeto.

**O que faz:**

- armazena IDs compartilhados de Cloud/Folder na configuração do projeto e o
  perfil `yc` da estação de trabalho em configuração local ignorada pelo Git;
- detecta os conjuntos de ferramentas necessários, verifica versões mínimas e
  executa uma pré-verificação de contexto somente leitura;
- oferece suporte a fluxos delimitados de CLI, SSH, Terraform, Ansible, Helm,
  Kubernetes, implantação, banco de dados, armazenamento, DNS, monitoramento,
  backup e incidentes;
- fornece saída JSON e auxiliares Python multiplataforma.

**O que não faz:**

- inferir Yandex Cloud a partir de pedidos genéricos de SSH, Kubernetes,
  Terraform ou implantação sem contexto de provedor;
- armazenar credenciais na configuração compartilhada do projeto;
- aplicar uma alteração antes de estabelecer o destino, o contexto e a autorização.

**Como invocar:**

```text
$operate-yandex-cloud Configure this project for Yandex Cloud operations.
```

### Evolução da coleção de skills

#### `discover-skill-candidates` (experimental)

Encontre ideias de skills reutilizáveis em evidências delimitadas de projeto e
contexto sem criar uma skill.

**O que faz:**

- inventaria arquivos `AGENTS.md` delimitados e relativos ao projeto, com
  proveniência do Git e por linha;
- opcionalmente inventaria documentação do projeto, arquivos selecionados,
  histórico Git delimitado, metadados de estrutura e resumos confirmados pelo
  usuário de conversas disponíveis ou transferências de `sync-project-context`;
- classifica candidatas como recomendadas, a investigar ou rejeitadas e as
  compara com catálogos existentes;
- oferece proativamente cada candidata elegível para contribuição segura a
  `kolabse/skills`, criação local ou adiamento;
- exporta uma ideia selecionada como pacote de contribuição sanitizado e
  vinculado a digest, que os mantenedores podem validar independentemente.

**O que não faz:**

- modificar regras do projeto nem criar a estrutura inicial, publicar ou instalar uma skill;
- enumerar conversas, ingerir transcrições brutas ou vasculhar amplamente o código-fonte;
- exportar regras brutas, caminhos locais, segredos, URLs ou endereços de e-mail;
- promover convenções exclusivamente de política, voláteis, sensíveis ou
  pontuais a fluxos reutilizáveis sem revisão.

**Como invocar:**

```text
$discover-skill-candidates Analyze this project's local rules and prepare an evidence-backed backlog of reusable skill ideas without creating anything.
```

#### `release-skill-collection`

Planeje, verifique, audite e faça a limpeza de releases determinísticas da coleção de skills.

**O que faz:**

- verifica versões, prontidão do changelog, estado do repositório, testes,
  segurança, arquivos determinísticos e checksums;
- valida evidências vinculadas ao commit para conjunto reservado de avaliação,
  instalações de agentes, plataformas, revisão e verificações locais;
- audita artefatos imutáveis do GitHub, manifestos, checksums e atestações;
- comprova se branches temporárias foram integradas, têm árvores idênticas ou
  são equivalentes por patches antes da limpeza;
- aplica uma limpeza explicitamente confirmada somente a partir de um plano
  seguro inalterado e de uma auditoria da release publicada com digest válido.

**O que não faz:**

- inferir permissão para criar commits ou tags, enviar alterações, disparar
  workflows ou publicar artefatos;
- mover uma tag existente ou substituir artefatos publicados;
- excluir branches apenas pelos nomes, com um plano desatualizado ou a partir
  de uma release não auditada.

**Como invocar:**

```text
$release-skill-collection Plan and verify release vX.Y.Z of this skill collection, but do not publish it yet.
```

## Composições suportadas

O catálogo define três fluxos de trabalho ordenados reutilizáveis:

- `protected-push`: sincronizar repositórios e depois produzir evidências atuais
  de verificação; registro de trabalho e notificação por Telegram são opcionais.
- `yandex-cloud-operation`: sincronizar repositórios e depois executar a
  operação de nuvem delimitada; verificação, registro de trabalho e notificação
  por Telegram são opcionais quando habilitados pela política do projeto.
- `skill-collection-release`: sincronizar o repositório, planejar e verificar
  localmente a release da coleção e depois vincular as evidências anteriores ao
  push; registro de trabalho e notificação por Telegram são opcionais.

Etapas obrigatórias bloqueiam a operação em caso de falha ou incerteza. Registros
e notificações opcionais informam suas próprias falhas sem alterar o resultado
observado da operação principal. Resolva um plano exato com
`scripts/compose_skills.py`; passe `--evidence` com um documento vinculado a digest
que corresponda a `schemas/composition-evidence.schema.json` para verificar a
ordem das etapas, os resultados obrigatórios e as falhas opcionais não bloqueantes.
O resultado verificado segue `schemas/composition-result.schema.json`.

## Adicione uma skill

Siga [CONTRIBUTING.md](CONTRIBUTING.md) e comece por
[`templates/skill-template.md`](../../../templates/skill-template.md). Toda skill
deve ter uma entrada correspondente em `skill-catalog.json` que registre seu
responsável, plataformas, status, licença e proveniência. Mantenha configurações
específicas de projeto fora da pasta da skill instalada para que atualizações
não possam sobrescrevê-las.

Não adicione um instalador no nível do repositório para uma skill individual.
Quando a coleção precisar de instalação e atualizações gerenciadas entre ChatGPT
e Codex, empacote-a como plugin OpenAI além desta estrutura multiagente.

Execute localmente as verificações da coleção com:

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py
```

Prepare uma suíte cega de acionamento para um agente ou seletor de modelo com:

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
```

A suíte contém apenas nomes de skills, descrições públicas, IDs opacos de casos
e prompts. Ela omite rótulos esperados e justificativas dos autores. Um seletor
retorna JSON estrito listando todas as skills selecionadas para cada caso;
pontue as observações com:

```shell
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

Use `run` com um comando após `--` para invocar um seletor que lê a suíte da
entrada padrão e escreve previsões na saída padrão. Mantenha credenciais de
provedores fora dos argumentos de comandos. O diretório ignorado
`.trigger-evals/` mantém suítes geradas, previsões e relatórios fora dos commits
por padrão. Suítes grandes de desenvolvimento são enviadas por padrão em lotes
de 64 casos vinculados a digest, para que respostas longas de JSON estrito não
trunquem IDs opacos de casos. Ajuste o limite com `--batch-size` sem expor os
rótulos esperados ao seletor.

Antes de uma release, execute o conjunto reservado de avaliação, versionado
separadamente e bloqueado por digest, sem usá-lo para ajustar descrições durante
o desenvolvimento:

```shell
python scripts/trigger_evals.py prepare \
  --corpus release-holdout \
  --output .trigger-evals/release-holdout.json
```

Compare um relatório candidato com um relatório produzido para a mesma versão
do conjunto reservado:

```shell
python scripts/trigger_evals.py compare \
  --candidate .trigger-evals/candidate-report.json \
  --markdown-output .trigger-evals/comparison.md
```

A comparação bloqueia a operação quando os digests das asserções diferem ou
quando a acurácia geral, a precisão, a revocação ou uma métrica por skill cai
além dos limites configurados. Por padrão, ela usa a baseline publicada indicada
por `skill-catalog.json`; passe `--baseline` somente ao comparar intencionalmente
com outro relatório compatível.

Para seletores de modelo não determinísticos, colete um número ímpar de pelo
menos três execuções cegas de previsão e pontue sua decisão majoritária:

```shell
python scripts/trigger_evals.py aggregate \
  --corpus release-holdout \
  --predictions run-1.json run-2.json run-3.json \
  --predictions-output .trigger-evals/aggregate.json \
  --json-output .trigger-evals/candidate-report.json
```

## Verifique uma release

Releases versionadas incluem arquivos ZIP e TAR.GZ determinísticos,
`release-manifest.json` e `SHA256SUMS`. Baixe os quatro artefatos em um único
diretório e verifique-os com:

```shell
python scripts/build_release.py --verify <download-directory>/SHA256SUMS
```

O GitHub também expõe um `digest` SHA-256 para cada artefato de release enviado.
Os workflows de release publicam adicionalmente atestações de artefatos do
GitHub. Verifique um artefato baixado em relação a este repositório com:

```shell
gh attestation verify <artifact> --repo kolabse/skills
```
