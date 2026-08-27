# kolabse/skills

[English](../../../README.md) | Русский | [Español](../es/README.md)

> Это перевод для удобства чтения. Канонической и наиболее актуальной является
> [английская версия](../../../README.md).

Переиспользуемые навыки агентов, сопровождаемые kolabse.

Лицензия — [Apache License 2.0](../../../LICENSE). Copyright 2026 kolabse.

## Оглавление

- [Установка навыков](#установка-навыков)
  - [Установка из Git marketplaces](#установка-из-git-marketplaces)
- [Обновление установленных навыков](#обновление-установленных-навыков)
  - [Запуск без клонирования репозитория](#запуск-без-клонирования-репозитория)
  - [Проверка глобальных установок](#проверка-глобальных-установок)
- [Установка или обновление локального Codex-плагина для разработки](#установка-или-обновление-локального-codex-плагина-для-разработки)
- [Доступные навыки](#доступные-навыки)
  - [Разработка и качество кода](#разработка-и-качество-кода)
    - [`develop-with-test-first-evidence`](#develop-with-test-first-evidence-experimental)
    - [`review-code-changes`](#review-code-changes-experimental)
    - [`diagnose-software-defects`](#diagnose-software-defects-experimental)
    - [`resolve-git-conflicts`](#resolve-git-conflicts-experimental)
  - [Репозитории и доставка изменений](#репозитории-и-доставка-изменений)
    - [`synchronize-git-repositories`](#synchronize-git-repositories)
    - [`verify-before-push`](#verify-before-push)
    - [`coordinate-code-documentation-repositories`](#coordinate-code-documentation-repositories-experimental)
    - [`execute-configured-gitflow-releases`](#execute-configured-gitflow-releases-experimental)
    - [`execute-verified-development-lifecycle`](#execute-verified-development-lifecycle-experimental)
  - [Знания и непрерывность проекта](#знания-и-непрерывность-проекта)
    - [`maintain-work-log`](#maintain-work-log)
    - [`maintain-project-digest`](#maintain-project-digest-experimental)
    - [`sync-project-context`](#sync-project-context)
  - [Координация и коммуникации](#координация-и-коммуникации)
    - [`orchestrate-agent-work`](#orchestrate-agent-work-experimental)
    - [`synchronize-team-skills`](#synchronize-team-skills-experimental)
    - [`notify-via-telegram`](#notify-via-telegram)
  - [Инфраструктура и эксплуатация](#инфраструктура-и-эксплуатация)
    - [`operate-yandex-cloud`](#operate-yandex-cloud)
  - [Развитие коллекции навыков](#развитие-коллекции-навыков)
    - [`discover-skill-candidates`](#discover-skill-candidates-experimental)
    - [`release-skill-collection`](#release-skill-collection)
- [Поддерживаемые композиции](#поддерживаемые-композиции)
- [Добавление навыка](#добавление-навыка)
- [Проверка релиза](#проверка-релиза)

## Установка навыков

Установите один или несколько навыков в текущий проект через общий для агентов
CLI [`skills`](https://skills.sh):

```shell
npx skills@latest add kolabse/skills
```

CLI находит папки в `skills/`, предлагает выбрать навыки и копирует их выбранным
агентам программирования. Это внешний установщик; репозиторий не публикует и не
запускает собственный npm-пакет.

Пользователи Codex также могут попросить `$skill-installer` установить навык из
этого репозитория, например:

```text
https://github.com/kolabse/skills/tree/main/skills/operate-yandex-cloud
```

Для неинтерактивной установки укажите потребителя:

```shell
npx skills@1.5.22 add kolabse/skills --agent codex --copy -y
npx skills@1.5.22 add kolabse/skills --agent claude-code --copy -y
```

Для project-scoped установки сразу создайте lifecycle contract, если
наблюдаемых defaults достаточно (используйте путь своего агента):

```shell
python .agents/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent codex --apply --yes --json
python .claude/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent claude-code --apply --yes --json
```

Глобальная marketplace/plugin-установка не знает active project root, поэтому
тот же bootstrap выполняется при первом использовании навыка в проекте.

Codex ищет проектные навыки в `.agents/skills/` и вызывает их как
`$skill-name`. Claude Code использует `.claude/skills/` и `/skill-name`.
Инструкции и скрипты общие; правила проекта и синтаксис вызова выбираются при
установке.

Репозиторий также упакован как содержащий только навыки плагин
`kolabse-skills` для ChatGPT/Codex и Claude Code. В него входят все папки из
`skills/`. Установка через `npx skills` остаётся независимой от плагинов.

### Установка из Git marketplaces

Для Codex зарегистрируйте marketplace и установите коллекцию:

```shell
codex plugin marketplace add kolabse/skills --ref main
codex plugin add kolabse-skills@kolabse
```

Обновите Git snapshot и переустановите текущую версию:

```shell
codex plugin marketplace upgrade kolabse
codex plugin add kolabse-skills@kolabse
```

Для Claude Code:

```shell
claude plugin marketplace add kolabse/skills
claude plugin install kolabse-skills@kolabse
```

Обновите его командой `claude plugin marketplace update kolabse` или включите
автообновление marketplace. После установки или обновления начните новую сессию
агента, чтобы он обнаружил актуальные навыки.

Каталоги находятся в
[`.agents/plugins/marketplace.json`](../../../.agents/plugins/marketplace.json)
и [`.claude-plugin/marketplace.json`](../../../.claude-plugin/marketplace.json),
payload описан в
[`.codex-plugin/plugin.json`](../../../.codex-plugin/plugin.json) и
[`.claude-plugin/plugin.json`](../../../.claude-plugin/plugin.json). Оба
каталога получают канонический `kolabse/skills` из `main`; версию релиза задают
manifest плагинов.

Материалы публичного размещения хранятся вместе с исходниками: [поддержка](SUPPORT.md),
[политика конфиденциальности](PRIVACY.md), [условия](TERMS.md) и воспроизводимый
[пакет marketplace submission](../../marketplace-submissions/). Публикация в
официальном каталоге требует review сопровождающего; Git marketplace — нет.

При тестировании Claude Code может загрузить распакованный релиз или доверенный
checkout через `claude --plugin-dir <collection-root>`. Для обычного применения
предпочитайте Git marketplace или `npx skills ... --agent claude-code`.
Claude Code читает `CLAUDE.md`, а не `AGENTS.md`; если правила уже находятся в
`AGENTS.md`, минимальный `CLAUDE.md` с `@AGENTS.md` сохраняет единый источник.

## Обновление установленных навыков

CLI `skills` записывает GitHub-источник и content hash в `skills-lock.json`.
Обновить все проектные установки из записанных источников:

```shell
npx skills@1.5.22 update -p -y
```

Обновить один навык или глобальные установки:

```shell
npx skills@1.5.22 update verify-before-push -p -y
npx skills@1.5.22 update -g -y
```

Lock для `kolabse/skills` без квалификатора следует за default branch и не
закрепляет релиз. Не редактируйте копии в `.agents/skills/`: update может их
заменить. Конфигурация проекта и пользователя хранится вне папок навыков.

Из клона или архива релиза обновите навыки и мигрируйте поддерживаемую
конфигурацию одной явной операцией:

```shell
python scripts/manage_installed_skills.py update --project-path . --yes --migrate
python scripts/manage_installed_skills.py doctor --project-path . --json
```

Предварительно просмотрите точный выбор без внешнего установщика и изменений:

```shell
python scripts/manage_installed_skills.py plan --project-path . --json
```

Plan сообщает источник, текущие и целевые версии, provenance, кандидатов на
миграцию и действия `update`, `unchanged`, `adopt-and-update` или `blocked`.
Схемы: `schemas/manager-plan.schema.json` и
`schemas/manager-result.schema.json`.

Без имён manager выбирает только установленные навыки kolabse из project lock;
посторонние навыки не обновляются. Для global scope имена указываются явно.
Проектное обновление заканчивается той же fail-closed диагностикой, что doctor.
Если обновляется `execute-verified-development-lifecycle`, manager также
создаёт отсутствующий config там, где проектных фактов достаточно, и возвращает
configuration outcome `created`, `configured` или `blocked`.

`--include-user-config` нужен только для миграции пользовательской конфигурации
Telegram. `status` и `doctor` read-only. `migrate` меняет только существующую
конфигурацию и не настраивает неиспользуемые навыки. По
`collection-metadata.json` status определяет версию и `provenance_status`:
`verified`, `legacy-unverified` или `mismatch`. Проверка локального checkout
основана на manifest, каталоге и содержимом, а не имени папки.

Legacy-установку до v1.2 без метаданных принимайте только после проверки
источника:

```shell
python scripts/manage_installed_skills.py status --project-path . --json
python scripts/manage_installed_skills.py update --project-path . --yes --adopt-legacy
```

Флаг не доверяет произвольным файлам: источник должен нормализоваться к
`kolabse/skills` или пройти проверку локального checkout, а итоговая диагностика
обязана подтвердить метаданные. Внешний CLI не обновляет `sourceType: local` на
месте; добавьте такие навыки заново с исходными `--skill` и `--agent`.

### Запуск без клонирования репозитория

Скачайте `scripts/bootstrap_update.py` из доверенного релиза или репозитория.
Он находит последний stable-релиз, сверяет ZIP с `SHA256SUMS` и GitHub build
provenance и запускает manager из изолированной временной распаковки:

```shell
python bootstrap_update.py doctor --json
python bootstrap_update.py plan --json
python bootstrap_update.py update --yes --migrate --json
```

`--release v1.15.0` закрепляет версию. Для attestation нужен `gh`; временная
папка удаляется. Offline cache требует `--offline-archive` вместе с
`--offline-checksums`. `--allow-unattested-offline` — явный ослабленный режим,
проверяющий только checksum доверенно переданного архива. Откат выбирает старый
релиз; миграции конфигурации остаются направленными вперёд.

### Проверка глобальных установок

Глобальное состояние ограничено общим `~/.agents/.skill-lock.json` v3. Payload
находится в `~/.agents/skills` для Codex и `~/.claude/skills` для Claude Code.
Другие пользовательские папки не сканируются. По умолчанию используется Codex;
для Claude передайте `--agent claude-code`:

```shell
python scripts/manage_installed_skills.py status --scope global --json
python scripts/manage_installed_skills.py doctor --scope global --json
python scripts/manage_installed_skills.py plan verify-before-push --scope global --json
python scripts/manage_installed_skills.py update verify-before-push --scope global --yes --json
python scripts/manage_installed_skills.py status --scope global --agent claude-code --json
```

`--global-root` позволяет read-only проверить тестовый или перенесённый layout.
Обновлять перенесённые roots нельзя, потому что внешний CLI не умеет их
адресовать. Неизвестные форматы lock только сообщаются.

Для отката сначала сохраните конфигурацию, затем переустановите нужный тег с теми
же навыками и агентами, например:

```shell
npx skills@1.5.22 add kolabse/skills@v1.1.0 --skill verify-before-push --agent codex --copy -y
```

Понижение конфигурации не поддерживается без явной документации релиза.
Восстановление старых файлов навыка не понижает config; при несовместимости
восстановите соответствующую резервную копию.

## Установка или обновление локального Codex-плагина для разработки

Для локальной разработки создайте или обновите personal marketplace, скопируйте
плагин, добавьте cachebuster Codex и активируйте:

```shell
python scripts/install_personal_plugin.py --activate
```

Установщик сохраняет посторонние marketplace entries и не правит manifest
репозитория. Это путь разработки, а не обычная Git marketplace установка.
Повторяйте после обновления checkout и начинайте новую задачу Codex. `--json`
показывает версию и пути установки.

## Доступные навыки

Stable и experimental навыки перечислены в `skill-catalog.json`. Их
конфигурация, safety boundaries и CLI следуют политике
[CONTRIBUTING.md](CONTRIBUTING.md). Каталог объявляет scope, read-only status,
возможности, зависимости и интеграции; stateful-навыки имеют идемпотентный
configure, schema и migration для версионированной конфигурации.

Каталог сгруппирован по основному назначению для пользователя в указанном ниже
порядке приоритета. У каждого навыка ровно одна основная категория. Независимые
теги описывают этап жизненного цикла, область действия, поведение и интеграции;
статус зрелости от них не зависит. Авторитетные машиночитаемые назначения и
контролируемый словарь находятся в
[`skill-catalog.json`](../../../skill-catalog.json) и проверяются по
[`schemas/skill-catalog.schema.json`](../../../schemas/skill-catalog.schema.json).

Контролируемые группы тегов:

- этап жизненного цикла: `prepare`, `investigate`, `implement`, `verify`,
  `publish`, `operate`, `document` и `handoff`;
- область действия: `project`, `repository`, `multi-repository`, `workstation`,
  `external-service` и `skill-collection`;
- поведение: `read-only-planning`, `mutation`, `evidence-producing`,
  `orchestration` и `notification`;
- интеграция: `git`, `github`, `telegram`, `google-drive` и `yandex-cloud`.

### Разработка и качество кода

#### `develop-with-test-first-evidence` (experimental)

Реализует поведение через подтверждённый red-green-refactor.

**Что делает:** фиксирует focused test, падающий по нужной причине до кода;
привязывает focused и broader green к финальному состоянию и валидирует evidence.

**Чего не делает:** не создаёт red поломкой постороннего поведения, не называет
последующие тесты test-first и не скрывает старые/environment/final failures.

**Вызов:**

```text
$develop-with-test-first-evidence Реализуй поведение с зафиксированным циклом red-green-refactor.
```

#### `review-code-changes` (experimental)

Проверяет заданное изменение на корректность, security, reliability и compatibility.

**Что делает:** определяет baseline/change, сообщает evidence-backed findings с
impact, trigger, priority и точным location, раскрывает uncertainty и test gaps.

**Чего не делает:** не выдаёт вкусовые предпочтения за дефекты, не реализует и
не публикует findings без разрешения и не заменяет review общим объяснением.

**Вызов:**

```text
$review-code-changes Проверь эту ветку относительно baseline и сообщи подтверждённые дефекты.
```

#### `diagnose-software-defects` (experimental)

Исследует failures и regressions до подтверждённой причины или ранжированных гипотез.

**Что делает:** ограничивает и безопасно воспроизводит симптом, проверяет
конкурирующие гипотезы и сообщает root cause, условия, blast radius, confidence
и план проверки исправления.

**Чего не делает:** не выводит причинность из корреляции, не мутирует production,
не уничтожает evidence и не реализует speculative fix вместо диагностики.

**Вызов:**

```text
$diagnose-software-defects Диагностируй regression и отдели evidence от гипотез.
```

#### `resolve-git-conflicts` (experimental)

Семантически разрешает одобренные merge/rebase/cherry-pick конфликты.

**Что делает:** изучает active operation, base, стороны и каждый unmerged path;
объединяет только понятное поведение, проверяет paths и явно называет следующий
Git-шаг.

**Чего не делает:** не считает обычную divergence файловым конфликтом, не
stash/reset/abort/continue/force-push автоматически, не stage постороннее и не
угадывает неоднозначные binary/generated/schema решения.

**Вызов:**

```text
$resolve-git-conflicts Разреши активные конфликты по файлам и проверь результат.
```


### Репозитории и доставка изменений

#### `synchronize-git-repositories`

Устанавливает актуальное remote-состояние без перезаписи локальной работы.

**Что делает:** находит только относящиеся к задаче репозитории, fetch их
tracked remotes, fast-forward чистых behind-only веток, сообщает опасные
состояния и при требовании публикует feature-ветку от проверенного main до edit.

**Чего не делает:** автоматически не stash/reset/rebase/merge/clean/switch и не
force-push; не скрывает divergence и не сканирует посторонние репозитории.

**Вызов:**

```text
$synchronize-git-repositories Настрой политику синхронизации репозиториев проекта.
```

#### `verify-before-push`

Привязывает объявленные проектом проверки к точному Git-состоянию push.

**Что делает:** настраивает repository-owned policy вне навыка, запускает checks
и записывает evidence для commits, worktree, upstream и config; fail closed при
отсутствующем, повреждённом или stale evidence.

**Чего не делает:** не блокирует неохваченные репозитории, не разбирает
произвольный shell и не считает старый успешный check актуальным.

**Вызов:**

```text
$verify-before-push Настрой политику проверок этого проекта.
```

#### `coordinate-code-documentation-repositories` (experimental)

Координирует одно проверяемое изменение, когда код и каноническая документация
живут в разных репозиториях.

**Что делает:** определяет объявленные роли репозиториев, создаёт read-only plan
на исходных commits, требует evidence по настроенным темам и проверяет обе
опубликованные идентичности и cross-repository traceability.

**Чего не делает:** не угадывает роли по именам, не заменяет документацию
дайджестом, сам не редактирует/commit/push/merge и не считает наличие файлов
доказательством смыслового согласия.

**Вызов:**

```text
$coordinate-code-documentation-repositories Реализуй изменение в объявленных репозиториях кода и документации и проверь оба опубликованных результата.
```

#### `execute-configured-gitflow-releases` (experimental)

Выполняет standard и hotfix routes по объявленному проектом GitFlow-контракту.

**Что делает:** читает ветви, remote, gates и default route из versioned config;
фиксирует план на commits; применяет общие gates и проверяет production,
deployment и обязательную hotfix reintegration.

**Чего не делает:** не угадывает имена веток и не выбирает hotfix по умолчанию;
не поддерживает trunk flow или специальную цепочку этой коллекции; не обходит
защиту, не переписывает историю и не завершает hotfix до reintegration.

**Вызов:**

```text
$execute-configured-gitflow-releases Выполни объявленный стандартный релиз и проверь production identity.
$execute-configured-gitflow-releases Выполни явный hotfix и проверь его возврат в development line.
```

#### `execute-verified-development-lifecycle` (experimental)

Планирует и проверяет объявленный проектом путь от feature preparation до
reviewed dev integration, delivery observation, документации и cleanup.

**Что делает:** при managed update или первом вызове создаёт консервативный
project config из наблюдаемых Git roots, upstream refs, checks и документации
и сообщает все defaults; фиксирует digest-bound plan до edit, продвигает ordered
checkpoints по retained evidence; проверяет feature-before-edit, test-first,
preflight, review, push, pipeline, docs, integration, production delegation,
delivery, smoke, notifications и cleanup; после ошибки возвращает к объявленной
точке и инвалидирует downstream evidence.

**Чего не делает:** не угадывает provider-specific adapters, repo roles,
delivery policy или authorization при неоднозначных данных;
сам не push/open/merge/deploy/notify/edit docs/delete; production остаётся у
одобренного процесса вроде `$execute-configured-gitflow-releases`.

Сначала установите обязательные `$synchronize-git-repositories`,
`$develop-with-test-first-evidence`, `$verify-before-push` и
`$review-code-changes`. Отсутствующий project-owned v1 lifecycle contract
создаётся из наблюдаемых фактов до первого plan; проверьте и уточните defaults,
если правила проекта задают более точную политику. Опциональные навыки
устанавливаются только для включённых checkpoints.

**Вызов:**

```text
$execute-verified-development-lifecycle Спланируй и проверь изменение по настроенному development lifecycle проекта.
```


### Знания и непрерывность проекта

#### `maintain-work-log`

Ведёт канонический датированный журнал `docs/reports/work-log.md`.

**Что делает:** записывает существенные изменения, операции, диагностику,
решения, проверки, blockers и rollback; сохраняет формат и восстанавливает
историю только по доступным evidence.

**Чего не делает:** не запускается без требования, не записывает секреты,
application logs, time tracking или неподтверждённые события.

**Вызов:**

```text
$maintain-work-log Настрой ведение датированного журнала проекта.
```

#### `maintain-project-digest` (experimental)

Ведёт ежедневный понятный пользователям дайджест завершённых изменений.

**Что делает:** группирует изменения текущей даты по возможностям, улучшениям,
исправлениям, безопасности, документации и важному поведению; пишет коротко,
пропускает пустые категории, не меняет прошлые даты и защищает совместную запись.

**Чего не делает:** не выбирает неоднозначное место документации, не пишет
планы и внутреннюю активность, не заменяет work log/changelog/release notes и
не переписывает прошлые периоды.

**Вызов:**

```text
$maintain-project-digest Добавь завершённые сегодня пользовательские изменения в дайджест проекта.
```

#### `sync-project-context`

Синхронизирует приватное очищенное состояние проекта и задач между компьютерами.
Навык stable после двух независимых real-device Google Drive прогонов.

**Что делает:** хранит immutable checkpoints в одобренной папке или Drive;
неуточнённый запрос по умолчанию использует подключённый Google Drive; ведёт
opaque stream с baseline/deltas, visible titles, decisions и Git fingerprints;
планирует task/batch save, restore и bidirectional sync; проверяет snapshots,
readback и project identity; сохраняет отдельный environment manifest для
правил, навыков, плагинов и безопасных settings, которых нет в Git.

**Чего не делает:** не копирует source, diffs, raw transcripts, hidden reasoning,
credentials, OAuth или установки; не дублирует Git-owned environment и не
перезаписывает destination rules; в metadata-only не включает branch/path.

Codex Desktop поддерживает batch discovery/create/rename и Drive connector.
Claude Code использует portable checkpoints, local-folder и environment core,
но не инспектирует sessions и fail closed для Codex-only batch операций.

**Вызов:**

Однократная настройка каждого компьютера:

```text
$sync-project-context Настрой этот клон в metadata-only. По умолчанию используй подключённый Google Drive, если я явно не выберу другой канал.
```

Затем:

```text
$sync-project-context Сохрани состояние текущей задачи.
$sync-project-context Восстанови все задачи проекта на этом компьютере.
$sync-project-context Синхронизируй все задачи двунаправленно и покажи конфликты до применения.
```

В Claude Code заменяйте `$` на `/`.


### Координация и коммуникации

#### `orchestrate-agent-work` (experimental)

Координирует явно разрешённых subagents и отвечает за общий результат.

**Что делает:** разделяет параллельную работу на ограниченные непересекающиеся
задачи, наблюдает и согласует результаты, проверяет интеграцию.

**Чего не делает:** не делегирует без разрешения, не передаёт approvals, secrets,
destructive cleanup или внешние mutations и не считает отдельные результаты
доказательством успешной интеграции.

**Вызов:**

```text
$orchestrate-agent-work Делегируй независимые подзадачи агентам и проверь общий результат.
```

#### `synchronize-team-skills` (experimental)

Синхронизирует проектные навыки участников команды с одним проверенным
manifest в документации проекта.

**Что делает:**

- создаёт или читает `team-agent-skills.md` в выбранной директории документации;
- сравнивает требования для Codex и Claude Code с проверенными проектными копиями;
- без изменений показывает отсутствующие, старые, более новые, непроверенные,
  проектные копии, перекрывающие более широкие области, и дополнительные навыки;
- строит связанный с digest manifest план установки одной версии коллекции;
- после подтверждения устанавливает только согласованный набор и проверяет его.

**Чего не делает:**

- не превращает случайное состояние одного компьютера в стандарт команды;
- не сохраняет secrets, user config, пути компьютера или plugin authentication;
- не удаляет дополнительные навыки, не понижает версии и не меняет global scope;
- не утверждает, что открытый диалог уже загрузил новые навыки.

**Вызов:**

```text
$synchronize-team-skills Проверь навыки проекта по командному manifest.
$synchronize-team-skills Покажи план и синхронизируй мои навыки с документацией команды.
$synchronize-team-skills Добавь maintain-project-digest в командный набор навыков.
```

#### `notify-via-telegram`

Отправляет Telegram-обновления жизненного цикла долгих задач агента.

**Что делает:** сообщает start/milestone/problem/blocker/completion; настраивает
бота и чат, предлагает безопасную Windows-форму, хранит credential в user config,
поддерживает отдельный чат/topic проекта и экспортирует secret-free routing для
`sync-project-context`; работает на Python standard library.

**Чего не делает:** не помещает token в чат, shell history или repo; не переносит
bot auth между ПК, не уведомляет против просьбы пользователя и не является
framework разработки Telegram-ботов.

**Вызов:**

```text
$notify-via-telegram Настрой Telegram-уведомления для долгих задач.
$notify-via-telegram Настрой проект на уведомления только в командный чат вместо глобального канала.
```


### Инфраструктура и эксплуатация

#### `operate-yandex-cloud`

Работает с явно настроенной инфраструктурой Yandex Cloud в scope проекта.

**Что делает:** хранит Cloud/Folder IDs в project config, локальный `yc` profile
в ignored config; проверяет tools/versions/context; поддерживает scoped CLI,
SSH, Terraform, Ansible, Helm, Kubernetes, deployment, DB, storage, DNS,
monitoring, backup и incident workflows.

**Чего не делает:** не выводит Yandex Cloud из общего SSH/Kubernetes запроса, не
хранит credentials в shared config и не мутирует до определения target,
context и authorization.

**Вызов:**

```text
$operate-yandex-cloud Настрой проект для работы с Yandex Cloud.
```


### Развитие коллекции навыков

#### `discover-skill-candidates` (experimental)

Находит переиспользуемые идеи навыков в ограниченных правилах и контексте, не
создавая навык.

**Что делает:** инвентаризирует project-relative `AGENTS.md` с Git/line
provenance; по разрешению изучает документацию, выбранные файлы, ограниченную
историю и подтверждённые summaries чатов или handoff; ранжирует кандидатов и
сравнивает с каталогами; предлагает contribution, локальную реализацию или
отсрочку; экспортирует очищенный digest-bound пакет.

**Чего не делает:** не меняет правила, не создаёт и не устанавливает навык; не
перечисляет чаты, не читает raw transcripts и не сканирует код широко; не
экспортирует правила, пути, секреты, URL и email; не продвигает одноразовые или
чувствительные соглашения без review.

**Вызов:**

```text
$discover-skill-candidates Проанализируй локальные правила проекта и подготовь подтверждённый список идей навыков, ничего не создавая.
```

#### `release-skill-collection`

Планирует, проверяет, аудитирует и очищает детерминированные релизы коллекции.

**Что делает:** проверяет версии, changelog, Git, тесты, security, архивы и
checksums; валидирует commit-bound gates; аудитирует assets, manifest и
attestation; доказывает представленность веток перед cleanup.

**Чего не делает:** не предполагает разрешение на commit/tag/push/workflow; не
перемещает тег, не заменяет assets и не удаляет ветки по имени или stale plan.

**Вызов:**

```text
$release-skill-collection Спланируй и проверь релиз vX.Y.Z, но пока не публикуй.
```

## Поддерживаемые композиции

Каталог определяет три упорядоченных процесса:

- `protected-push`: синхронизация, затем актуальное verification evidence;
- `yandex-cloud-operation`: синхронизация и scoped cloud operation;
- `skill-collection-release`: синхронизация, local release verify и pre-push evidence.

Work log и Telegram необязательны. Required steps fail closed; необязательные
ошибки не меняют основной результат. `scripts/compose_skills.py` формирует plan,
а `--evidence` со схемами `schemas/composition-evidence.schema.json` и
`schemas/composition-result.schema.json` проверяет порядок и результаты.

## Добавление навыка

Следуйте [CONTRIBUTING.md](CONTRIBUTING.md) и
[`templates/skill-template.md`](../../../templates/skill-template.md). Каждый
навык имеет запись в `skill-catalog.json` с владельцем, платформами, status,
license и provenance. Project config хранится вне установленной папки.

Не добавляйте repository-level установщик одного навыка. Для управляемой
установки ChatGPT/Codex коллекция пакуется OpenAI-плагином дополнительно к
cross-agent layout.

Локальные проверки:

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py
```

Подготовить blind trigger suite:

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
```

Suite содержит только имена, публичные descriptions, opaque IDs и prompts без
labels и author reasons. Selector возвращает strict JSON; оценка:

```shell
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

`run -- <command>` передаёт suite через stdin. Credentials не должны быть в
arguments. `.trigger-evals/` игнорируется. Большие suites разбиваются на
digest-bound batches по 64; размер меняется через `--batch-size`.

Перед релизом используйте отдельно версионированный digest-locked holdout:

```shell
python scripts/trigger_evals.py prepare \
  --corpus release-holdout \
  --output .trigger-evals/release-holdout.json
```

Сравнение только с baseline той же версии:

```shell
python scripts/trigger_evals.py compare \
  --candidate .trigger-evals/candidate-report.json \
  --markdown-output .trigger-evals/comparison.md
```

Разные assertion digests отклоняются; сравниваются общие и per-skill metrics.
По умолчанию baseline берётся из каталога. Для недетерминированного selector
соберите нечётное число минимум из трёх blind runs:

```shell
python scripts/trigger_evals.py aggregate \
  --corpus release-holdout \
  --predictions run-1.json run-2.json run-3.json \
  --predictions-output .trigger-evals/aggregate.json \
  --json-output .trigger-evals/candidate-report.json
```

## Проверка релиза

Релиз включает deterministic ZIP и TAR.GZ, `release-manifest.json` и
`SHA256SUMS`. Скачайте четыре assets в одну папку и выполните:

```shell
python scripts/build_release.py --verify <download-directory>/SHA256SUMS
```

GitHub показывает SHA-256 digest каждого asset и публикует artifact
attestations. Проверка скачанного файла:

```shell
gh attestation verify <artifact> --repo kolabse/skills
```
