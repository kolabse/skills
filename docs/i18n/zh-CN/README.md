# kolabse/skills

[English](../../../README.md) | [Русский](../ru/README.md) | [Español](../es/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Português (Brasil)](../pt-BR/README.md) | [日本語](../ja/README.md) | [Italiano](../it/README.md) | [한국어](../ko/README.md) | 简体中文 | [Türkçe](../tr/README.md)

本文为简体中文译文。如有差异，以[英文原文](../../../README.md)为准。

由 kolabse 维护的可复用代理技能。

依据 [Apache License 2.0](../../../LICENSE) 许可。版权所有 2026 kolabse。

## 目录

- [安装技能](#安装技能)
  - [从 Git 市场安装](#从-git-市场安装)
- [更新已安装的技能](#更新已安装的技能)
  - [无需克隆仓库即可运行](#无需克隆仓库即可运行)
  - [检查全局安装](#检查全局安装)
- [安装或更新本地开发用 Codex 插件](#安装或更新本地开发用-codex-插件)
- [可用技能](#可用技能)
  - [开发与代码质量](#开发与代码质量)
    - [`develop-with-test-first-evidence`](#develop-with-test-first-evidence-实验性)
    - [`review-code-changes`](#review-code-changes-实验性)
    - [`diagnose-software-defects`](#diagnose-software-defects-实验性)
    - [`resolve-git-conflicts`](#resolve-git-conflicts-实验性)
  - [仓库与变更交付](#仓库与变更交付)
    - [`synchronize-git-repositories`](#synchronize-git-repositories)
    - [`verify-before-push`](#verify-before-push)
    - [`coordinate-code-documentation-repositories`](#coordinate-code-documentation-repositories-实验性)
    - [`execute-configured-gitflow-releases`](#execute-configured-gitflow-releases-实验性)
    - [`execute-verified-development-lifecycle`](#execute-verified-development-lifecycle-实验性)
  - [项目知识与连续性](#项目知识与连续性)
    - [`maintain-work-log`](#maintain-work-log)
    - [`maintain-project-digest`](#maintain-project-digest-实验性)
    - [`sync-project-context`](#sync-project-context)
  - [协调与沟通](#协调与沟通)
    - [`orchestrate-agent-work`](#orchestrate-agent-work-实验性)
    - [`synchronize-team-skills`](#synchronize-team-skills-实验性)
    - [`notify-via-telegram`](#notify-via-telegram)
  - [基础设施与运维](#基础设施与运维)
    - [`operate-yandex-cloud`](#operate-yandex-cloud)
  - [技能集合演进](#技能集合演进)
    - [`discover-skill-candidates`](#discover-skill-candidates-实验性)
    - [`release-skill-collection`](#release-skill-collection)
- [支持的组合](#支持的组合)
- [添加技能](#添加技能)
- [验证发布](#验证发布)

## 安装技能

使用跨代理的 [`skills`](https://skills.sh) CLI，将一个或多个技能安装到当前项目：

```shell
npx skills@latest add kolabse/skills
```

该 CLI 会发现 `skills/` 下的文件夹，让你选择要安装的技能，并将其复制到所选编码代理中。
它是外部安装程序；本仓库不发布或执行自己的 npm 包。

Codex 用户也可以请求 `$skill-installer` 从本仓库安装技能，例如从以下地址安装：

```text
https://github.com/kolabse/skills/tree/main/skills/operate-yandex-cloud
```

非交互式安装时，请明确选择使用方：

```shell
npx skills@1.5.22 add kolabse/skills --agent codex --copy -y
npx skills@1.5.22 add kolabse/skills --agent claude-code --copy -y
```

在项目中安装时，可向代理提出：“安装所选技能并初始化缺失的项目默认值，不要替换我们已有的规则。”
外部安装程序完成后，为你的代理引导初始化 Git 规则：

```shell
python .agents/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent codex --apply --yes --json
python .claude/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent claude-code --apply --yes --json
```

缺失的约定默认使用 `feature/`、`bugfix/`、`release/`、`hotfix/` 和提交类型 `feat`、`fix`、`refactor`、`docs`、`test`、`chore`。
项目明确指定的前缀、分支角色和提交格式仍具有权威性。不会创建持久分支或 Git 钩子。
项目范围的受管理更新会为相关技能应用同样的引导初始化；尚未确认的更新只会生成计划。

项目范围的安装中，当可观察的默认值足够时，应立即初始化生命周期约定（使用对应代理的路径）：

```shell
python .agents/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent codex --apply --yes --json
python .claude/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent claude-code --apply --yes --json
```

市场/插件安装是全局的，没有活动的项目根目录，因此技能会在首次用于项目时执行同样的引导初始化。

Codex 在 `.agents/skills/` 下发现项目技能，并以 `$skill-name` 调用。
Claude Code 在 `.claude/skills/` 下发现技能，并以 `/skill-name` 调用。
技能指令和随附脚本是共享的；使用方专用的规则文件和调用语法在设置时选择。

本仓库还打包为面向 ChatGPT/Codex 和 Claude Code、仅包含技能的 `kolabse-skills` 插件。
`skills/` 下的每个文件夹都包含在内。跨代理的 `npx skills` 安装独立于两种插件格式，仍可使用。

### 从 Git 市场安装

Codex 用户可以注册仓库市场并安装完整集合：

```shell
codex plugin marketplace add kolabse/skills --ref main
codex plugin add kolabse-skills@kolabse
```

刷新 Git 快照并重新安装当前插件版本：

```shell
codex plugin marketplace upgrade kolabse
codex plugin add kolabse-skills@kolabse
```

Claude Code 用户可以注册同一仓库并安装插件：

```shell
claude plugin marketplace add kolabse/skills
claude plugin install kolabse-skills@kolabse
```

使用 `claude plugin marketplace update kolabse` 显式刷新，或在 Claude Code 中启用市场自动更新。
安装或更新后，请启动新的代理会话，使其发现当前技能集。

市场目录为 [`.agents/plugins/marketplace.json`](../../../.agents/plugins/marketplace.json) 和
[`.claude-plugin/marketplace.json`](../../../.claude-plugin/marketplace.json)。
其插件内容由 [`.codex-plugin/plugin.json`](../../../.codex-plugin/plugin.json) 和
[`.claude-plugin/plugin.json`](../../../.claude-plugin/plugin.json) 描述。
两个目录都从 `main` 获取权威的 `kolabse/skills` 仓库；发布版本仍以插件清单为准。

公开上架材料与源码一同维护：[支持](SUPPORT.md)、[隐私政策](PRIVACY.md)、[使用条款](TERMS.md) 和可重现的[市场提交资料包](../../../docs/marketplace-submissions/)。
发布到官方目录仍是需要审查的维护者操作；从 Git 市场安装不需要目录批准。

测试时，Claude Code 可使用 `claude --plugin-dir <collection-root>` 直接加载解压后的发布版本或可信的检出目录。
普通个人或项目使用，应优先选择 Git 市场或上面显式指定的 `npx skills ... --agent claude-code` 命令。
Claude Code 读取 `CLAUDE.md`，而非 `AGENTS.md`；如果项目已有共享的 `AGENTS.md` 规则，只需一个包含 `@AGENTS.md` 的最小 `CLAUDE.md`，即可保留唯一的权威规则文档。

## 更新已安装的技能

`skills` CLI 在 `skills-lock.json` 中记录 GitHub 来源和内容哈希。根据记录的来源更新所有项目安装：

```shell
npx skills@1.5.22 update -p -y
```

更新单个技能或全局安装：

```shell
npx skills@1.5.22 update verify-before-push -p -y
npx skills@1.5.22 update -g -y
```

未限定版本的 `kolabse/skills` 锁记录跟随仓库默认分支；它不会固定集合的发布版本。
不要编辑 `.agents/skills/` 下复制的文件，因为更新可能会替换它们。项目和用户配置保留在已安装技能文件夹之外。

从克隆的检出目录或发布归档中，通过一次显式操作更新并迁移受支持的项目配置：

```shell
python scripts/manage_installed_skills.py update --project-path . --yes --migrate
python scripts/manage_installed_skills.py doctor --project-path . --json
```

预览确切的选择，不调用外部安装程序，也不更改配置：

```shell
python scripts/manage_installed_skills.py plan --project-path . --json
```

计划报告来源身份、当前和目标版本、来源信息、迁移候选项，以及 `update`、`unchanged`、`adopt-and-update` 或 `blocked` 操作。
其模式为 `schemas/manager-plan.schema.json`。为 `update` 添加 `--json`；更新和迁移结果遵循 `schemas/manager-result.schema.json`。

未指定名称时，管理器从项目锁文件解析已安装的 kolabse 技能，并将这些名称显式传给外部 CLI；无关的项目技能绝不纳入更新。
全局更新要求显式指定集合技能名称。项目更新最后会执行与 `doctor` 相同的严格诊断，无法验证时拒绝继续。
当项目更新包含 `execute-verified-development-lifecycle` 时，如果项目事实足够，管理器还会引导初始化其缺失配置，并返回 `created`、`configured` 或 `blocked` 配置结果。

只有在也应迁移 Telegram 用户配置时，才添加 `--include-user-config`。
`status` 和 `doctor` 为只读。`migrate` 仅更改已存在的配置文件；不会配置未使用的技能。
每个已安装技能都携带 `collection-metadata.json`，因此即使外部锁格式没有版本字段，`status` 仍能报告其集合版本。
它还报告 `provenance_status`：`verified` 同时要求集合元数据和权威 GitHub 来源或经过内容验证的本地锁来源；
`legacy-unverified` 表示引入元数据前的安装；`mismatch` 绝不会更新。
检出目录可以更名，因为本地身份来自插件清单、目录和技能内容，而非目录名称。

只有在审查所报告的来源后，才接纳 v1.2 之前没有元数据的安装：

```shell
python scripts/manage_installed_skills.py status --project-path . --json
python scripts/manage_installed_skills.py update --project-path . --yes --adopt-legacy
```

接纳标志不会使任意文件都获得认可：来源必须已可规范化为 `kolabse/skills` 或通过本地检出验证，且常规更新后诊断必须验证已安装的元数据。
外部 CLI 不会原地更新 `sourceType: local` 开发锁。管理器会将该 CLI 无操作视为失败；
请使用原先的 `--skill` 和 `--agent` 选择，从本地来源重新添加这些技能。

### 无需克隆仓库即可运行

从可信发布版本或本仓库下载 `scripts/bootstrap_update.py`，让它解析最新稳定版，依据 `SHA256SUMS` 和 GitHub 构建来源验证发布 ZIP，并在隔离的临时解压目录中运行管理器：

```shell
python bootstrap_update.py doctor --json
python bootstrap_update.py plan --json
python bootstrap_update.py update --yes --migrate --json
```

使用 `--release v1.15.0` 固定版本。引导程序需要 `gh` 来验证认证，并在完成后删除其临时目录。
使用离线缓存时，同时提供 `--offline-archive` 和 `--offline-checksums`。
当 `gh` 可以访问 GitHub 时，仍必须验证来源。
`--allow-unattested-offline` 是显式降级模式：它仅验证缓存校验和，只应用于通过独立可信渠道传递的产物。
回滚时选择较旧的发布版本并遵循现有回滚流程；配置迁移仍然只能向前进行。

### 检查全局安装

支持的全局状态有意限制为共享的 `~/.agents/.skill-lock.json` v3 锁文件。
Codex 的已安装内容位于 `~/.agents/skills`，Claude Code 的位于 `~/.claude/skills`。
管理器不会扫描其他用户目录。默认仍为 Codex；使用 `--agent claude-code` 指定 Claude 内容布局：

```shell
python scripts/manage_installed_skills.py status --scope global --json
python scripts/manage_installed_skills.py doctor --scope global --json
python scripts/manage_installed_skills.py plan verify-before-push --scope global --json
python scripts/manage_installed_skills.py update verify-before-push --scope global --yes --json
python scripts/manage_installed_skills.py status --scope global --agent claude-code --json
```

使用 `--global-root` 只读检查测试布局或明确迁移位置后的兼容布局。
迁移位置后的根目录无法更新，因为外部 CLI 无法将其作为目标。未知的锁格式会被报告，不会发生修改。

若要回滚技能文件，先备份项目/用户配置，再以原始安装相同的技能和代理目标重新安装所需发布标签，例如：

```shell
npx skills@1.5.22 add kolabse/skills@v1.1.0 --skill verify-before-push --agent codex --copy -y
```

除非某个发布版本明确记录支持降级，否则配置迁移只能向前进行。
恢复较旧的技能文件不会降级配置；当旧版无法读取新版格式时，请恢复相匹配的配置备份。

## 安装或更新本地开发用 Codex 插件

本地插件开发时，创建/更新默认个人市场条目，将插件复制到本地插件目录，为 Codex 添加缓存失效标记并激活：

```shell
python scripts/install_personal_plugin.py --activate
```

安装程序保留其他个人市场条目，且不编辑仓库清单。这是替代性的开发路径，不是常规的 Git 市场安装。
更新检出目录后再次运行，再启动新的 Codex 任务以加载更新后的技能。
使用 `--json` 记录已安装版本、插件路径、市场路径和市场名称。

## 可用技能

稳定技能和实验性新增技能在 `skill-catalog.json` 中标明。
其面向项目的配置路径、安全边界和已记录的命令接口遵循 [CONTRIBUTING.md](CONTRIBUTING.md) 中的兼容性政策。

每个目录条目现在都声明配置范围、只读 JSON 状态命令、能力、前提条件和可选集成。
有状态技能还声明幂等配置命令；带版本的 JSON/YAML 配置在技能旁发布 JSON Schema 和迁移命令。

目录按面向用户的主要用途分组，优先顺序如下。每个技能恰好有一个主要类别。
正交标签描述生命周期阶段、范围、行为和集成；成熟度状态保持独立。
权威的机器可读分类和受控词汇位于 [`skill-catalog.json`](../../../skill-catalog.json)，并依据
[`schemas/skill-catalog.schema.json`](../../../schemas/skill-catalog.schema.json) 验证。

受控标签维度为：

- 生命周期阶段：`prepare`、`investigate`、`implement`、`verify`、`publish`、`operate`、`document` 和 `handoff`；
- 范围：`project`、`repository`、`multi-repository`、`workstation`、`external-service` 和 `skill-collection`；
- 行为：`read-only-planning`、`mutation`、`evidence-producing`、`orchestration` 和 `notification`；
- 集成：`git`、`github`、`telegram`、`google-drive` 和 `yandex-cloud`。

### 开发与代码质量

#### `develop-with-test-first-evidence` （实验性）

通过有证据支持的红—绿—重构循环实现行为。

**功能：**

- 在实现之前，记录针对性测试因预期的行为原因而失败的结果；
- 将针对性测试和更广泛测试的通过结果绑定到最终变更状态；
- 使用随附模式和辅助程序验证可长期保留的证据。

**不会执行：**

- 通过破坏无关行为制造失败结果；
- 将事后测试称为测试先行开发；
- 隐瞒既有失败、环境失败或最终状态中的失败。

**调用方式：**

```text
$develop-with-test-first-evidence Implement this behavior with a recorded red-green-refactor cycle.
```

#### `review-code-changes` （实验性）

审查指定变更，寻找可采取行动的正确性、安全性、可靠性和兼容性缺陷。

**功能：**

- 确定确切基线和变更状态；
- 报告有证据支持的问题，包括影响、触发条件、优先级和精确位置；
- 明确不确定性和有实际意义的测试缺口。

**不会执行：**

- 将风格偏好或缺乏依据的推测报告为缺陷；
- 未经单独授权就实现修复、发布评论或批准审查；
- 用一般代码说明代替限定范围的审查。

**调用方式：**

```text
$review-code-changes Review this branch against its declared baseline and report actionable findings.
```

#### `diagnose-software-defects` （实验性）

调查故障和回归，给出有依据的因果解释或排序后的假设。

**功能：**

- 界定症状范围，并在可行时安全复现；
- 用相关证据检验相互竞争的假设；
- 报告根因、促成条件、影响范围、置信度和修复验证计划。

**不会执行：**

- 从相关性推断因果关系；
- 修改生产环境或丢弃失败证据；
- 在仅被要求诊断时实施推测性的修复。

**调用方式：**

```text
$diagnose-software-defects Diagnose this regression and distinguish evidence from hypotheses.
```

#### `resolve-git-conflicts` （实验性）

在保留无关工作的同时，从语义层面解决已获授权的合并、变基或拣选冲突。

**功能：**

- 检查当前操作、基线、双方内容和每个未合并路径；
- 仅协调那些预期合并行为已被理解的冲突；
- 验证已解决的路径，并明确剩余的 Git 操作步骤。

**不会执行：**

- 将普通仓库分歧视为文件冲突任务；
- 自动暂存工作、重置、中止、继续、强制推送或将无关路径加入暂存区；
- 对有歧义的生成文件、二进制文件、模式或产品决策进行猜测。

**调用方式：**

```text
$resolve-git-conflicts Resolve the active merge conflicts path by path and validate the result.
```

### 仓库与变更交付

#### `synchronize-git-repositories`

在不覆盖本地工作的情况下，确认最新远端状态。

**功能：**

- 仅发现与任务相关的仓库，并获取其跟踪远端；
- 对干净且仅落后的分支执行快进；
- 报告工作区不干净、领先、分歧、游离、未跟踪和操作进行中的状态；
- 当项目政策要求时，在首次编辑之前，从经过验证的当前 `main` 发布已获授权的功能分支。

**不会执行：**

- 自动暂存工作、重置、变基、合并、清理、切换或强制推送；
- 隐瞒分歧，或将获取成功视为本地分支已更新的证明；
- 扫描或更新无关仓库。

**调用方式：**

```text
$synchronize-git-repositories Configure this project's repository synchronization policy.
```

#### `verify-before-push`

将项目声明的检查绑定到待推送的确切 Git 状态。

**功能：**

- 在已安装技能文件夹之外配置仓库拥有的验证政策；
- 运行声明的检查，并为确切提交、工作树、上游状态和验证配置记录证据；
- 当受保护的证据缺失、失败、格式错误或过时时，拒绝继续。

**不会执行：**

- 阻塞政策未涵盖的无关仓库；
- 解析任意 shell 命令或安装 IDE/代理专用钩子；
- 将较旧 Git 状态下通过的检查视为当前证据。

**调用方式：**

```text
$verify-before-push Configure this project's verification policy and checks.
```

#### `coordinate-code-documentation-repositories` （实验性）

当实现与权威文档位于不同 Git 仓库时，协调一项可审计的项目变更。

**功能：**

- 解析项目声明的实现仓库和文档仓库角色；
- 创建绑定双方起始提交及权威文档来源的只读计划；
- 要求为已配置主题提供文档证据，例如需求、行为、验证、运维影响和限制；
- 在报告共同完成之前，验证双方已发布的提交身份、验证证据和跨仓库可追溯性。

**不会执行：**

- 根据目录或仓库名称推断仓库角色；
- 用每日摘要替代权威文档；
- 自行编辑、提交、推送、合并，或修复不干净和有分歧的仓库；
- 仅因预期文档文件存在就声称语义一致。

**调用方式：**

```text
$coordinate-code-documentation-repositories Implement this change across the declared code and canonical documentation repositories and verify both published outcomes.
```

#### `execute-configured-gitflow-releases` （实验性）

依据项目声明的 GitFlow 约定执行标准发布和热修复发布路径。

**功能：**

- 从带版本的项目配置解析开发、生产、热修复命名空间、远端、门禁和默认路径政策；
- 冻结绑定源提交及远端分支身份的只读计划；
- 对标准路径和热修复路径应用相同的已声明通用门禁；
- 验证经过审查的生产发布、部署证据，以及热修复强制回集成至开发线的结果。

**不会执行：**

- 推断惯例分支名称，或将热修复作为默认路径；
- 支持主干式交付或本集合专用的发布链；
- 直接推送到受保护的生产分支、绕过门禁、重写历史或静默修复分歧；
- 在验证回集成之前，将生产热修复视为完全完成。

**调用方式：**

```text
$execute-configured-gitflow-releases Run the standard release route declared by this project and verify the resulting production identity.
$execute-configured-gitflow-releases Run an explicit hotfix release and verify its reintegration into the declared development line.
```

#### `execute-verified-development-lifecycle` （实验性）

规划并验证项目声明的路径，涵盖功能准备、经过审查的开发集成、交付观测、文档和有证明的清理。

**功能：**

- 在编辑前冻结绑定摘要的计划，并使用保留的证据推进有序检查点；
- 在受管理更新或首次使用时，当仓库根目录、跟踪上游、检查和文档均可观察时，创建保守的项目配置，并报告应用的每个默认值；
- 验证编辑前功能分支、测试先行、变更范围预检、审查、确切状态推送、流水线、文档、开发集成、委托生产发布、交付、冒烟测试、通知和清理门禁；
- 失败后退回已声明的检查点，并使过时的下游证据失效。

**不会执行：**

- 在项目证据有歧义时，猜测提供商专用适配器、仓库角色、交付政策或授权；
- 自行推送、创建或合并审查、部署、通知、编辑文档或删除资源；
- 执行生产交付，该操作仍委托给已批准的发布工作流，例如 `$execute-configured-gitflow-releases`。

请先安装并配置所需技能：`$synchronize-git-repositories`、`$develop-with-test-first-evidence`、`$verify-before-push` 和 `$review-code-changes`。
在首次计划之前，将根据可观察的项目事实引导初始化缺失的、项目拥有的版本 1 生命周期约定；
当项目声明了更具体的政策时，请审查并细化它报告的默认值。
仅在项目启用相应检查点时安装可选技能：`$orchestrate-agent-work`、`$diagnose-software-defects`、`$resolve-git-conflicts`、
`$coordinate-code-documentation-repositories`、`$maintain-work-log`、`$maintain-project-digest`、`$notify-via-telegram` 和 `$execute-configured-gitflow-releases`。

**调用方式：**

```text
$execute-verified-development-lifecycle Plan and verify this change through the project's configured development lifecycle.
```

### 项目知识与连续性

#### `maintain-work-log`

在 `docs/reports/work-log.md` 维护带日期的权威项目日志。

**功能：**

- 记录重大变更、操作、诊断、决策、验证、阻塞项和回滚结果；
- 保留项目现有的日志格式；
- 根据可用 Git 和项目任务证据重建缺失历史。

**不会执行：**

- 在项目政策或用户未要求时，为普通工作启用；
- 写入秘密信息、应用日志、工时记录或个人笔记；
- 声称发生了无法由现有证据支持的事件。

**调用方式：**

```text
$maintain-work-log Configure this project to maintain its dated work log.
```

#### `maintain-project-digest` （实验性）

在项目文档中维护面向用户的每日已完成项目变更摘要。

**功能：**

- 将已完成变更按新能力、改进、修复、安全、文档或重要行为变化，分组记录在当天日期下；
- 编写简短的非技术性结果说明，省略空类别；
- 将最新日期放在最前，并保持所有更早日期不变；
- 使用绑定内容的计划、协作锁、原子替换和重复检测，使多名开发者能在同一天安全贡献。

**不会执行：**

- 在项目未明确指定时选择或创建文档位置；
- 记录计划、失败实验、内部实现活动或无证据支持的用户收益；
- 替代技术工作日志、版本发布说明或常规变更日志；
- 在普通同日更新中重写历史摘要期间的内容。

**调用方式：**

```text
$maintain-project-digest Add today's completed user-visible changes to the project digest.
```

#### `sync-project-context`

在计算机之间同步私有、已脱敏的项目状态和每个对话的续接状态。
两次独立的真实设备 Google Drive 运行通过确定性晋级门禁后，该技能已达到稳定状态。

**功能：**

- 在已批准的同步文件夹或已连接的 Google Drive 中保存不可变检查点，将机器本地配置保留在仓库之外；
- 对未限定方式的同步请求默认使用已连接的 Google Drive，同时保留现有后端，并在使用本地同步文件夹前要求显式选择加入；
- 在新计算机上创建任何远端文件夹之前，根据仓库指纹发现经过验证的已有 Google Drive 映射，并在列表不完整、可见性不可信或存在重复匹配时阻塞；
- 为每个项目任务保留一个不透明流：详细基线，随后是简短增量、确切可见标题、决策、验证、开放问题、后续步骤和 Git 指纹；
- 保存、恢复所有最近和置顶的项目任务，或为其规划双向同步，同时跳过未更改/活动任务并明确呈现冲突；
- 验证下载的快照，回读上传内容，防止跨项目恢复，并拒绝匹配高置信度秘密信息模式的内容；
- 为 Git 尚未提供的已声明规则、技能、插件和安全标量设置记录单独的环境清单。

**不会执行：**

- 复制源文件、差异、原始对话记录、隐藏推理、凭据、OAuth 令牌或技能/插件安装；
- 重复 Git 已携带的规则或依赖；
- 静默覆盖 Git 管理的目标规则：只有制定显式计划后，应用操作才能为活动代理创建所选的、缺失且未跟踪的 `AGENTS.md` 或 `CLAUDE.md`；
- 在仅元数据模式下包含分支名称或文件路径；可见任务标题则有意保留。

Codex Desktop 支持文档所述的批量任务发现、创建、更名和 Google Drive 连接器工作流。
Claude Code 可以使用可移植的检查点、本地文件夹存储和环境协调核心，但不会检查其会话存储；Codex 专用的批量任务操作会以不受支持为由拒绝执行。

**调用方式：**

每台计算机配置一次：

```text
$sync-project-context Configure this clone in metadata-only mode. Use connected Google Drive by default unless I explicitly request another approved channel.
```

随后使用任务级或批量命令，例如：

```text
$sync-project-context Save the current task state.
$sync-project-context Restore all project tasks on this computer.
$sync-project-context Synchronize all project tasks bidirectionally and show conflicts before applying changes.
```

在 Claude Code 中，将这些示例的 `$` 前缀替换为 `/`。

### 协调与沟通

#### `orchestrate-agent-work` （实验性）

协调已明确授权的子代理，同时对集成结果保持责任。

**功能：**

- 将并行工作划分为范围明确、互不重叠的任务；
- 依据共享约束监控并协调代理结果；
- 在报告完成之前验证合并后的结果。

**不会执行：**

- 在用户或项目指令未授权子代理时进行委托；
- 将审批权限、秘密信息、破坏性清理或未经批准的外部修改转交给其他代理；
- 将各子任务独立完成视为集成成功的证明。

**调用方式：**

```text
$orchestrate-agent-work Delegate these independent subtasks to agents and verify the integrated result.
```

#### `synchronize-team-skills` （实验性）

使每名团队成员在项目范围内的代理技能，与项目文档中一份经过审查的清单保持一致。

**功能：**

- 在已批准的文档根目录中创建或读取 `team-agent-skills.md`；
- 将声明的 Codex 和 Claude Code 技能与已验证的项目副本进行比较；
- 在不改变环境的情况下，报告缺失、过时、较新、未验证、项目覆盖和额外项保留状态；
- 为一个固定集合版本构建绑定清单摘要的安装计划；
- 获得批准后仅安装已审查的集合，再验证可观察状态。

**不会执行：**

- 自动将某台工作站的偶然状态转化为团队政策；
- 保存秘密信息、用户配置、机器路径或插件认证信息；
- 移除额外技能、降级较新的副本或更改全局安装；
- 声称运行中的代理任务已重新加载新安装的技能。

**调用方式：**

```text
$synchronize-team-skills Check this project's installed skills against the reviewed team manifest.
$synchronize-team-skills Align my project skills with the team documentation after showing the plan.
$synchronize-team-skills Add maintain-project-digest to the reviewed team skill set.
```

#### `notify-via-telegram`

通过 Telegram 发送长时间运行代理任务的生命周期更新。

**功能：**

- 报告开始、里程碑、中间结果、问题、阻塞项和完成情况；
- 交互式验证机器人，并协助发现目标聊天；
- 为 Windows 上的 Codex Desktop 提供掩码显示、便于粘贴的首次使用表单；
- 将凭据保存在用户配置目录中，并在设置期间发送测试通知；
- 支持每个项目使用单独的聊天或论坛话题，并明确选择全局加项目投递或仅项目投递；
- 导出不含秘密信息的项目路由值，以便通过 `sync-project-context` 协调；
- 使用 Python 3 标准库，在 Windows、macOS 和 Linux 上运行。

**不会执行：**

- 将机器人令牌放入对话、shell 历史或仓库；
- 在计算机之间复制全局机器人令牌或 Telegram 认证状态；
- 在用户要求仅在当前任务中报告进度时发送通知；
- 充当通用 Telegram 机器人开发框架。

**调用方式：**

```text
$notify-via-telegram Configure Telegram notifications for long tasks.
$notify-via-telegram Configure this project to notify its team chat only, instead of the global destination.
```

### 基础设施与运维

#### `operate-yandex-cloud`

操作明确配置、限定在项目范围内的 Yandex Cloud 基础设施。

**功能：**

- 在项目配置中保存共享的 Cloud/Folder ID，在被忽略的本地配置中保存工作站的 `yc` 配置档案；
- 检测所需工具集、检查最低版本，并运行只读上下文预检；
- 支持限定范围的 CLI、SSH、Terraform、Ansible、Helm、Kubernetes、部署、数据库、存储、DNS、监控、备份和事件处理工作流；
- 提供 JSON 输出和跨平台 Python 辅助程序。

**不会执行：**

- 在缺少提供商上下文时，从通用 SSH、Kubernetes、Terraform 或部署请求推断使用 Yandex Cloud；
- 将凭据保存在共享项目配置中；
- 在目标、上下文和授权尚未确定之前应用修改。

**调用方式：**

```text
$operate-yandex-cloud Configure this project for Yandex Cloud operations.
```

### 技能集合演进

#### `discover-skill-candidates` （实验性）

在限定范围的项目和上下文证据中发现可复用技能构想，但不创建技能。

**功能：**

- 盘点限定范围、相对于项目的 `AGENTS.md` 文件，并提供 Git 和行级来源信息；
- 可选盘点项目文档、所选文件、限定范围的 Git 历史、结构元数据，以及来自可用对话或 `sync-project-context` 交接的用户已确认摘要；
- 将候选项排序为推荐、待调查或拒绝，并与现有目录比较；
- 主动为每个符合条件的候选项提供安全贡献到 `kolabse/skills`、本地创建或暂缓的选择；
- 将所选构想导出为已脱敏、绑定摘要的贡献包，供维护者独立验证。

**不会执行：**

- 修改项目规则，或搭建、发布、安装技能；
- 枚举对话、摄取原始对话记录或广泛扫描源码；
- 导出原始规则、本地路径、秘密信息、URL 或电子邮件地址；
- 未经审查，将纯政策性、易变、敏感或一次性约定提升为可复用工作流。

**调用方式：**

```text
$discover-skill-candidates Analyze this project's local rules and prepare an evidence-backed backlog of reusable skill ideas without creating anything.
```

#### `release-skill-collection`

规划、验证、审计和清理确定性的技能集合发布。

**功能：**

- 检查版本、变更日志就绪情况、仓库状态、测试、安全性、确定性归档和校验和；
- 验证绑定提交的留出测试、使用方、平台、审查和本地检查证据；
- 审计不可变的 GitHub 资源、清单、校验和和认证；
- 在清理前，证明临时分支是已合并、树相同还是补丁等价；
- 仅基于未更改的安全计划和摘要有效的已发布版本审计，应用已明确确认的清理。

**不会执行：**

- 推断已获得提交、打标签、推送、调度工作流或发布资源的许可；
- 移动现有标签或替换已发布资源；
- 仅凭名称、过时计划或未经审计的发布版本删除分支。

**调用方式：**

```text
$release-skill-collection Plan and verify release vX.Y.Z of this skill collection, but do not publish it yet.
```

## 支持的组合

目录定义了三种可复用的有序工作流：

- `protected-push`：先同步仓库，再生成当前验证证据；工作日志和 Telegram 通知为可选项。
- `yandex-cloud-operation`：先同步仓库，再运行限定范围的云操作；项目政策启用时，验证、工作日志和 Telegram 通知为可选项。
- `skill-collection-release`：先同步仓库，规划并在本地验证集合发布，再绑定推送前证据；工作日志和 Telegram 通知为可选项。

必需步骤在无法验证时拒绝继续。可选日志和通知报告自身失败，不改变主要操作的已观察结果。
使用 `scripts/compose_skills.py` 解析确切计划；通过 `--evidence` 传入匹配 `schemas/composition-evidence.schema.json`、绑定摘要的文档，验证步骤顺序、必需结果和非阻塞的可选失败。
验证后的结果遵循 `schemas/composition-result.schema.json`。

## 添加技能

遵循 [CONTRIBUTING.md](CONTRIBUTING.md)，并从 [`templates/skill-template.md`](../../../templates/skill-template.md) 开始。
每个技能都必须有相匹配的 `skill-catalog.json` 条目，记录所有者、平台、状态、许可证和来源。
将项目专用配置保留在已安装技能文件夹之外，避免更新覆盖配置。

不要为单个技能添加仓库级安装程序。当集合需要在 ChatGPT 和 Codex 之间进行受管理安装和更新时，除这种跨代理布局外，还应将集合打包为 OpenAI 插件。

在本地运行集合检查：

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py
```

为代理或模型选择器准备盲触发测试套件：

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
```

套件仅包含技能名称、公开描述、不透明用例 ID 和提示词，不包含预期标签和作者理由。
选择器返回严格 JSON，列出每个用例选中的所有技能；使用以下命令对观测结果评分：

```shell
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

使用 `run` 并在 `--` 后放置命令，调用从标准输入读取套件并向标准输出写入预测的选择器。
不要将提供商凭据放入命令参数。被忽略的 `.trigger-evals/` 目录默认使生成的套件、预测和报告不进入提交。
大型开发套件默认以每批 64 个用例、绑定摘要的批次发送，避免较长的严格 JSON 响应截断不透明用例 ID。
可通过 `--batch-size` 调整限制，而无需向选择器暴露预期标签。

发布之前，运行单独版本化且由摘要锁定的留出测试；不要在开发期间用它来调整描述：

```shell
python scripts/trigger_evals.py prepare \
  --corpus release-holdout \
  --output .trigger-evals/release-holdout.json
```

将候选报告与同一留出版本生成的报告比较：

```shell
python scripts/trigger_evals.py compare \
  --candidate .trigger-evals/candidate-report.json \
  --markdown-output .trigger-evals/comparison.md
```

当断言摘要不同，或总体准确率、精确率、召回率或单个技能指标下降超过配置限值时，比较会拒绝通过。
默认使用 `skill-catalog.json` 指定的已发布基线；仅在有意与另一份兼容报告比较时传入 `--baseline`。

对于非确定性的模型选择器，收集不少于三次的奇数次盲预测运行，并对其多数决策评分：

```shell
python scripts/trigger_evals.py aggregate \
  --corpus release-holdout \
  --predictions run-1.json run-2.json run-3.json \
  --predictions-output .trigger-evals/aggregate.json \
  --json-output .trigger-evals/candidate-report.json
```

## 验证发布

带版本的发布包含确定性 ZIP 和 TAR.GZ 归档、`release-manifest.json` 和 `SHA256SUMS`。
将四个资源下载到同一目录，然后验证：

```shell
python scripts/build_release.py --verify <download-directory>/SHA256SUMS
```

GitHub 还为每个上传的发布资源提供 SHA-256 `digest`。发布工作流另外发布 GitHub 产物认证。
针对本仓库验证已下载的产物：

```shell
gh attestation verify <artifact> --repo kolabse/skills
```
