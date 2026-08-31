# kolabse/skills

[English](../../../README.md) | [Русский](../ru/README.md) | [Español](../es/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Português (Brasil)](../pt-BR/README.md) | 日本語 | [Italiano](../it/README.md) | [한국어](../ko/README.md) | [简体中文](../zh-CN/README.md) | [Türkçe](../tr/README.md)

この文書は日本語訳です。内容に相違がある場合は[英語版](../../../README.md)を正とします。

kolabse が管理する、再利用可能なエージェントスキルです。

[Apache License 2.0](../../../LICENSE) に基づいて提供されます。Copyright 2026 kolabse.

## 目次

- [スキルのインストール](#スキルのインストール)
  - [Git マーケットプレイスからのインストール](#git-マーケットプレイスからのインストール)
- [インストール済みスキルの更新](#インストール済みスキルの更新)
  - [リポジトリをクローンせずに実行する](#リポジトリをクローンせずに実行する)
  - [グローバルインストールの調査](#グローバルインストールの調査)
- [ローカル開発用 Codex プラグインのインストールまたは更新](#ローカル開発用-codex-プラグインのインストールまたは更新)
- [利用可能なスキル](#利用可能なスキル)
  - [開発とコード品質](#開発とコード品質)
    - [`develop-with-test-first-evidence`](#develop-with-test-first-evidence-実験的)
    - [`review-code-changes`](#review-code-changes-実験的)
    - [`diagnose-software-defects`](#diagnose-software-defects-実験的)
    - [`resolve-git-conflicts`](#resolve-git-conflicts-実験的)
  - [リポジトリと変更の提供](#リポジトリと変更の提供)
    - [`synchronize-git-repositories`](#synchronize-git-repositories)
    - [`verify-before-push`](#verify-before-push)
    - [`coordinate-code-documentation-repositories`](#coordinate-code-documentation-repositories-実験的)
    - [`execute-configured-gitflow-releases`](#execute-configured-gitflow-releases-実験的)
    - [`execute-verified-development-lifecycle`](#execute-verified-development-lifecycle-実験的)
  - [プロジェクトの知識と継続性](#プロジェクトの知識と継続性)
    - [`maintain-work-log`](#maintain-work-log)
    - [`maintain-project-digest`](#maintain-project-digest-実験的)
    - [`sync-project-context`](#sync-project-context)
  - [調整とコミュニケーション](#調整とコミュニケーション)
    - [`orchestrate-agent-work`](#orchestrate-agent-work-実験的)
    - [`synchronize-team-skills`](#synchronize-team-skills-実験的)
    - [`notify-via-telegram`](#notify-via-telegram)
  - [インフラストラクチャと運用](#インフラストラクチャと運用)
    - [`operate-yandex-cloud`](#operate-yandex-cloud)
  - [スキルコレクションの発展](#スキルコレクションの発展)
    - [`discover-skill-candidates`](#discover-skill-candidates-実験的)
    - [`release-skill-collection`](#release-skill-collection)
- [対応するスキル構成](#対応するスキル構成)
- [スキルを追加する](#スキルを追加する)
- [リリースを検証する](#リリースを検証する)

## スキルのインストール

複数のエージェントに対応する [`skills`](https://skills.sh) CLI を使用して、
現在のプロジェクトに 1 つ以上のスキルをインストールします。

```shell
npx skills@latest add kolabse/skills
```

CLI は `skills/` 内のフォルダーを検出し、インストールするスキルを選択させ、
選択したコーディングエージェントにコピーします。これは外部のインストーラーです。
このリポジトリ自体が npm パッケージを公開したり実行したりすることはありません。

Codex ユーザーは、代わりに `$skill-installer` に、このリポジトリからスキルを
インストールするよう依頼できます。たとえば、次の場所を指定します。

```text
https://github.com/kolabse/skills/tree/main/skills/operate-yandex-cloud
```

非対話型インストールでは、対象エージェントを明示的に選択します。

```shell
npx skills@1.5.22 add kolabse/skills --agent codex --copy -y
npx skills@1.5.22 add kolabse/skills --agent claude-code --copy -y
```

プロジェクトへのインストールでは、エージェントに「選択したスキルをインストールし、
既存のルールを置き換えずに、不足しているプロジェクトの既定値を初期化してください」と依頼します。
外部インストーラーの完了後、使用するエージェントの Git ルールを初期設定します。

```shell
python .agents/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent codex --apply --yes --json
python .claude/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent claude-code --apply --yes --json
```

規約が未設定の場合、接頭辞は `feature/`、`bugfix/`、`release/`、`hotfix/`、
コミットタイプは `feat`、`fix`、`refactor`、`docs`、`test`、`chore` が既定値です。
プロジェクトで明示された接頭辞、ブランチの役割、コミット形式が優先されます。
永続的なブランチや Git フックは作成しません。プロジェクトスコープの管理付き更新でも、
該当スキルに同じ初期設定を適用します。未確認の更新では、その計画だけを行います。

プロジェクトスコープのインストールでは、観測可能な既定値で十分な場合、
ライフサイクル契約を直ちに初期化します。使用するエージェントのパスを選んでください。

```shell
python .agents/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent codex --apply --yes --json
python .claude/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent claude-code --apply --yes --json
```

マーケットプレイスやプラグインによるインストールはグローバルであり、有効なプロジェクトルートがないため、
スキルがプロジェクトで初めて使われたときに、同じ初期設定を行います。

Codex は `.agents/skills/` 内のプロジェクトスキルを検出し、`$skill-name` として呼び出します。
Claude Code は `.claude/skills/` 内で検出し、`/skill-name` として呼び出します。
スキルの指示と同梱スクリプトは共有され、エージェント固有のルールファイルと呼び出し構文は設定時に選択されます。

このリポジトリは、ChatGPT/Codex と Claude Code 向けに、スキルのみを含む `kolabse-skills`
プラグインとしてもパッケージ化されています。`skills/` 内のすべてのフォルダーが含まれます。
エージェント横断の `npx skills` インストールも、どちらのプラグイン形式とも独立して利用できます。

### Git マーケットプレイスからのインストール

Codex ユーザーは、次のコマンドでリポジトリのマーケットプレイスを登録し、コレクション全体をインストールできます。

```shell
codex plugin marketplace add kolabse/skills --ref main
codex plugin add kolabse-skills@kolabse
```

Git スナップショットを更新し、現行のプラグインバージョンを再インストールするには、次を実行します。

```shell
codex plugin marketplace upgrade kolabse
codex plugin add kolabse-skills@kolabse
```

Claude Code ユーザーは、次のコマンドで同じリポジトリを登録し、プラグインをインストールできます。

```shell
claude plugin marketplace add kolabse/skills
claude plugin install kolabse-skills@kolabse
```

`claude plugin marketplace update kolabse` で明示的に更新するか、Claude Code で
マーケットプレイスの自動更新を有効にします。インストールまたは更新後は、現在のスキルセットを
検出できるよう、新しいエージェントセッションを開始してください。

マーケットプレイスのカタログは、
[`.agents/plugins/marketplace.json`](../../../.agents/plugins/marketplace.json) と
[`.claude-plugin/marketplace.json`](../../../.claude-plugin/marketplace.json) です。
プラグインのペイロードは、
[`.codex-plugin/plugin.json`](../../../.codex-plugin/plugin.json) と
[`.claude-plugin/plugin.json`](../../../.claude-plugin/plugin.json) に記載されています。
両カタログは、正規の `kolabse/skills` リポジトリの `main` から取得します。
リリースのバージョン管理については、引き続きプラグインマニフェストが正となります。

公開掲載用の資料はソースとともに管理されています。[サポート](SUPPORT.md)、
[プライバシーポリシー](PRIVACY.md)、[利用規約](TERMS.md)、および再現可能な
[マーケットプレイス提出用パケット](../../../docs/marketplace-submissions/) を参照してください。
公式ディレクトリへの掲載は、引き続きレビューを経たメンテナーの操作です。
Git マーケットプレイスからのインストールに、ディレクトリの承認は必要ありません。

Claude Code では、テスト時に `claude --plugin-dir <collection-root>` を使って、
展開したリリースまたは信頼できるチェックアウトを直接読み込めます。通常の個人利用またはプロジェクト利用では、
Git マーケットプレイスか、上記の明示的な `npx skills ... --agent claude-code` コマンドを推奨します。
Claude Code は `AGENTS.md` ではなく `CLAUDE.md` を読みます。プロジェクトに共有の `AGENTS.md`
ルールがすでにある場合は、`@AGENTS.md` を含む最小限の `CLAUDE.md` にすることで、正規のルール文書を 1 つに保てます。

## インストール済みスキルの更新

`skills` CLI は GitHub ソースとコンテンツハッシュを `skills-lock.json` に記録します。
記録されたソースから、プロジェクトの全インストールを更新します。

```shell
npx skills@1.5.22 update -p -y
```

1 つのスキルまたはグローバルインストールを更新するには、次を実行します。

```shell
npx skills@1.5.22 update verify-before-push -p -y
npx skills@1.5.22 update -g -y
```

参照を指定しない `kolabse/skills` ロックは、リポジトリの既定ブランチを追跡し、
コレクションのリリースを固定しません。更新により置き換えられる可能性があるため、
`.agents/skills/` 配下にコピーされたファイルを編集しないでください。
プロジェクト設定とユーザー設定は、インストール済みスキルフォルダーの外に保持されます。

クローンしたチェックアウトまたはリリースアーカイブから、1 回の明示的な操作で更新と
対応するプロジェクト設定の移行を行えます。

```shell
python scripts/manage_installed_skills.py update --project-path . --yes --migrate
python scripts/manage_installed_skills.py doctor --project-path . --json
```

外部インストーラーの起動や設定の変更を行わずに、正確な選択内容を事前確認します。

```shell
python scripts/manage_installed_skills.py plan --project-path . --json
```

計画には、ソースの識別情報、現行および対象バージョン、来歴、移行候補、
`update`、`unchanged`、`adopt-and-update`、`blocked` の各操作が報告されます。
そのスキーマは `schemas/manager-plan.schema.json` です。`update` に `--json` を追加すると、
更新と移行の結果は `schemas/manager-result.schema.json` に従います。

名前を指定しない場合、マネージャーはプロジェクトのロックからインストール済みの kolabse スキルを解決し、
その名前を外部 CLI に明示的に渡します。無関係なプロジェクトスキルが更新対象に含まれることはありません。
グローバル更新では、コレクションのスキル名を明示する必要があります。
プロジェクト更新は、`doctor` と同じ、安全側に停止する診断で完了します。
プロジェクト更新に `execute-verified-development-lifecycle` が含まれる場合、マネージャーは、
プロジェクトの事実が十分であれば不足している設定も初期化し、設定結果として
`created`、`configured`、または `blocked` を返します。

Telegram のユーザー設定も移行する場合に限り、`--include-user-config` を追加します。
`status` と `doctor` は読み取り専用です。`migrate` は既存の設定ファイルだけを変更し、未使用のスキルは設定しません。
インストール済みの各スキルには `collection-metadata.json` が付属するため、外部のロック形式に
バージョンフィールドがなくても、`status` はコレクションのバージョンを報告します。
また、`provenance_status` も報告します。`verified` には、コレクションメタデータと、正規の GitHub
または内容が検証済みのローカルロックソースの両方が必要です。`legacy-unverified` はメタデータ導入前の
インストールを示し、`mismatch` は決して更新しません。ローカルの識別にはディレクトリ名ではなく、
プラグインマニフェスト、カタログ、スキル内容を使うため、チェックアウトの名前は変更できます。

v1.2 より前のメタデータを持たないインストールは、報告されたソースを確認した後にのみ引き継ぎます。

```shell
python scripts/manage_installed_skills.py status --project-path . --json
python scripts/manage_installed_skills.py update --project-path . --yes --adopt-legacy
```

引き継ぎフラグは、任意のファイルを無条件に承認するものではありません。ソースがすでに `kolabse/skills` に
正規化できるか、ローカルチェックアウトの検証に合格し、通常の更新後診断でインストール済みメタデータを検証する必要があります。
外部 CLI は、`sourceType: local` の開発用ロックをその場で更新しません。
マネージャーは、この CLI の無操作を失敗として扱います。元の `--skill` と `--agent` の選択を使い、
ローカルソースからそのスキルを再追加してください。

### リポジトリをクローンせずに実行する

信頼できるリリースまたはこのリポジトリから `scripts/bootstrap_update.py` をダウンロードします。
最新の安定リリースを解決し、リリース ZIP を `SHA256SUMS` と GitHub のビルド来歴に照らして検証した後、
分離された一時展開先からマネージャーを実行します。

```shell
python bootstrap_update.py doctor --json
python bootstrap_update.py plan --json
python bootstrap_update.py update --yes --migrate --json
```

バージョンを固定するには `--release v1.15.0` を使用します。ブートストラップにはアテステーション検証用の
`gh` が必要で、完了時に一時ディレクトリを削除します。オフラインキャッシュには、`--offline-archive` と
`--offline-checksums` の両方を指定します。`gh` から GitHub に接続できる場合、来歴の検証は引き続き必須です。
`--allow-unattested-offline` は明示的な機能制限モードであり、キャッシュされたチェックサムだけを検証します。
別途信頼性が確認された経路で転送された成果物にのみ使用してください。
ロールバックは、以前のリリースを選び、既存のロールバック手順に従って行います。設定の移行は引き続き前方のみです。

### グローバルインストールの調査

対応するグローバル状態は、意図的に共有の `~/.agents/.skill-lock.json` v3 ロックに限定しています。
インストール済みペイロードは、Codex では `~/.agents/skills`、Claude Code では `~/.claude/skills` にあります。
マネージャーは他のユーザーディレクトリを走査しません。Codex が既定のままです。
Claude のペイロード配置には `--agent claude-code` を渡します。

```shell
python scripts/manage_installed_skills.py status --scope global --json
python scripts/manage_installed_skills.py doctor --scope global --json
python scripts/manage_installed_skills.py plan verify-before-push --scope global --json
python scripts/manage_installed_skills.py update verify-before-push --scope global --yes --json
python scripts/manage_installed_skills.py status --scope global --agent claude-code --json
```

テスト用、または明示的に移動した互換性のある配置を読み取り専用で調査するには、`--global-root` を使用します。
外部 CLI が対象にできないため、移動したルートは更新できません。未知のロック形式は変更せずに報告します。

スキルファイルをロールバックするには、まずプロジェクト設定とユーザー設定をバックアップし、
元のインストールと同じスキルおよび対象エージェントを指定して、必要なリリースタグを再インストールします。例：

```shell
npx skills@1.5.22 add kolabse/skills@v1.1.0 --skill verify-before-push --agent codex --copy -y
```

リリースでダウングレードが明記されていない限り、設定の移行は前方のみです。
古いスキルファイルを復元しても設定はダウングレードされません。以前のリリースが新しい形式を読めない場合は、
対応する設定のバックアップを復元してください。

## ローカル開発用 Codex プラグインのインストールまたは更新

ローカルでプラグインを開発する場合は、既定の個人用マーケットプレイスのエントリを作成または更新し、
プラグインをローカルのプラグインディレクトリにコピーし、Codex のキャッシュバスターを追加して有効化します。

```shell
python scripts/install_personal_plugin.py --activate
```

インストーラーは、他の個人用マーケットプレイスのエントリを保持し、リポジトリのマニフェストは編集しません。
これは開発向けの代替経路であり、通常の Git マーケットプレイスによるインストールではありません。
チェックアウトを更新した後に再実行し、更新済みスキルを読み込むため、新しい Codex タスクを開始します。
インストール済みバージョン、プラグインのパス、マーケットプレイスのパスと名前を記録するには、`--json` を使用します。

## 利用可能なスキル

安定版のスキルと実験的な追加スキルは、`skill-catalog.json` で識別できます。
プロジェクト向けの設定パス、安全上の制約、文書化されたコマンドインターフェイスは、
[CONTRIBUTING.md](CONTRIBUTING.md) の互換性ポリシーに従います。

現在、各カタログエントリは、設定スコープ、読み取り専用の JSON 状態確認コマンド、機能、前提条件、
任意の連携を宣言します。状態を持つスキルは冪等な設定コマンドも宣言し、
バージョン付き JSON/YAML 設定は、スキルと並べて JSON Schema と移行コマンドを公開します。

カタログは、ユーザーにとっての主要な目的ごとに、以下の優先順位で分類しています。
各スキルは主要カテゴリをちょうど 1 つ持ちます。独立したタグでライフサイクル段階、対象範囲、動作、連携を記述し、
成熟度ステータスは独立しています。正規の機械可読な割り当てと統制語彙は
[`skill-catalog.json`](../../../skill-catalog.json) にあり、
[`schemas/skill-catalog.schema.json`](../../../schemas/skill-catalog.schema.json) に照らして検証されます。

統制されたタグの軸は次のとおりです。

- ライフサイクル段階：`prepare`、`investigate`、`implement`、`verify`、`publish`、
  `operate`、`document`、`handoff`。
- 対象範囲：`project`、`repository`、`multi-repository`、`workstation`、
  `external-service`、`skill-collection`。
- 動作：`read-only-planning`、`mutation`、`evidence-producing`、`orchestration`、`notification`。
- 連携：`git`、`github`、`telegram`、`google-drive`、`yandex-cloud`。

### 開発とコード品質

#### `develop-with-test-first-evidence` 実験的

証拠に裏付けられた red-green-refactor サイクルを通じて動作を実装します。

**行うこと：**

- 実装前に、意図した動作上の理由で失敗する焦点を絞ったテストを記録します。
- 焦点を絞ったテストと、より広範なテストの成功結果を、最終的な変更状態に結び付けます。
- 同梱のスキーマとヘルパーで、永続的な証拠を検証します。

**行わないこと：**

- 無関係な動作を壊して、テストの失敗結果を作り出すこと。
- 実装後のテストを、テストファースト開発と呼ぶこと。
- 既存の失敗、環境に起因する失敗、最終状態での失敗を隠すこと。

**呼び出し方法：**

```text
$develop-with-test-first-evidence Implement this behavior with a recorded red-green-refactor cycle.
```

#### `review-code-changes` 実験的

定義された変更をレビューし、対処可能な正確性、セキュリティ、信頼性、互換性の欠陥を見つけます。

**行うこと：**

- 正確なベースラインと変更後の状態を確定します。
- 影響、発生条件、優先度、絞り込んだ位置を添えて、証拠に裏付けられた指摘を報告します。
- 不確実性と重要なテストの不足を明示します。

**行わないこと：**

- スタイルの好みや裏付けのない推測を欠陥として報告すること。
- 別途の承認なしに、指摘の実装、コメントの公開、レビューの承認を行うこと。
- 対象を限定したレビューを、一般的なコード説明で代替すること。

**呼び出し方法：**

```text
$review-code-changes Review this branch against its declared baseline and report actionable findings.
```

#### `diagnose-software-defects` 実験的

障害や回帰を調査し、裏付けのある因果説明、または順位付けした仮説を示します。

**行うこと：**

- 症状の範囲を限定し、可能であれば安全に再現します。
- 関連する証拠を使い、競合する仮説を検証します。
- 根本原因、寄与する条件、影響範囲、確信度、修正の検証計画を報告します。

**行わないこと：**

- 相関関係から因果関係を推測すること。
- 本番環境を変更したり、失敗の証拠を破棄したりすること。
- 診断だけを依頼されたときに、推測に基づく修正を実装すること。

**呼び出し方法：**

```text
$diagnose-software-defects Diagnose this regression and distinguish evidence from hypotheses.
```

#### `resolve-git-conflicts` 実験的

無関係な作業を保持しながら、承認済みの merge、rebase、cherry-pick の競合を意味に基づいて解決します。

**行うこと：**

- 実行中の操作、ベース、双方の変更、未マージの各パスを調査します。
- 統合後に意図される動作を理解できる競合だけを調整します。
- 解決したパスを検証し、残る Git 操作の手順を明示します。

**行わないこと：**

- 通常のリポジトリの分岐を、ファイル競合のタスクとして扱うこと。
- 自動で stash、reset、abort、continue、force-push を行ったり、無関係なパスをステージしたりすること。
- 生成物、バイナリ、スキーマ、製品仕様に関する曖昧な判断を、推測で進めること。

**呼び出し方法：**

```text
$resolve-git-conflicts Resolve the active merge conflicts path by path and validate the result.
```


### リポジトリと変更の提供

#### `synchronize-git-repositories`

ローカル作業を上書きせずに、現在のリモート状態を確認します。

**行うこと：**

- タスクに関係するリポジトリだけを検出し、追跡対象のリモートをフェッチします。
- クリーンで、リモートより遅れているだけのブランチを fast-forward します。
- 未コミット変更、先行、分岐、detached、追跡先なし、進行中の操作の状態を報告します。
- プロジェクトポリシーが要求する場合、最初の編集前に、検証済みの現行 `main` から承認済みの機能ブランチを公開します。

**行わないこと：**

- 自動で stash、reset、rebase、merge、clean、switch、force-push を行うこと。
- 分岐を隠したり、フェッチの成功をローカルブランチの更新の証明とみなしたりすること。
- 無関係なリポジトリを走査または更新すること。

**呼び出し方法：**

```text
$synchronize-git-repositories Configure this project's repository synchronization policy.
```

#### `verify-before-push`

プロジェクトで宣言されたチェックを、プッシュ対象の正確な Git 状態に結び付けます。

**行うこと：**

- インストール済みスキルフォルダーの外に、リポジトリが管理する検証ポリシーを設定します。
- 宣言されたチェックを実行し、正確なコミット、ワークツリー、上流の状態、検証設定の証拠を記録します。
- 保護対象の証拠が欠落、失敗、不正、古い状態であれば、安全側に停止します。

**行わないこと：**

- ポリシーの対象外である無関係なリポジトリをブロックすること。
- 任意のシェルコマンドを解析したり、IDE やエージェント固有のフックをインストールしたりすること。
- 古い Git 状態で成功したチェックを、現行の証拠として扱うこと。

**呼び出し方法：**

```text
$verify-before-push Configure this project's verification policy and checks.
```

#### `coordinate-code-documentation-repositories` 実験的

実装と正規のドキュメントが別々の Git リポジトリにある場合に、監査可能な 1 つのプロジェクト変更を調整します。

**行うこと：**

- プロジェクトで宣言された実装リポジトリとドキュメントリポジトリの役割を確定します。
- 両方の開始コミットと正規のドキュメントソースに結び付けた、読み取り専用の計画を作成します。
- 要件、動作、検証、運用への影響、制限など、設定された項目のドキュメント証拠を要求します。
- 共同での完了を報告する前に、公開された両コミットの識別情報、検証証拠、リポジトリ間の追跡可能性を検証します。

**行わないこと：**

- ディレクトリ名やリポジトリ名から、リポジトリの役割を推測すること。
- 正規のドキュメントを日次ダイジェストで置き換えること。
- 自ら編集、コミット、プッシュ、マージを行ったり、未コミット変更や分岐のあるリポジトリを修復したりすること。
- 想定されたドキュメントファイルが存在するだけで、意味上の整合性があると主張すること。

**呼び出し方法：**

```text
$coordinate-code-documentation-repositories Implement this change across the declared code and canonical documentation repositories and verify both published outcomes.
```

#### `execute-configured-gitflow-releases` 実験的

プロジェクトで宣言された GitFlow 契約に基づいて、標準リリースとホットフィックスの経路を実行します。

**行うこと：**

- バージョン管理されたプロジェクト設定から、開発、本番、ホットフィックスの名前空間、リモート、ゲート、既定経路のポリシーを確定します。
- ソースコミットとリモートブランチの識別情報に結び付けた、読み取り専用の計画を凍結します。
- 標準経路とホットフィックス経路に、宣言された同じ共通ゲートを適用します。
- レビュー済みの本番公開、デプロイ証拠、必須となるホットフィックスの開発ラインへの再統合を検証します。

**行わないこと：**

- 慣例的なブランチ名を推測したり、ホットフィックスを既定経路にしたりすること。
- トランクベースの提供や、このコレクション固有のリリースチェーンをサポートすること。
- 保護された本番ブランチへの直接プッシュ、ゲートの迂回、履歴の書き換え、分岐の無断修復を行うこと。
- 再統合が検証される前に、本番ホットフィックスを完全な完了として扱うこと。

**呼び出し方法：**

```text
$execute-configured-gitflow-releases Run the standard release route declared by this project and verify the resulting production identity.
$execute-configured-gitflow-releases Run an explicit hotfix release and verify its reintegration into the declared development line.
```

#### `execute-verified-development-lifecycle` 実験的

機能の準備から、レビュー済みの開発統合、提供の観測、ドキュメント、安全性が証明されたクリーンアップまで、
プロジェクトが宣言する経路を計画し、検証します。

**行うこと：**

- 編集前にダイジェストに結び付けた計画を凍結し、保持した証拠を使って、順序付きのチェックポイントを進めます。
- 管理付き更新または初回使用時に、リポジトリルート、追跡中の上流、チェック、ドキュメントが観測可能であれば、
  保守的なプロジェクト設定を作成し、適用した既定値をすべて報告します。
- 編集前の機能ブランチ、テストファースト、変更範囲の事前確認、レビュー、正確な状態のプッシュ、
  パイプライン、ドキュメント、開発統合、委譲された本番処理、提供、スモークテスト、通知、クリーンアップのゲートを検証します。
- 失敗後は宣言済みのチェックポイントに戻り、古くなった後続の証拠を無効化します。

**行わないこと：**

- プロジェクトの証拠が曖昧な場合に、プロバイダー固有のアダプター、リポジトリの役割、提供ポリシー、承認を推測すること。
- 自らプッシュ、レビューの作成やマージ、デプロイ、通知、ドキュメント編集、リソース削除を行うこと。
- 本番への提供を実行すること。本番への提供は、引き続き `$execute-configured-gitflow-releases` などの
  承認済みリリースワークフローに委譲されます。

まず必須スキルである `$synchronize-git-repositories`、`$develop-with-test-first-evidence`、
`$verify-before-push`、`$review-code-changes` をインストールして設定します。
プロジェクト管理のバージョン 1 のライフサイクル契約がない場合、最初の計画前に、観測可能なプロジェクトの事実から初期化します。
プロジェクトがより具体的なポリシーを宣言している場合は、報告された既定値を確認して調整してください。
任意のスキルは、プロジェクトで対応するチェックポイントが有効な場合にのみインストールします。
該当スキルは `$orchestrate-agent-work`、`$diagnose-software-defects`、`$resolve-git-conflicts`、
`$coordinate-code-documentation-repositories`、`$maintain-work-log`、`$maintain-project-digest`、
`$notify-via-telegram`、`$execute-configured-gitflow-releases` です。

**呼び出し方法：**

```text
$execute-verified-development-lifecycle Plan and verify this change through the project's configured development lifecycle.
```


### プロジェクトの知識と継続性

#### `maintain-work-log`

`docs/reports/work-log.md` に、日付付きの正規のプロジェクト作業記録を維持します。

**行うこと：**

- 重要な変更、操作、診断、意思決定、検証、ブロッカー、ロールバック結果を記録します。
- プロジェクトの既存の記録形式を維持します。
- 利用可能な Git とプロジェクトタスクの証拠から、不足している履歴を再構成します。

**行わないこと：**

- プロジェクトポリシーやユーザーの要求がない通常作業で起動すること。
- 秘密情報、アプリケーションログ、時間追跡、個人メモを書き込むこと。
- 利用可能な証拠で裏付けられない出来事を主張すること。

**呼び出し方法：**

```text
$maintain-work-log Configure this project to maintain its dated work log.
```

#### `maintain-project-digest` 実験的

完了したプロジェクト変更の日次のユーザー向けダイジェストを、プロジェクトドキュメントに維持します。

**行うこと：**

- 完了した変更を今日の日付の下に、新機能、改善、修正、セキュリティ、ドキュメント、重要な動作変更として分類します。
- 技術的でない短い成果を記述し、空のカテゴリは省略します。
- 新しい日付を先頭に置き、過去の日付の内容はすべて変更せずに保持します。
- コンテンツに結び付けた計画、協調ロック、アトミックな置換、重複検出を使い、同じ日に複数の開発者が安全に貢献できるようにします。

**行わないこと：**

- プロジェクトがドキュメントの場所を一意に特定していない場合に、その場所を選んだり作成したりすること。
- 計画、失敗した実験、内部の実装作業、裏付けのないユーザーの利点を記録すること。
- 技術的な作業ログ、バージョンごとのリリースノート、通常の変更履歴を置き換えること。
- 通常の当日更新で、過去のダイジェスト期間を書き換えること。

**呼び出し方法：**

```text
$maintain-project-digest Add today's completed user-visible changes to the project digest.
```

#### `sync-project-context`

非公開で機密情報を除去したプロジェクトおよびチャットごとの継続状態を、コンピューター間で同期します。
このスキルは、実機での独立した Google Drive 実行が 2 回、決定的な昇格ゲートに合格した後、安定版となりました。

**行うこと：**

- 承認済みの同期フォルダーまたは接続済み Google Drive に不変のチェックポイントを保存し、
  マシン固有の設定はリポジトリ外に置きます。
- 指定のない同期要求では接続済み Google Drive を既定としつつ、既存のバックエンドを維持し、
  ローカル同期フォルダーを使う前に明示的なオプトインを要求します。
- 新しいコンピューターでは、リモートフォルダーを作成する前に、リポジトリのフィンガープリントから
  検証済みの既存 Google Drive マッピングを検出します。一覧が不完全、可視性が信頼できない、または一致が重複する場合はブロックします。
- プロジェクトタスクごとに不透明なストリームを 1 つ維持し、詳細なベースラインに続いて、
  短い差分、表示どおりの正確なタイトル、意思決定、検証、未解決の質問、次の手順、Git フィンガープリントを保持します。
- 最近のタスクと固定されたタスクのすべてを保存、復元、または双方向に計画し、
  変更のないタスクやアクティブなタスクはスキップして、競合を明示します。
- ダウンロードしたスナップショットを検証し、アップロードを再読み取りし、プロジェクトをまたぐ復元を防ぎ、
  高い確度で秘密情報と判断できるパターンを拒否します。
- Git がすでに提供していない、宣言済みのルール、スキル、プラグイン、安全なスカラー設定について、別の環境マニフェストを記録します。

**行わないこと：**

- ソースファイル、diff、生の会話記録、非公開の推論、認証情報、OAuth トークン、スキルやプラグインのインストールをコピーすること。
- Git がすでに運ぶルールや依存関係を重複して保持すること。
- Git が管理する移行先のルールを無断で上書きすること。適用では、明示的な計画の後、
  アクティブなエージェントに応じて選んだ、欠落している未追跡の `AGENTS.md` または `CLAUDE.md` の作成だけが可能です。
- メタデータのみのモードで、ブランチ名やファイルパスを含めること。表示されるタスクタイトルは意図的に含めます。

Codex Desktop は、文書化されたバッチタスク検出、作成、名前変更、Google Drive コネクターのワークフローに対応しています。
Claude Code は、移植可能なチェックポイント、ローカルフォルダー保存、環境調整のコアを使用できますが、
そのセッションストアは調査されず、Codex 専用のバッチタスク操作は未対応として安全側に停止します。

**呼び出し方法：**

各コンピューターで一度設定します。

```text
$sync-project-context Configure this clone in metadata-only mode. Use connected Google Drive by default unless I explicitly request another approved channel.
```

その後、たとえば次のような、タスク単位またはバッチのコマンドを使用します。

```text
$sync-project-context Save the current task state.
$sync-project-context Restore all project tasks on this computer.
$sync-project-context Synchronize all project tasks bidirectionally and show conflicts before applying changes.
```

Claude Code では、これらの例の `$` 接頭辞を `/` に置き換えます。


### 調整とコミュニケーション

#### `orchestrate-agent-work` 実験的

統合結果への責任を保持しながら、明示的に承認されたサブエージェントを調整します。

**行うこと：**

- 並行作業を、範囲が限定され、重複しない担当に分割します。
- 共有の制約に照らしてエージェントの結果を監視し、整合させます。
- 完了を報告する前に、統合結果を検証します。

**行わないこと：**

- ユーザーまたはプロジェクトの指示がサブエージェントを承認していない場合に委譲すること。
- 承認権限、秘密情報、破壊的なクリーンアップ、未承認の外部変更を別のエージェントに渡すこと。
- 個別に完了したサブタスクを、統合成功の証明として扱うこと。

**呼び出し方法：**

```text
$orchestrate-agent-work Delegate these independent subtasks to agents and verify the integrated result.
```

#### `synchronize-team-skills` 実験的

各チームメンバーのプロジェクトスコープのエージェントスキルを、プロジェクトドキュメント内の
レビュー済みの単一マニフェストに合わせて維持します。

**行うこと：**

- 承認済みのドキュメントルートで `team-agent-skills.md` を作成または読み取ります。
- 宣言された Codex および Claude Code のスキルを、検証済みのプロジェクト内コピーと比較します。
- 環境を変更せずに、欠落、古い、新しい、未検証、プロジェクト上書き、保持された追加分の状態を報告します。
- 固定された 1 つのコレクションバージョンについて、マニフェストのダイジェストに結び付けたインストール計画を構築します。
- 承認後、レビュー済みのセットだけをインストールし、観測可能な状態を検証します。

**行わないこと：**

- あるワークステーションの偶発的な状態を、自動でチームポリシーにすること。
- 秘密情報、ユーザー設定、マシンのパス、プラグイン認証を保存すること。
- 追加のスキルを削除したり、新しいコピーをダウングレードしたり、グローバルインストールを変更したりすること。
- 実行中のエージェントタスクが、新しくインストールしたスキルを再読み込みしたと主張すること。

**呼び出し方法：**

```text
$synchronize-team-skills Check this project's installed skills against the reviewed team manifest.
$synchronize-team-skills Align my project skills with the team documentation after showing the plan.
$synchronize-team-skills Add maintain-project-digest to the reviewed team skill set.
```

#### `notify-via-telegram`

長時間実行するエージェントタスクのライフサイクル更新を、Telegram 経由で送信します。

**行うこと：**

- 開始、マイルストーン、中間結果、問題、ブロッカー、完了を報告します。
- 対話形式でボットを検証し、通知先チャットの検出を支援します。
- Windows の Codex Desktop 向けに、マスク表示で貼り付けやすい初回用フォームを提供します。
- 認証情報をユーザー設定ディレクトリに保存し、設定時にテスト通知を送信します。
- プロジェクトごとの個別チャットやフォーラムトピックに対応し、グローバルとプロジェクトの両方への送信か、
  プロジェクトのみに送信するかを明示的に選択できます。
- `sync-project-context` による調整用に、秘密情報を含まないプロジェクトのルーティング値をエクスポートします。
- Windows、macOS、Linux 上で Python 3 の標準ライブラリを使って動作します。

**行わないこと：**

- ボットトークンを会話、シェル履歴、リポジトリに含めること。
- グローバルのボットトークンや Telegram の認証状態をコンピューター間でコピーすること。
- ユーザーが進捗を現在のタスク内にとどめるよう求めた場合に、通知を送ること。
- 汎用的な Telegram ボット開発フレームワークとして機能すること。

**呼び出し方法：**

```text
$notify-via-telegram Configure Telegram notifications for long tasks.
$notify-via-telegram Configure this project to notify its team chat only, instead of the global destination.
```


### インフラストラクチャと運用

#### `operate-yandex-cloud`

明示的に設定された、プロジェクトスコープの Yandex Cloud インフラストラクチャを運用します。

**行うこと：**

- 共有の Cloud/Folder ID をプロジェクト設定に保存し、ワークステーションの `yc` プロファイルを
  Git の追跡対象外にしたローカル設定に保存します。
- 必要なツールセットを検出し、最小バージョンを確認して、読み取り専用のコンテキスト事前チェックを実行します。
- 対象を限定した CLI、SSH、Terraform、Ansible、Helm、Kubernetes、デプロイ、データベース、ストレージ、
  DNS、監視、バックアップ、インシデントのワークフローに対応します。
- JSON 出力とクロスプラットフォームの Python ヘルパーを提供します。

**行わないこと：**

- プロバイダーのコンテキストがない一般的な SSH、Kubernetes、Terraform、デプロイの要求から、Yandex Cloud を推測すること。
- 共有のプロジェクト設定に認証情報を保存すること。
- 対象、コンテキスト、承認が確定する前に変更を適用すること。

**呼び出し方法：**

```text
$operate-yandex-cloud Configure this project for Yandex Cloud operations.
```


### スキルコレクションの発展

#### `discover-skill-candidates` 実験的

範囲を限定したプロジェクトとコンテキストの証拠から、スキルを作成することなく、再利用可能なスキルの案を見つけます。

**行うこと：**

- 範囲を限定したプロジェクト相対の `AGENTS.md` ファイルを、Git と行単位の来歴とともに一覧化します。
- 必要に応じて、プロジェクトドキュメント、選択したファイル、範囲を限定した Git 履歴、構造メタデータ、
  利用可能なチャットまたは `sync-project-context` の引き継ぎからユーザーが確認した要約を一覧化します。
- 候補を推奨、要調査、却下に順位付けし、既存のカタログと比較します。
- 適格なすべての候補について、`kolabse/skills` への安全な貢献、ローカルでの作成、保留を積極的に提案します。
- 選択した案を、メンテナーが独立して検証できる、機密情報を除去しダイジェストに結び付けた貢献パッケージとしてエクスポートします。

**行わないこと：**

- プロジェクトルールの変更や、スキルの雛形作成、公開、インストールを行うこと。
- チャットの列挙、生の会話記録の取り込み、ソースコードの広範な走査を行うこと。
- 生のルール、ローカルパス、秘密情報、URL、メールアドレスをエクスポートすること。
- ポリシーだけの規約、変動しやすい規約、機密性のある規約、一度限りの規約を、レビューなしに再利用可能なワークフローとして推進すること。

**呼び出し方法：**

```text
$discover-skill-candidates Analyze this project's local rules and prepare an evidence-backed backlog of reusable skill ideas without creating anything.
```

#### `release-skill-collection`

決定的に再現可能なスキルコレクションのリリースを計画、検証、監査し、クリーンアップします。

**行うこと：**

- バージョン、変更履歴の準備状況、リポジトリ状態、テスト、セキュリティ、決定的なアーカイブ、チェックサムを確認します。
- コミットに結び付けたホールドアウト、インストール先エージェント、プラットフォーム、レビュー、ローカルチェックの証拠を検証します。
- 不変の GitHub アセット、マニフェスト、チェックサム、アテステーションを監査します。
- クリーンアップ前に、一時ブランチがマージ済み、同一ツリー、またはパッチ等価であるかを証明します。
- 変更されていない安全な計画と、公開済みリリースのダイジェストが有効な監査に基づく場合にのみ、明示的に確認されたクリーンアップを適用します。

**行わないこと：**

- コミット、タグ付け、プッシュ、ワークフロー起動、アセット公開の許可を推測すること。
- 既存のタグを移動したり、公開済みアセットを置き換えたりすること。
- 名前だけ、古い計画、未監査のリリースに基づいてブランチを削除すること。

**呼び出し方法：**

```text
$release-skill-collection Plan and verify release vX.Y.Z of this skill collection, but do not publish it yet.
```

## 対応するスキル構成

カタログは、再利用可能で順序付きのワークフローを 3 つ定義しています。

- `protected-push`：リポジトリを同期してから、現行の検証証拠を生成します。
  作業ログと Telegram 通知は任意です。
- `yandex-cloud-operation`：リポジトリを同期してから、対象を限定したクラウド操作を実行します。
  検証、作業ログ、Telegram 通知は、プロジェクトポリシーで有効にした場合の任意の手順です。
- `skill-collection-release`：リポジトリを同期し、コレクションリリースを計画してローカルで検証し、
  プッシュ前の証拠を結び付けます。作業ログと Telegram 通知は任意です。

必須ステップは安全側に停止します。任意のログ記録と通知は、主要操作の観測結果を変えることなく、
自身の失敗を報告します。`scripts/compose_skills.py` で正確な計画を確定します。
`schemas/composition-evidence.schema.json` に適合するダイジェストに結び付けた文書を `--evidence` で渡し、
ステップ順序、必須の結果、処理を妨げない任意ステップの失敗を検証します。
検証された結果は `schemas/composition-result.schema.json` に従います。

## スキルを追加する

[CONTRIBUTING.md](CONTRIBUTING.md) に従い、
[`templates/skill-template.md`](../../../templates/skill-template.md) から始めます。
すべてのスキルには、所有者、プラットフォーム、ステータス、ライセンス、来歴を記録する、
対応した `skill-catalog.json` エントリが必要です。更新で上書きされないように、
プロジェクト固有の設定はインストール済みスキルフォルダーの外に保持します。

個別のスキル用にリポジトリレベルのインストーラーを追加しないでください。
コレクションに ChatGPT と Codex を横断する管理付きインストールや更新が必要な場合は、
このエージェント横断の配置に加えて、コレクションを OpenAI プラグインとしてパッケージ化します。

コレクションのチェックをローカルで実行します。

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py
```

エージェントまたはモデルセレクター用のブラインドトリガースイートを準備します。

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
```

このスイートに含まれるのは、スキル名、公開説明、不透明なケース ID、プロンプトだけです。
期待ラベルや作成者の理由は含みません。セレクターは、ケースごとに選択したすべてのスキルを列挙した
厳密な JSON を返します。次のコマンドで観測結果を採点します。

```shell
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

`run` と、`--` の後に指定するコマンドを使い、標準入力からスイートを読み、標準出力に予測を書き出す
セレクターを呼び出します。プロバイダーの認証情報はコマンド引数に含めないでください。
無視対象の `.trigger-evals/` ディレクトリにより、生成されたスイート、予測、レポートは既定でコミットに含まれません。
大規模な開発スイートは、長い厳密 JSON 応答で不透明なケース ID が切り詰められないよう、
既定で 64 ケースずつのダイジェストに結び付けたバッチで送信します。
期待ラベルをセレクターに見せずに、`--batch-size` で上限を調整できます。

リリース前には、独立してバージョン管理されダイジェストで固定されたホールドアウトを実行します。
開発中の説明調整には使用しないでください。

```shell
python scripts/trigger_evals.py prepare \
  --corpus release-holdout \
  --output .trigger-evals/release-holdout.json
```

候補レポートを、同じホールドアウトバージョンから生成したレポートと比較します。

```shell
python scripts/trigger_evals.py compare \
  --candidate .trigger-evals/candidate-report.json \
  --markdown-output .trigger-evals/comparison.md
```

アサーションのダイジェストが異なる場合、または全体の正解率、適合率、再現率、スキル別の指標が
設定された限度を超えて低下した場合、比較は安全側に停止します。
既定では `skill-catalog.json` に指定された公開ベースラインを使用します。
別の互換性のあるレポートと意図的に比較する場合にのみ、`--baseline` を指定します。

非決定的なモデルセレクターでは、3 回以上の奇数回のブラインド予測実行を収集し、多数決の結果を採点します。

```shell
python scripts/trigger_evals.py aggregate \
  --corpus release-holdout \
  --predictions run-1.json run-2.json run-3.json \
  --predictions-output .trigger-evals/aggregate.json \
  --json-output .trigger-evals/candidate-report.json
```

## リリースを検証する

バージョン付きリリースには、決定的に再現可能な ZIP と TAR.GZ アーカイブ、`release-manifest.json`、
`SHA256SUMS` が含まれます。4 つのアセットをすべて同じディレクトリにダウンロードし、次で検証します。

```shell
python scripts/build_release.py --verify <download-directory>/SHA256SUMS
```

GitHub は、アップロードされた各リリースアセットについて、SHA-256 の `digest` も公開しています。
リリースワークフローは、さらに GitHub アーティファクトアテステーションを公開します。
ダウンロードした成果物をこのリポジトリに対して検証します。

```shell
gh attestation verify <artifact> --repo kolabse/skills
```
