# kolabse/skills

[English](../../../README.md) | [Русский](../ru/README.md) | [Español](../es/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Português (Brasil)](../pt-BR/README.md) | [日本語](../ja/README.md) | [Italiano](../it/README.md) | [한국어](../ko/README.md) | [简体中文](../zh-CN/README.md) | [Türkçe](../tr/README.md) | [Polski](../pl/README.md) | Українська

> Це переклад для зручності читання. Канонічною та найбільш актуальною є
> [англійська версія](../../../README.md).

Навички агентів, що перевикористовуються, супроводжуються kolabse.

Ліцензія — [Apache License 2.0](../../../LICENSE). Copyright 2026 kolabse.

## Зміст

- [Встановлення навичок](#встановлення-навичок)
  - [Установка з Git marketplaces](#установка-з-git-marketplaces)
- [Оновлення встановлених навичок](#оновлення-встановлених-навичок)
  - [Запуск без клонування репозиторію](#запуск-без-клонування-репозиторію)
  - [Перевірка глобальних установок](#перевірка-глобальних-установок)
- [Встановлення або оновлення локального Codex-плагіну для розробки](#встановлення-або-оновлення-локального-codex-плагіна-для-розробки)
- [Доступні навички](#доступні-навички)
  - [Розробка та якість коду](#розробка-та-якість-коду)
    - [`develop-with-test-first-evidence`](#develop-with-test-first-evidenceexperimental)
    - [`review-code-changes`](#review-code-changesexperimental)
    - [`diagnose-software-defects`](#diagnose-software-defectsexperimental)
    - [`resolve-git-conflicts`](#resolve-git-conflictsexperimental)
  - [Репозиторії та доставка змін](#репозиторії-та-доставка-змін)
    - [`synchronize-git-repositories`](#synchronize-git-repositories)
    - [`verify-before-push`](#verify-before-push)
    - [`coordinate-code-documentation-repositories`](#coordinate-code-documentation-repositoriesexperimental)
    - [`execute-configured-gitflow-releases`](#execute-configured-gitflow-releasesexperimental)
    - [`execute-verified-development-lifecycle`](#execute-verified-development-lifecycleexperimental)
  - [Знання та безперервність проекту](#знання-та-безперервність-проекту)
    - [`maintain-work-log`](#maintain-work-log)
    - [`maintain-project-digest`](#maintain-project-digestexperimental)
    - [`sync-project-context`](#sync-project-context)
  - [Координація та комунікації](#координація-та-комунікації)
    - [`orchestrate-agent-work`](#orchestrate-agent-workexperimental)
    - [`synchronize-team-skills`](#synchronize-team-skillsexperimental)
    - [`report-skill-feedback`](#report-skill-feedbackexperimental)
    - [`notify-via-telegram`](#notify-via-telegram)
  - [Інфраструктура та експлуатація](#інфраструктура-та-експлуатація)
    - [`operate-yandex-cloud`](#operate-yandex-cloud)
  - [Розвиток колекції навичок](#розвиток-колекції-навичок)
    - [`discover-skill-candidates`](#discover-skill-candidatesexperimental)
    - [`release-skill-collection`](#release-skill-collection)
- [Підтримувані композиції](#підтримувані-композиції)
- [Додавання навыка](#додавання-навички)
- [Перевірка випуску](#перевірка-релізу)

## Встановлення навичок

Встановіть один або кілька навичок глобально для поточного користувача через
загальний для агентів CLI [`skills`](https://skills.sh):

```shell
npx skills@latest add kolabse/skills --global
```

CLI знаходить папки в`skills/`, пропонує вибрати навички та копіює їх вибраним
агентам програмування. Це зовнішній установник; репозиторій не публікує та не
запускає свій npm-пакет.

Користувачі Codex також можуть попросити`$skill-installer`встановити навичку з
цього репозиторію, наприклад:

```text
https://github.com/kolabse/skills/tree/main/skills/operate-yandex-cloud
```

Для неінтерактивної установки вкажіть споживача:

```shell
npx skills@1.5.22 add kolabse/skills --agent codex --copy --global -y
npx skills@1.5.22 add kolabse/skills --agent claude-code --copy --global -y
```

Попросіть агента: «Встанови вибрані навички глобально і додай тільки
відсутні налаштування цього проекту, не замінюючи існуючі правила».
Після роботи зовнішнього установника використовуйте глобальний шлях навички:

```shell
python ~/.agents/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent codex --apply --yes --json
python ~/.claude/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent claude-code --apply --yes --json
```

Якщо угод ще немає, використовуються префікси`feature/`, `bugfix/`, `release/`,
`hotfix/`та типи коммітів`feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
Явно задані префікси, ролі гілок та формати коммітів зберігають пріоритет.
Постійні гілки та Git hooks не створюються. Кероване глобальне оновлення
виконує той же bootstrap для явно вибраного активного проекту; без
підтвердження – лише план.

Відразу створіть lifecycle contract проекту, якщо спостерігаються defaults достатньо
(використовуйте шлях свого агента):

```shell
python ~/.agents/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent codex --apply --yes --json
python ~/.claude/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent claude-code --apply --yes --json
```

Глобальна marketplace/plugin-установка не знає active project root, тому
той же bootstrap виконується при першому використанні навички у проекті.

Підтримувані глобальні шляхи:`~/.agents/skills/`для Codex та`~/.claude/skills/`для Claude Code. У проектах поза цими payload-папками зберігаються
лише конфігурація, керовані правила та навмисні проектні налаштування.

Репозиторій також упакований як плагін, що містить тільки навички.`kolabse-skills`для ChatGPT/Codex та Claude Code. До нього входять усі папки з`skills/`. Установка через`npx skills`залишається незалежною від плагінів.

### Установка з Git marketplaces

Для Codex зареєструйте marketplace та встановіть колекцію:

```shell
codex plugin marketplace add kolabse/skills --ref main
codex plugin add kolabse-skills@kolabse
```

Оновіть Git snapshot та перевстановіть поточну версію:

```shell
codex plugin marketplace upgrade kolabse
codex plugin add kolabse-skills@kolabse
```

Для Claude Code:

```shell
claude plugin marketplace add kolabse/skills
claude plugin install kolabse-skills@kolabse
```

Оновіть його командою`claude plugin marketplace update kolabse`або увімкніть
Автоновини на ринкуринку. Після встановлення або оновлення розпочніть нову сесію
агента, щоб він виявив актуальні навички.

Каталоги знаходяться в
[`.agents/plugins/marketplace.json`](../../../.agents/plugins/marketplace.json)
і [`.claude-plugin/marketplace.json`](../../../.claude-plugin/marketplace.json),
payload описаний у
[`.codex-plugin/plugin.json`](../../../.codex-plugin/plugin.json) та
[`.claude-plugin/plugin.json`](../../../.claude-plugin/plugin.json). Обидва
каталогу отримують канонічний`kolabse/skills`з`main`; версію релізу задають
manifest плагінів.

Матеріали публічного розміщення зберігаються разом із вихідними джерелами: [підтримка](SUPPORT.md),
[Політика конфіденційності](PRIVACY.md), [умови](TERMS.md) і відтворюваний
[пакет marketplace submission](../../marketplace-submissions/). Публікація в
офіційний каталог вимагає review супроводжуючого; Git marketplace – ні.

Під час тестування Claude Code може завантажити розпакований реліз або довірений
checkout через`claude --plugin-dir <collection-root>`. Для звичайного застосування
віддайте перевагу Git marketplace або`npx skills ... --agent claude-code`.
Claude Code читає`CLAUDE.md`, а не`AGENTS.md`; якщо правила вже знаходяться в`AGENTS.md`, мінімальний`CLAUDE.md`з`@AGENTS.md`зберігає єдине джерело.

## Оновлення встановлених навичок

CLI`skills`записує глобальні джерела та content hashes у`~/.agents/.skill-lock.json`. Оновіть глобальні установки із записаних джерел:

```shell
npx skills@1.5.22 update -g -y
```

Оновити одну навичку або глобальні установки:

```shell
npx skills@1.5.22 update verify-before-push -g -y
npx skills@1.5.22 update -g -y
```

Старі проектні копії необхідно централізувати після перевірки плану. Міграція
спочатку встановлює та перевіряє глобальну копію, потім зберігає резервну
копію старого payload і не зачіпає конфігурацію проекту та чужі навички:

```shell
python scripts/centralize_skill_installations.py plan --project-path . --json
python scripts/centralize_skill_installations.py apply --project-path . --expected-plan-sha256 <plan-value> --yes --json
```

Lock для`kolabse/skills`без кваліфікатора слідує за default branch і не
закріплює реліз. Не редагуйте глобальні payload-копії: update може їх
замінити. Конфігурація проекту та користувача зберігається поза папками навичок.

З клону або архіву релізу оновіть навички та мігруйте підтримувану
конфігурацію однією явною операцією:

```shell
python scripts/manage_installed_skills.py update --scope global --project-path . --yes --migrate
python scripts/manage_installed_skills.py doctor --scope global --project-path . --json
```

Попередньо перегляньте точний вибір без зовнішнього установника та змін:

```shell
python scripts/manage_installed_skills.py plan --scope global --project-path . --json
```

Plan повідомляє джерело, поточні та цільові версії, provenance, кандидатів на
міграцію та дії`update`, `unchanged`, `adopt-and-update`або`blocked`.
Схеми:`schemas/manager-plan.schema.json`і`schemas/manager-result.schema.json`.

Без назви manager вибирає тільки навички kolabse з глобального lock;
сторонні глобальні навички не оновлюються. Старе проектне оновлення
зберігається лише як перехідний шлях до повідомлення та міграції. Якщо глобально
оновлюється`execute-verified-development-lifecycle`, manager також
створює відсутній config там, де проектних фактів достатньо, та повертає
configuration outcome`created`, `configured`або`blocked`.

`--include-user-config`потрібен тільки для міграції конфігурації користувача
Telegram.`status`і`doctor`read-only.`migrate`змінює лише існуючу
конфігурацію і не налаштовує навички, що не використовуються. за`collection-metadata.json`status визначає версію та`provenance_status`:
`verified`, `legacy-unverified`або`mismatch`. Перевірка локального checkout
заснована на manifest, каталозі та вмісті, а не імені папки.

Legacy-установку до v1.2 без метаданих приймайте лише після перевірки
джерела:

```shell
python scripts/manage_installed_skills.py status --scope global --project-path . --json
python scripts/manage_installed_skills.py update --scope global --project-path . --yes --adopt-legacy
```

Прапор не довіряє довільним файлам: джерело має нормалізуватися до`kolabse/skills`або пройти перевірку локального checkout, а підсумкова діагностика
повинна підтвердити метадані. Зовнішній CLI не оновлює`sourceType: local`на
місці; додайте такі навички заново з вихідними`--skill`і`--agent`.

### Запуск без клонування репозиторію

Завантажте`scripts/bootstrap_update.py`з довіреного релізу чи репозиторію.
Він знаходить останній stable-реліз, звіряє ZIP з`SHA256SUMS`та GitHub build
provenance і запускає manager із ізольованого тимчасового розпакування:

```shell
python bootstrap_update.py doctor --json
python bootstrap_update.py plan --json
python bootstrap_update.py update --yes --migrate --json
```

`--release v1.15.0`закріплює версію. Для аттестації потрібен`gh`; тимчасова
папка видаляється. Offline cache вимагає`--offline-archive`разом з`--offline-checksums`. `--allow-unattested-offline`- явний ослаблений режим,
перевіряючий тільки checksum довірено переданого архіву. Відкат вибирає старий
реліз; міграції конфігурації залишаються спрямованими вперед.

### Перевірка глобальних установок

Глобальний стан обмежений загальним`~/.agents/.skill-lock.json`v3. Payload
знаходиться в`~/.agents/skills`для Codex та`~/.claude/skills`для Claude Code.
Інші папки користувача не скануються. За промовчанням використовується Codex;
для Claude передайте`--agent claude-code`:

```shell
python scripts/manage_installed_skills.py status --scope global --json
python scripts/manage_installed_skills.py doctor --scope global --json
python scripts/manage_installed_skills.py plan verify-before-push --scope global --json
python scripts/manage_installed_skills.py update verify-before-push --scope global --yes --json
python scripts/manage_installed_skills.py status --scope global --agent claude-code --json
```

`--global-root`дозволяє read-only перевірити тестовий або перенесений layout.
Оновлювати перенесені roots не можна, тому що зовнішній CLI не вміє їх
адресувати. Невідомі формати lock лише повідомляються.

Для відкату спочатку збережіть конфігурацію, потім перевстановіть потрібний тег з тими.
ж навичками та агентами, наприклад:

```shell
npx skills@1.5.22 add kolabse/skills@v1.1.0 --skill verify-before-push --agent codex --copy --global -y
```

Зниження конфігурації не підтримується без явної документації релізу.
Відновлення старих файлів досвіду не знижує config; при несумісності
відновіть резервну копію.

## Встановлення або оновлення локального Codex-плагіна для розробки

Для локальної розробки створіть або оновіть персональний ринок, скопіюйте
плагін, додайте cachebuster Codex та активуйте:

```shell
python scripts/install_personal_plugin.py --activate
```

Установник зберігає сторонні marketplace entries і не править manifest
репозиторію. Це шлях розробки, а не звичайна Git marketplace установка.
Повторюйте після оновлення checkout та починайте нове завдання Codex.`--json`показує версію та шляхи встановлення.

## Доступні навички

Stable і experimental навички перераховані у`skill-catalog.json`. Їх
конфігурація, safety boundaries та CLI дотримуються політики
[CONTRIBUTING.md](CONTRIBUTING.md). Каталог оголошує scope, read-only status,
можливості, залежності та інтеграції; stateful-навички мають ідемпотентний
configure, schema та migration для версійної конфігурації.

Каталог згруповано за основним призначенням для користувача у наведеному нижче
порядок пріоритету. У кожного навички рівно одна основна категорія. Незалежні
теги описують етап життєвого циклу, область дії, поведінку та інтеграцію;
статус зрілості від них залежить. Авторитетні машиночитані призначення та
контрольований словник знаходяться в
[`skill-catalog.json`](../../../skill-catalog.json) і перевіряються по
[`schemas/skill-catalog.schema.json`](../../../schemas/skill-catalog.schema.json).

Контрольовані групи тегів:

- Етап життєвого циклу:`prepare`, `investigate`, `implement`, `verify`,
  `publish`, `operate`, `document`і`handoff`;
- сфера застосування:`project`, `repository`, `multi-repository`, `workstation`,
  `external-service`і`skill-collection`;
- Поведінка:`read-only-planning`, `mutation`, `evidence-producing`,
  `orchestration`і`notification`;
- Інтеграція:`git`, `github`, `telegram`, `google-drive`і`yandex-cloud`.

### Розробка та якість коду

#### `develop-with-test-first-evidence`(experimental)

Реалізує поведінку через підтверджений red-green-refactor.

**Що робить:** фіксує focused test, що падає з потрібної причини до коду;
прив'язує focused та broader green до фінального стану та валідує evidence.

**Чого не робить:** не створює red поломкою сторонньої поведінки, не називає
наступні тести test-first та не приховує старі/environment/final failures.

**Виклик:**

```text
$develop-with-test-first-evidence Реалізуй поведінку із зафіксованим циклом red-green-refactor.
```

#### `review-code-changes`(experimental)

Перевіряє задану зміну на коректність, security, reliability та compatibility.

**Що робить:** визначає baseline/change, повідомляє evidence-backed findings з
Impact, trigger, priority та точне місцезнаходження, розкриває uncertainty і test gaps.

**Чого не робить:** не видає смакові переваги за дефекти, не реалізує та
не публікує findings без дозволу та не замінює review загальним поясненням.

**Виклик:**

```text
$review-code-changes Перевір цю гілку відносно baseline і повідом про підтверджені дефекти.
```

#### `diagnose-software-defects`(experimental)

Досліджує failures та regressions до підтвердженої причини або ранжованих гіпотез.

**Що робить:** обмежує та безпечно відтворює симптом, перевіряє
конкуруючі гіпотези та повідомляє root cause, умови, blast radius, confidence
та план перевірки виправлення.

**Чого не робить:** не виводить причинність кореляції, не мутує production,
не знищує evidence та не реалізує speculative fix замість діагностики.

**Виклик:**

```text
$diagnose-software-defects Діагностуй regression і відокрем evidence від гіпотез.
```

#### `resolve-git-conflicts`(experimental)

Семантично дозволяє схвалені merge/rebase/cherry-pick конфлікти.

**Що робить:** вивчає active operation, base, сторони та кожний unmerged path;
об'єднує тільки зрозумілу поведінку, перевіряє paths та явно називає наступний
Git-крок.

**Чого не робить:** не вважає звичайну divergence файловим конфліктом, не
stash/reset/abort/continue/force-push автоматично, не stage стороннє та не
вгадує неоднозначні binary/generated/schema рішення.

**Виклик:**

```text
$resolve-git-conflicts Розв'яжи активні конфлікти по файлах і перевір результат.
```


### Репозиторії та доставка змін

#### `synchronize-git-repositories`

Встановлює актуальний remote-стан без перезапису локальної роботи.

**Що робить:** знаходить тільки репозиторії, що відносяться до завдання, fetch їх
tracked remotes, fast-forward чистих behind-only гілок, повідомляє небезпечні
стану та при вимогі публікує feature-гілка від перевіреного main до edit.

**Чого не робить:** автоматично не stash/reset/rebase/merge/clean/switch і не
force-push; не приховує divergence та не сканує сторонні репозиторії.

**Виклик:**

```text
$synchronize-git-repositories Налаштуй політику синхронізації репозиторіїв проєкту.
```

#### `verify-before-push`

Прив'язує оголошені проектом перевірки до точного Git стану push.

**Що робить:** налаштовує repository-owned policy поза навичкою, запускає checks
і записує evidence для commits, worktree, upstream та config; fail closed у
відсутнє, пошкоджене або stale evidence.

**Чого не робить:** не блокує неохоплені репозиторії, не розбирає
довільний shell і не вважає старий успішний check актуальним.

**Виклик:**

```text
$verify-before-push Налаштуй політику перевірок цього проєкту.
```

#### `coordinate-code-documentation-repositories`(experimental)

Координує одну зміну, що перевіряється, коли код і канонічна документація
живуть у різних репозиторіях.

**Що робить:** визначає оголошені ролі репозиторіїв, створює read-only plan
на вихідних commits, вимагає evidence за налаштованими темами і перевіряє обидві
опубліковані ідентичності та cross-repository traceability.

**Чого не робить:** не вгадує ролі за іменами, не замінює документацію
дайджестом, сам не редагує/commit/push/merge та не вважає наявність файлів
доказом смислової згоди.

**Виклик:**

```text
$coordinate-code-documentation-repositories Реалізуй зміну в оголошених репозиторіях коду й документації та перевір обидва опубліковані результати.
```

#### `execute-configured-gitflow-releases`(experimental)

Виконує standard та hotfix routes за оголошеним проектом GitFlow-контрактом.

**Що робить:** читає гілки, remote, gates та default route з versioned config;
фіксує план на commits; застосовує загальні gates та перевіряє production,
deployment і обов'язкове hotfix reintegration.

**Чого не робить:** не вгадує імена гілок і не вибирає hotfix за замовчуванням;
не підтримує trunk flow або спеціальний ланцюжок цієї колекції; не оминає
захист, що не переписує історію і не завершує hotfix до reintegration.

**Виклик:**

```text
$execute-configured-gitflow-releases Виконай оголошений стандартний реліз і перевір production identity.
$execute-configured-gitflow-releases Виконай явний hotfix і перевір його повернення в development line.
```

#### `execute-verified-development-lifecycle`(experimental)

Планує та перевіряє оголошений проектом шлях від feature preparation до
reviewed dev integration, delivery observation, документації та cleanup.

**Що робить:** у managed update або першому викликі створює консервативний
project config з Git roots, upstream refs, checks і документації
та повідомляє всі defaults; фіксує digest-bound plan до edit, просуває ordered
checkpoints по retained evidence; перевіряє feature-before-edit, test-first,
preflight, review, push, pipeline, docs, integration, production delegation,
delivery, smoke, notifications і cleanup; після помилки повертає до оголошеної
точці та інвалідів downstream evidence.

**Чого не робить:** не вгадує provider-specific adapters, repo roles,
delivery policy або authorization при неоднозначних даних;
сам не push/open/merge/deploy/notify/edit docs/delete; production залишається у
схваленого процесу начебто`$execute-configured-gitflow-releases`.

Спочатку встановіть обов'язкові`$synchronize-git-repositories`,
`$develop-with-test-first-evidence`, `$verify-before-push`і`$review-code-changes`. Відсутній project-owned v1 lifecycle contract
створюється з фактів, що спостерігаються, до першого плану; перевірте та уточніть defaults,
якщо правила проекту задають більш точну політику. Опціональні навички
встановлюються лише для включених checkpoints.

**Виклик:**

```text
$execute-verified-development-lifecycle Сплануй і перевір зміну за налаштованим development lifecycle проєкту.
```


### Знання та безперервність проекту

#### `maintain-work-log`

Веде канонічний датований журнал`docs/reports/work-log.md`.

**Що робить:** записує суттєві зміни, операції, діагностику,
рішення, перевірки, blockers та rollback; зберігає формат та відновлює
історію лише за доступною evidence.

**Чого не робить:** не запускається без вимоги, не записує секрети,
application logs, time tracking чи непідтверджені події.

**Виклик:**

```text
$maintain-work-log Налаштуй ведення датованого журналу проєкту.
```

#### `maintain-project-digest`(experimental)

Веде щоденний зрозумілий користувачам дайджест завершених змін.

**Що робить:** групує зміни поточної дати за можливостями, поліпшеннями,
виправлень, безпеки, документації та важливої поведінки; пише коротко,
пропускає порожні категорії, не змінює минулі дати та захищає спільний запис.

**Чого не робить:** не вибирає неоднозначне місце документації, не пише
плани та внутрішню активність, не замінює work log/changelog/release notes та
не переписує минулих періодів.

**Виклик:**

```text
$maintain-project-digest Додай завершені сьогодні користувацькі зміни до дайджесту проєкту.
```

#### `sync-project-context`

Синхронізує приватний очищений стан проекту та завдань між комп'ютерами.
Навичка stable після двох незалежних real-device Google Drive прогонів.

**Що робить:** зберігає immutable checkpoints у схваленій папці або Drive;
неуточнений запит за замовчуванням використовує підключений Google Drive; веде
opaque stream з baseline/deltas, visible titles, decisions і Git fingerprints;
планує task/batch save, restore та bidirectional sync; перевіряє snapshots,
readback та project identity; зберігає окремий environment manifest для
правил, навичок, плагінів та безпечних settings, яких немає в Git.

**Чого не робить:** не копіює source, diffs, raw transcripts, hidden reasoning,
credentials, OAuth або установки; не дублює Git-owned environment та не
перезаписує destination rules; в metadata-тільки не включає branch/path.

Codex Desktop підтримує batch discovery/create/rename та Drive connector.
Claude Code використовує portable checkpoints, local-folder та environment core,
але не перевіряє sessions та fail closed для Codex-only batch операцій.

**Виклик:**

Одноразове налаштування кожного комп'ютера:

```text
$sync-project-context Налаштуй цей клон у режимі metadata-only. За замовчуванням використовуй підключений Google Drive, якщо я явно не виберу інший канал.
```

Потім:

```text
$sync-project-context Збережи стан поточного завдання.
$sync-project-context Віднови всі завдання проєкту на цьому комп'ютері.
$sync-project-context Синхронізуй усі завдання двонапрямно й покажи конфлікти до застосування.
```

У Claude Code заміняйте`$`на`/`.


### Координація та комунікації

#### `orchestrate-agent-work`(experimental)

Координує явно дозволених subagents та відповідає за загальний результат.

**Що робить:** поділяє паралельну роботу на обмежені непересічні
завдання, спостерігає та узгоджує результати, перевіряє інтеграцію.

**Чого не робить:** не делегує без дозволу, не передає approvals, secrets,
destructive cleanup або зовнішні mutations і не вважає окремі результати
доказом успішної інтеграції.

**Виклик:**

```text
$orchestrate-agent-work Делегуй незалежні підзавдання агентам і перевір спільний результат.
```

#### `synchronize-team-skills`(experimental)

Синхронізує глобально встановлені навички учасників команди із перевіреним
manifest у документації проекту; Налаштування проекту залишаються локальними.

**Що робить:**

- створює чи читає`team-agent-skills.md`у вибраній директорії документації;
- порівнює вимоги для Codex та Claude Code з перевіреними глобальними копіями;
- без змін показує відсутні, старі, новіші, неперевірені,
  проектні копії, що перекривають ширші області, та додаткові навички;
- будує пов'язаний з digest manifest план встановлення однієї версії колекції;
- після підтвердження встановлює лише узгоджений набір та перевіряє його.

**Чого не робить:**

- не перетворює випадковий стан одного комп'ютера на стандарт команди;
- не зберігає secrets, user config, шляхи комп'ютера або plugin authentication;
- не видаляє додаткові навички, не знижує версії та не видаляє старі
  проектні копії без підтвердженої централізації;
– не стверджує, що відкритий діалог вже завантажив нові навички.

**Виклик:**

```text
$synchronize-team-skills Перевір навички проєкту за командним manifest.
$synchronize-team-skills Покажи план і синхронізуй мої навички з документацією команди.
$synchronize-team-skills Додай maintain-project-digest до командного набору навичок.
```

#### `report-skill-feedback`(experimental)

Після явної згоди готує обмежений знеособлений звіт про застосування навички, що спостерігається. Чернетка не містить код, листування, секрети, імена, шляхи та URL. Він повністю показується користувачеві і відправляється в`kolabse/skills`лише після окремого підтвердження; Issue залишається пов'язаним із обліковим записом GitHub.

**Aufruf / Invocation:**

```text
$report-skill-feedback Підготуй знеособлений попередній звіт про це використання навички; поки не надсилай його.
```

#### `notify-via-telegram`

Відправляє Telegram оновлення життєвого циклу довгих завдань агента.

**Що робить:** повідомляє start/milestone/problem/blocker/completion; налаштовує
бота і чат, пропонує безпечну Windows-форму, зберігає credential в user config,
підтримує окремий чат/topic проект та експортує secret-free routing для`sync-project-context`; працює на Python standard library.

**Чого не робить:** не поміщає token у чат, shell history або repo; не переносить
bot auth між ПК, не повідомляє проти прохання користувача і не є
Framework розробки Telegram-ботів.

**Виклик:**

```text
$notify-via-telegram Налаштуй Telegram-сповіщення для тривалих завдань.
$notify-via-telegram Налаштуй проєкт на сповіщення лише в командний чат замість глобального каналу.
```


### Інфраструктура та експлуатація

#### `operate-yandex-cloud`

Працює з явно налаштованою інфраструктурою Yandex Cloud у scope проекту.

**Що робить:** зберігає Cloud/Folder IDs у project config, локальний`yc`profile
у ignored config; перевіряє tools/versions/context; підтримує scoped CLI,
SSH, Terraform, Ansible, Helm, Kubernetes, deployment, DB, storage, DNS,
Monitoring, backup та incidentworkflows.

**Чого не робить:** не виводить Yandex Cloud із загального SSH/Kubernetes запиту, не
зберігає credentials в shared config і не мутує до визначення target,
context і authorization.

**Виклик:**

```text
$operate-yandex-cloud Налаштуй проєкт для роботи з Yandex Cloud.
```


### Розвиток колекції навичок

#### `discover-skill-candidates`(experimental)

Знаходить ідеї, що перевикористовуються, навичок в обмежених правилах і контексті, не
створюючи навичку.

**Що робить:** інвентаризує project-relative`AGENTS.md`з Git/line
provenance; з дозволу вивчає документацію, вибрані файли, обмежену
історію та підтверджені summaries чатів або handoff; ранжує кандидатів та
порівнює з каталогами; пропонує contribution, локальну реалізацію або
відстрочення; експортує очищений digest-bound пакет.

**Чого не робить:** не змінює правила, не створює і не встановлює навички; не
перераховує чати, не читає raw transcripts і не сканує код широко; не
експортує правила, шляхи, секрети, URL та email; не просуває одноразові або
чутливі угоди без review.

**Виклик:**

```text
$discover-skill-candidates Проаналізуй локальні правила проєкту й підготуй підтверджений список ідей навичок, нічого не створюючи.
```

#### `release-skill-collection`

Планує, перевіряє, аудитує та очищує детерміновані релізи колекції.

**Що робить:** перевіряє версії, changelog, Git, тести, security, архіви та
checksums; валідує commit-bound gates; аудитує assets, manifest та
attestation; доводить представленість гілок перед cleanup.

**Чого не робить:** не передбачає дозвіл на commit/tag/push/workflow; не
переміщує тег, не замінює assets і не видаляє гілки на ім'я або stale plan.

**Виклик:**

```text
$release-skill-collection Сплануй і перевір реліз vX.Y.Z, але поки не публікуй.
```

## Підтримувані композиції

Каталог визначає три впорядковані процеси:

- `protected-push`: синхронізація, потім актуальне verification evidence;
-`yandex-cloud-operation`: синхронізація та scoped cloud operation;
-`skill-collection-release`: синхронізація, local release verify та pre-push evidence.

Work log та Telegram необов'язкові. Required steps fail closed; необов'язкові
помилки не змінюють основний результат.`scripts/compose_skills.py`формує plan,
а`--evidence`зі схемами`schemas/composition-evidence.schema.json`і`schemas/composition-result.schema.json`перевіряє порядок та результати.

## Додавання навички

Виконайте [CONTRIBUTING.md](CONTRIBUTING.md) та
[`templates/skill-template.md`](../../../templates/skill-template.md). Кожен
навик має запис у`skill-catalog.json`з власником, платформами, status,
license та provenance. Project config зберігається поза встановленою папкою.

Не додавайте repository-level установник однієї навички. Для керованої
установки ChatGPT/Codex колекція пакується OpenAI-плагіном додатково до
cross-agent layout.

Локальні перевірки:

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py
```

Підготувати blind trigger suite:

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
```

Suite містить тільки імена, публічні descriptions, opaque IDs та prompts без
labels і author reasons. Selector повертає strict JSON; оцінка:

```shell
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

`run -- <command>`передає suite через stdin. Credentials не повинні бути у
arguments.`.trigger-evals/`ігнорується. Великі suites розбиваються на
digest-bound batches по 64; розмір змінюється через`--batch-size`.

Перед релізом використовуйте окремо версійний digest-locked holdout:

```shell
python scripts/trigger_evals.py prepare \
  --corpus release-holdout \
  --output .trigger-evals/release-holdout.json
```

Порівняння тільки з baseline тієї ж версії:

```shell
python scripts/trigger_evals.py compare \
  --candidate .trigger-evals/candidate-report.json \
  --markdown-output .trigger-evals/comparison.md
```

Різні assertion digests відхиляються; порівнюються загальні та per-skill metrics.
За промовчанням baseline береться з каталогу. Для недетермінованого selector
зберіть непарне число мінімум із трьох blind runs:

```shell
python scripts/trigger_evals.py aggregate \
  --corpus release-holdout \
  --predictions run-1.json run-2.json run-3.json \
  --predictions-output .trigger-evals/aggregate.json \
  --json-output .trigger-evals/candidate-report.json
```

## Перевірка релізу

Реліз включає deterministic ZIP та TAR.GZ,`release-manifest.json`і`SHA256SUMS`. Завантажте чотири assets в одну папку та виконайте:

```shell
python scripts/build_release.py --verify <download-directory>/SHA256SUMS
```

GitHub показує SHA-256 digest кожного asset і публікує artifact
attestations. Перевірка завантаженого файлу:

```shell
gh attestation verify <artifact> --repo kolabse/skills
```
