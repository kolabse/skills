# kolabse/skills

[English](../../../README.md) | [Русский](../ru/README.md) | [Español](../es/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Português (Brasil)](../pt-BR/README.md) | [日本語](../ja/README.md) | [Italiano](../it/README.md) | 한국어 | [简体中文](../zh-CN/README.md) | [Türkçe](../tr/README.md) | [Polski](../pl/README.md) | [Українська](../uk/README.md)

이 문서는 한국어 번역입니다. 내용이 다를 경우 [영어 원문](../../../README.md)이 기준입니다.

kolabse가 관리하는 재사용 가능한 에이전트 스킬 모음입니다.

[Apache License 2.0](../../../LICENSE)에 따라 사용이 허가됩니다. Copyright 2026 kolabse.

## 목차

- [스킬 설치](#스킬-설치)
  - [Git 마켓플레이스에서 설치](#git-마켓플레이스에서-설치)
- [설치된 스킬 업데이트](#설치된-스킬-업데이트)
  - [저장소 복제 없이 실행](#저장소-복제-없이-실행)
  - [전역 설치 검사](#전역-설치-검사)
- [로컬 개발용 Codex 플러그인 설치 또는 업데이트](#로컬-개발용-codex-플러그인-설치-또는-업데이트)
- [사용 가능한 스킬](#사용-가능한-스킬)
  - [개발 및 코드 품질](#개발-및-코드-품질)
    - [`develop-with-test-first-evidence`](#develop-with-test-first-evidence-실험적)
    - [`review-code-changes`](#review-code-changes-실험적)
    - [`diagnose-software-defects`](#diagnose-software-defects-실험적)
    - [`resolve-git-conflicts`](#resolve-git-conflicts-실험적)
  - [저장소 및 변경 전달](#저장소-및-변경-전달)
    - [`synchronize-git-repositories`](#synchronize-git-repositories)
    - [`verify-before-push`](#verify-before-push)
    - [`coordinate-code-documentation-repositories`](#coordinate-code-documentation-repositories-실험적)
    - [`execute-configured-gitflow-releases`](#execute-configured-gitflow-releases-실험적)
    - [`execute-verified-development-lifecycle`](#execute-verified-development-lifecycle-실험적)
  - [프로젝트 지식 및 연속성](#프로젝트-지식-및-연속성)
    - [`maintain-work-log`](#maintain-work-log)
    - [`maintain-project-digest`](#maintain-project-digest-실험적)
    - [`sync-project-context`](#sync-project-context)
  - [조율 및 소통](#조율-및-소통)
    - [`orchestrate-agent-work`](#orchestrate-agent-work-실험적)
    - [`synchronize-team-skills`](#synchronize-team-skills-실험적)
    - [`report-skill-feedback`](#report-skill-feedback-실험적)
    - [`notify-via-telegram`](#notify-via-telegram)
  - [인프라 및 운영](#인프라-및-운영)
    - [`operate-yandex-cloud`](#operate-yandex-cloud)
  - [스킬 모음의 발전](#스킬-모음의-발전)
    - [`discover-skill-candidates`](#discover-skill-candidates-실험적)
    - [`release-skill-collection`](#release-skill-collection)
- [지원하는 조합](#지원하는-조합)
- [스킬 추가](#스킬-추가)
- [릴리스 검증](#릴리스-검증)

## 스킬 설치

여러 에이전트를 지원하는 [`skills`](https://skills.sh) CLI로 하나 이상의 스킬을
현재 사용자에게 전역으로 설치하세요.

```shell
npx skills@latest add kolabse/skills --global
```

CLI는 `skills/` 아래의 폴더를 찾고 설치할 스킬을 선택하게 한 뒤 선택한 코딩
에이전트에 복사합니다. 이는 외부 설치 프로그램이며, 이 저장소는 자체 npm 패키지를
게시하거나 실행하지 않습니다.

Codex 사용자는 대신 `$skill-installer`에 이 저장소의 스킬 설치를 요청할 수 있습니다.
예를 들어 다음 경로를 사용할 수 있습니다.

```text
https://github.com/kolabse/skills/tree/main/skills/operate-yandex-cloud
```

비대화형 설치에서는 대상 에이전트를 명시적으로 선택하세요.

```shell
npx skills@1.5.22 add kolabse/skills --agent codex --copy --global -y
npx skills@1.5.22 add kolabse/skills --agent claude-code --copy --global -y
```

에이전트에 “선택한 스킬을 전역으로 설치하고 기존 규칙을 교체하지 않으면서 이 프로젝트의
누락된 설정만 초기화해 주세요.”라고 요청하세요. 이후 전역 스킬 경로를 사용하세요.

```shell
python ~/.agents/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent codex --apply --yes --json
python ~/.claude/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent claude-code --apply --yes --json
```

규칙이 없으면 기본 접두사는 `feature/`, `bugfix/`, `release/`, `hotfix/`이고,
커밋 유형은 `feat`, `fix`, `refactor`, `docs`, `test`, `chore`입니다.
명시된 프로젝트 접두사, 브랜치 역할, 커밋 형식이 계속 우선합니다.
상시 브랜치나 Git 훅은 생성하지 않습니다. 관리형 전역 업데이트는 명시적으로 선택한
활성 프로젝트에 같은 초기화를 적용하며, 확인되지 않은 업데이트는 계획만 세웁니다.

관찰 가능한 기본값이 충분하다면 프로젝트 수명 주기 계약을 즉시 초기화하세요.
에이전트에 맞는 경로를 사용하세요.

```shell
python ~/.agents/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent codex --apply --yes --json
python ~/.claude/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent claude-code --apply --yes --json
```

마켓플레이스 및 플러그인 설치는 전역 설치이고 활성 프로젝트 루트가 없으므로,
스킬은 프로젝트에서 처음 사용될 때 동일한 초기화를 수행합니다.

지원되는 전역 경로는 Codex의 `~/.agents/skills/`와 Claude Code의
`~/.claude/skills/`입니다. 프로젝트에는 설정, 관리형 규칙, 의도적인 프로젝트별 설정만
이 payload 폴더 밖에 보관합니다.

이 저장소는 ChatGPT/Codex 및 Claude Code용 스킬 전용 `kolabse-skills` 플러그인으로도
패키징됩니다. `skills/` 아래의 모든 폴더가 포함됩니다. 여러 에이전트용 `npx skills`
설치는 두 플러그인 형식과 독립적으로 계속 사용할 수 있습니다.

### Git 마켓플레이스에서 설치

Codex 사용자는 다음 명령으로 저장소 마켓플레이스를 등록하고 전체 모음을 설치할 수 있습니다.

```shell
codex plugin marketplace add kolabse/skills --ref main
codex plugin add kolabse-skills@kolabse
```

Git 스냅샷을 갱신하고 현재 플러그인 버전을 다시 설치하려면 다음을 실행하세요.

```shell
codex plugin marketplace upgrade kolabse
codex plugin add kolabse-skills@kolabse
```

Claude Code 사용자는 다음 명령으로 같은 저장소를 등록하고 플러그인을 설치할 수 있습니다.

```shell
claude plugin marketplace add kolabse/skills
claude plugin install kolabse-skills@kolabse
```

`claude plugin marketplace update kolabse`로 명시적으로 갱신하거나 Claude Code에서
마켓플레이스 자동 업데이트를 활성화하세요. 설치 또는 업데이트 후에는 새 에이전트 세션을
시작하여 현재 스킬 구성을 인식하도록 하세요.

마켓플레이스 카탈로그는
[`.agents/plugins/marketplace.json`](../../../.agents/plugins/marketplace.json)과
[`.claude-plugin/marketplace.json`](../../../.claude-plugin/marketplace.json)입니다.
플러그인 페이로드는 [`.codex-plugin/plugin.json`](../../../.codex-plugin/plugin.json)과
[`.claude-plugin/plugin.json`](../../../.claude-plugin/plugin.json)에 정의되어 있습니다.
두 카탈로그 모두 기준 저장소인 `kolabse/skills`의 `main`에서 가져오며,
릴리스 버전의 기준은 계속 플러그인 매니페스트입니다.

공개 등록 자료는 소스와 함께 관리합니다. [지원](SUPPORT.md),
[개인정보 처리방침](PRIVACY.md), [이용약관](TERMS.md), 재현 가능한
[마켓플레이스 제출 패킷](../../../docs/marketplace-submissions/)을 참고하세요.
공식 디렉터리에 게시하는 것은 여전히 검토를 거치는 유지관리자 작업입니다.
Git 마켓플레이스에서 설치하는 데는 디렉터리 승인이 필요하지 않습니다.

테스트 시 Claude Code는 `claude --plugin-dir <collection-root>`를 사용하여 압축을 푼
릴리스나 신뢰할 수 있는 체크아웃을 직접 불러올 수 있습니다. 일반적인 개인 또는 프로젝트
사용에는 Git 마켓플레이스나 위의 명시적 `npx skills ... --agent claude-code` 명령을
권장합니다. Claude Code는 `AGENTS.md`가 아닌 `CLAUDE.md`를 읽습니다.
프로젝트에 이미 공유 `AGENTS.md` 규칙이 있다면 `@AGENTS.md`를 포함한 최소한의
`CLAUDE.md`로 하나의 기준 규칙 문서를 유지할 수 있습니다.

## 설치된 스킬 업데이트

`skills` CLI는 전역 원본과 콘텐츠 해시를 `~/.agents/.skill-lock.json`에 기록합니다.
기록된 원본에서 전역 설치를 업데이트하세요.

```shell
npx skills@1.5.22 update -g -y
```

스킬 하나 또는 전역 설치를 업데이트하려면 다음을 실행하세요.

```shell
npx skills@1.5.22 update verify-before-push -g -y
npx skills@1.5.22 update -g -y
```

기존 프로젝트 범위 복사본은 계획을 검토한 뒤 전역 설치로 중앙화해야 합니다.
마이그레이션은 전역 복사본을 먼저 설치하고 검증한 뒤 기존 payload를 백업하며,
프로젝트 설정과 관련 없는 스킬을 보존합니다.

```shell
python scripts/centralize_skill_installations.py plan --project-path . --json
python scripts/centralize_skill_installations.py apply --project-path . --expected-plan-sha256 <plan-value> --yes --json
```

버전 등을 한정하지 않은 `kolabse/skills` 잠금 항목은 저장소의 기본 브랜치를 따르며,
모음 릴리스를 고정하지 않습니다. 업데이트가 교체할 수 있으므로 복사된 전역 payload를
편집하지 마세요. 프로젝트 및 사용자 설정은 설치된 스킬 폴더 밖에 둡니다.

복제한 체크아웃이나 릴리스 아카이브에서 하나의 명시적인 작업으로 업데이트하고
지원되는 프로젝트 설정을 마이그레이션하세요.

```shell
python scripts/manage_installed_skills.py update --scope global --project-path . --yes --migrate
python scripts/manage_installed_skills.py doctor --scope global --project-path . --json
```

외부 설치 프로그램을 호출하거나 설정을 변경하지 않고 정확한 선택 대상을 미리 확인하세요.

```shell
python scripts/manage_installed_skills.py plan --scope global --project-path . --json
```

계획에는 원본 식별 정보, 현재 및 대상 버전, 출처, 마이그레이션 후보,
`update`, `unchanged`, `adopt-and-update`, `blocked` 작업이 표시됩니다.
스키마는 `schemas/manager-plan.schema.json`입니다. `update`에 `--json`을 추가하세요.
업데이트 및 마이그레이션 결과는 `schemas/manager-result.schema.json`을 따릅니다.

이름을 지정하지 않으면 관리자는 전역 잠금의 kolabse 스킬만 확인하며 관련 없는 전역
스킬은 포함하지 않습니다. 기존 프로젝트 업데이트는 알림과 마이그레이션을 위한 전환
경로로만 남습니다. `execute-verified-development-lifecycle`을 전역 업데이트하는 경우,
관리자는 프로젝트 정보가 충분하면 누락된 설정도 초기화하고 `created`, `configured`,
`blocked` 중 하나의 설정 결과를 반환합니다.

Telegram 사용자 설정도 마이그레이션해야 하는 경우에만 `--include-user-config`를
추가하세요. `status`와 `doctor`는 읽기 전용입니다. `migrate`는 이미 존재하는 설정
파일만 변경하며, 사용하지 않는 스킬을 설정하지 않습니다. 설치된 각 스킬에
`collection-metadata.json`이 포함되므로 외부 잠금 형식에 버전 필드가 없어도 `status`는
모음 버전을 보고합니다. `provenance_status`도 보고합니다. `verified`에는 모음 메타데이터와
기준 GitHub 원본 또는 콘텐츠가 검증된 로컬 잠금 원본이 모두 필요합니다.
`legacy-unverified`는 메타데이터 도입 이전의 설치를 나타내며, `mismatch`는 절대
업데이트하지 않습니다. 로컬 식별은 디렉터리 이름이 아닌 플러그인 매니페스트, 카탈로그,
스킬 내용으로 이루어지므로 체크아웃 이름은 변경해도 됩니다.

v1.2 이전의 메타데이터 없는 설치는 보고된 원본을 검토한 후에만 채택하세요.

```shell
python scripts/manage_installed_skills.py status --scope global --project-path . --json
python scripts/manage_installed_skills.py update --scope global --project-path . --yes --adopt-legacy
```

채택 플래그가 임의의 파일에 신뢰를 부여하는 것은 아닙니다. 원본이 이미 `kolabse/skills`로
정규화되거나 로컬 체크아웃 검증을 통과해야 하며, 일반 업데이트 후 진단에서 설치된
메타데이터를 검증해야 합니다. 외부 CLI는 `sourceType: local` 개발용 잠금 항목을 제자리에서
업데이트하지 않습니다. 관리자는 CLI의 무변경 종료를 실패로 취급합니다. 이러한 스킬은 원래의
`--skill` 및 `--agent` 선택으로 로컬 원본에서 다시 추가하세요.

### 저장소 복제 없이 실행

신뢰할 수 있는 릴리스나 이 저장소에서 `scripts/bootstrap_update.py`를 다운로드하세요.
이 스크립트는 최신 안정 릴리스를 확인하고, `SHA256SUMS` 및 GitHub 빌드 출처에 따라
릴리스 ZIP을 검증한 다음, 격리된 임시 압축 해제 디렉터리에서 관리자를 실행합니다.

```shell
python bootstrap_update.py doctor --json
python bootstrap_update.py plan --json
python bootstrap_update.py update --yes --migrate --json
```

버전을 고정하려면 `--release v1.15.0`을 사용하세요. 부트스트랩은 증명 검증에 `gh`가
필요하며 완료 시 임시 디렉터리를 제거합니다. 오프라인 캐시에는 `--offline-archive`와
`--offline-checksums`를 모두 제공하세요. `gh`가 GitHub에 연결할 수 있다면 출처 검증은
계속 필수입니다. `--allow-unattested-offline`은 보장 수준이 낮아지는 명시적 모드입니다.
캐시된 체크섬만 검증하므로 독립적으로 신뢰할 수 있는 채널을 통해 이동한 산출물에만
사용해야 합니다. 롤백하려면 이전 릴리스를 선택하고 기존 롤백 절차를 사용하세요.
설정 마이그레이션은 계속 정방향만 지원합니다.

### 전역 설치 검사

지원하는 전역 상태는 의도적으로 공유 `~/.agents/.skill-lock.json` v3 잠금 파일로
제한됩니다. 설치 페이로드는 Codex의 경우 `~/.agents/skills`, Claude Code의 경우
`~/.claude/skills`에 있습니다. 관리자는 다른 사용자 디렉터리를 검색하지 않습니다.
기본값은 계속 Codex이며, Claude 페이로드 배치를 사용하려면 `--agent claude-code`를 전달하세요.

```shell
python scripts/manage_installed_skills.py status --scope global --json
python scripts/manage_installed_skills.py doctor --scope global --json
python scripts/manage_installed_skills.py plan verify-before-push --scope global --json
python scripts/manage_installed_skills.py update verify-before-push --scope global --yes --json
python scripts/manage_installed_skills.py status --scope global --agent claude-code --json
```

테스트용 또는 명시적으로 옮긴 호환 배치를 읽기 전용으로 검사하려면 `--global-root`를
사용하세요. 외부 CLI가 옮긴 루트를 대상으로 지정할 수 없으므로 해당 루트는 업데이트할 수
없습니다. 알 수 없는 잠금 형식은 변경 없이 보고합니다.

스킬 파일을 롤백하려면 먼저 프로젝트 및 사용자 설정을 백업하고, 원래 설치에 사용했던
동일한 스킬 및 에이전트 대상을 지정하여 필요한 릴리스 태그를 재설치하세요. 예:

```shell
npx skills@1.5.22 add kolabse/skills@v1.1.0 --skill verify-before-push --agent codex --copy --global -y
```

릴리스에 다운그레이드가 명시적으로 문서화되어 있지 않으면 설정 마이그레이션은
정방향만 지원합니다. 이전 스킬 파일을 복원해도 설정이 다운그레이드되지는 않습니다.
이전 릴리스가 새 형식을 읽을 수 없다면 해당 버전에 맞는 설정 백업을 복원하세요.

## 로컬 개발용 Codex 플러그인 설치 또는 업데이트

로컬 플러그인 개발을 위해 기본 개인 마켓플레이스 항목을 생성하거나 갱신하고,
플러그인을 로컬 플러그인 디렉터리에 복사하며, Codex 캐시 갱신용 값을 추가한 뒤 활성화하세요.

```shell
python scripts/install_personal_plugin.py --activate
```

설치 프로그램은 다른 개인 마켓플레이스 항목을 보존하고 저장소 매니페스트를 편집하지
않습니다. 이는 일반적인 Git 마켓플레이스 설치가 아닌 대체 개발 경로입니다.
체크아웃을 업데이트한 후 다시 실행하고, 새 Codex 작업을 시작하여 갱신된 스킬을 불러오세요.
설치 버전, 플러그인 경로, 마켓플레이스 경로 및 이름을 기록하려면 `--json`을 사용하세요.

## 사용 가능한 스킬

안정 스킬과 실험적으로 추가된 스킬은 `skill-catalog.json`에 표시되어 있습니다.
프로젝트용 설정 경로, 안전 경계, 문서화된 명령 인터페이스는
[CONTRIBUTING.md](CONTRIBUTING.md)의 호환성 정책을 따릅니다.

이제 각 카탈로그 항목은 설정 범위, 읽기 전용 JSON 상태 명령, 기능, 전제 조건,
선택적 연동을 선언합니다. 상태를 유지하는 스킬은 멱등적 설정 명령도 선언합니다.
버전이 지정된 JSON/YAML 설정은 스킬과 함께 JSON Schema 및 마이그레이션 명령을 제공합니다.

카탈로그는 아래 우선순위에 따라 사용자 관점의 주목적별로 분류됩니다.
각 스킬에는 정확히 하나의 기본 범주가 있습니다. 서로 독립적인 태그는 수명 주기 단계,
범위, 동작, 연동을 설명하며 성숙도 상태는 별개입니다. 기계 판독 가능한 기준 분류와
통제 어휘는 [`skill-catalog.json`](../../../skill-catalog.json)에 있으며,
[`schemas/skill-catalog.schema.json`](../../../schemas/skill-catalog.schema.json)에 따라 검증합니다.

통제된 태그의 분류 축은 다음과 같습니다.

- 수명 주기 단계: `prepare`, `investigate`, `implement`, `verify`, `publish`,
  `operate`, `document`, `handoff`;
- 범위: `project`, `repository`, `multi-repository`, `workstation`,
  `external-service`, `skill-collection`;
- 동작: `read-only-planning`, `mutation`, `evidence-producing`,
  `orchestration`, `notification`;
- 연동: `git`, `github`, `telegram`, `google-drive`, `yandex-cloud`.

### 개발 및 코드 품질

#### `develop-with-test-first-evidence` (실험적)

증거로 뒷받침되는 실패 확인, 통과, 리팩터링 주기를 통해 동작을 구현합니다.

**수행하는 작업:**

- 구현 전에 의도한 동작상의 이유로 실패하는 집중 테스트를 기록합니다.
- 집중 테스트와 더 넓은 범위의 통과 결과를 최종 변경 상태에 연결합니다.
- 번들 스키마와 도우미로 보존 가능한 증거를 검증합니다.

**수행하지 않는 작업:**

- 관련 없는 동작을 망가뜨려 실패 결과를 만들어 내지 않습니다.
- 사후 테스트를 테스트 우선 개발이라고 부르지 않습니다.
- 기존 실패, 환경 문제로 인한 실패, 최종 상태의 실패를 숨기지 않습니다.

**호출 방법:**

```text
$develop-with-test-first-evidence Implement this behavior with a recorded red-green-refactor cycle.
```

#### `review-code-changes` (실험적)

정의된 변경을 검토하여 조치 가능한 정확성, 보안, 신뢰성, 호환성 결함을 찾습니다.

**수행하는 작업:**

- 정확한 기준 상태와 변경된 상태를 확인합니다.
- 영향, 발현 조건, 우선순위, 좁게 특정한 위치와 함께 증거에 기반한 발견 사항을 보고합니다.
- 불확실성과 의미 있는 테스트 공백을 명시합니다.

**수행하지 않는 작업:**

- 스타일 취향이나 근거 없는 추측을 결함으로 보고하지 않습니다.
- 별도 승인 없이 발견 사항을 구현하거나, 댓글을 게시하거나, 리뷰를 승인하지 않습니다.
- 범위가 정해진 리뷰를 일반적인 코드 설명으로 대신하지 않습니다.

**호출 방법:**

```text
$review-code-changes Review this branch against its declared baseline and report actionable findings.
```

#### `diagnose-software-defects` (실험적)

실패와 회귀를 조사하여 근거 있는 인과 설명이나 순위가 매겨진 가설을 제시합니다.

**수행하는 작업:**

- 가능한 경우 증상의 범위를 한정하고 안전하게 재현합니다.
- 관련 증거로 경쟁 가설을 검증합니다.
- 근본 원인, 기여 조건, 영향 범위, 확신 수준, 수정 검증 계획을 보고합니다.

**수행하지 않는 작업:**

- 상관관계로부터 인과관계를 추론하지 않습니다.
- 운영 환경을 변경하거나 실패 증거를 버리지 않습니다.
- 진단만 요청받았을 때 추측에 기반한 수정을 구현하지 않습니다.

**호출 방법:**

```text
$diagnose-software-defects Diagnose this regression and distinguish evidence from hypotheses.
```

#### `resolve-git-conflicts` (실험적)

관련 없는 작업을 보존하면서 승인된 merge, rebase 또는 cherry-pick 충돌을
의미에 맞게 해결합니다.

**수행하는 작업:**

- 진행 중인 작업, 기준, 양쪽 변경, 병합되지 않은 각 경로를 조사합니다.
- 결합 후 의도된 동작이 이해되는 충돌만 조정합니다.
- 해결한 경로를 검증하고 남아 있는 Git 작업 단계를 명시합니다.

**수행하지 않는 작업:**

- 일반적인 저장소 이력 분기를 파일 충돌 작업으로 취급하지 않습니다.
- 자동으로 stash, reset, abort, continue, 강제 푸시를 수행하거나 관련 없는 경로를
  스테이징하지 않습니다.
- 모호한 생성 파일, 바이너리, 스키마 또는 제품 관련 결정을 추측으로 처리하지 않습니다.

**호출 방법:**

```text
$resolve-git-conflicts Resolve the active merge conflicts path by path and validate the result.
```

### 저장소 및 변경 전달

#### `synchronize-git-repositories`

로컬 작업을 덮어쓰지 않고 현재 원격 상태를 확인합니다.

**수행하는 작업:**

- 작업과 관련된 저장소만 찾아 추적 중인 원격 저장소에서 가져옵니다.
- 작업 트리가 깨끗하고 뒤처지기만 한 브랜치를 fast-forward로 갱신합니다.
- 수정 사항이 있는 상태, 앞선 상태, 분기된 상태, 분리된 HEAD, 추적 대상이 없는 상태,
  작업 진행 중인 상태를 보고합니다.
- 프로젝트 정책이 요구하면 첫 편집 전에 검증된 최신 `main`에서 승인된 기능 브랜치를 게시합니다.

**수행하지 않는 작업:**

- 자동으로 stash, reset, rebase, merge, clean, 브랜치 전환, 강제 푸시를 수행하지 않습니다.
- 분기를 숨기거나 fetch 성공을 로컬 브랜치가 갱신되었다는 증거로 취급하지 않습니다.
- 관련 없는 저장소를 검색하거나 업데이트하지 않습니다.

**호출 방법:**

```text
$synchronize-git-repositories Configure this project's repository synchronization policy.
```

#### `verify-before-push`

프로젝트에 선언된 검사를 푸시할 정확한 Git 상태와 연결합니다.

**수행하는 작업:**

- 설치된 스킬 폴더 밖에 저장소가 관리하는 검증 정책을 설정합니다.
- 선언된 검사를 실행하고 정확한 커밋, 작업 트리, 업스트림 상태, 검증 설정에 대한 증거를 기록합니다.
- 보호 대상 증거가 누락되거나, 실패하거나, 잘못되거나, 오래되면 안전하게 진행을 차단합니다.

**수행하지 않는 작업:**

- 정책이 적용되지 않는 관련 없는 저장소를 차단하지 않습니다.
- 임의의 셸 명령을 파싱하거나 IDE 또는 에이전트 전용 훅을 설치하지 않습니다.
- 이전 Git 상태의 검사 성공을 현재 증거로 취급하지 않습니다.

**호출 방법:**

```text
$verify-before-push Configure this project's verification policy and checks.
```

#### `coordinate-code-documentation-repositories` (실험적)

구현과 기준 문서가 별도의 Git 저장소에 있을 때 감사 가능한 하나의 프로젝트 변경을 조율합니다.

**수행하는 작업:**

- 프로젝트에 선언된 구현 및 문서 저장소 역할을 확인합니다.
- 두 시작 커밋과 권위 있는 문서 원본에 연결된 읽기 전용 계획을 만듭니다.
- 요구 사항, 동작, 검증, 운영 영향, 제한 사항 등 설정된 주제의 문서 증거를 요구합니다.
- 공동 완료를 보고하기 전에 두 게시 커밋의 식별 정보, 검증 증거, 저장소 간 추적 가능성을 검증합니다.

**수행하지 않는 작업:**

- 디렉터리나 저장소 이름에서 저장소 역할을 추측하지 않습니다.
- 기준 문서를 일일 요약으로 대체하지 않습니다.
- 직접 편집, 커밋, 푸시, 병합을 수행하거나 수정 사항이 있거나 분기된 저장소를 복구하지 않습니다.
- 예상한 문서 파일이 존재한다는 이유만으로 의미상 일치한다고 주장하지 않습니다.

**호출 방법:**

```text
$coordinate-code-documentation-repositories Implement this change across the declared code and canonical documentation repositories and verify both published outcomes.
```

#### `execute-configured-gitflow-releases` (실험적)

프로젝트에 선언된 GitFlow 계약에 따라 표준 및 핫픽스 릴리스 경로를 실행합니다.

**수행하는 작업:**

- 버전 관리되는 프로젝트 설정에서 개발, 운영, 핫픽스 네임스페이스, 원격 저장소,
  통과 조건, 기본 경로 정책을 확인합니다.
- 원본 커밋과 원격 브랜치 식별 정보에 연결된 읽기 전용 계획을 고정합니다.
- 표준 경로와 핫픽스 경로에 동일하게 선언된 공통 통과 조건을 적용합니다.
- 검토된 운영 게시, 배포 증거, 핫픽스의 개발 계열 필수 재통합을 검증합니다.

**수행하지 않는 작업:**

- 관례적인 브랜치 이름을 추측하거나 핫픽스를 기본 경로로 사용하지 않습니다.
- 트렁크 기반 전달이나 이 모음의 특수한 릴리스 체인을 지원하지 않습니다.
- 보호된 운영 브랜치에 직접 푸시하거나, 통과 조건을 우회하거나, 이력을 다시 쓰거나,
  분기를 알리지 않고 복구하지 않습니다.
- 재통합 검증 전에 운영 핫픽스를 완전히 완료된 것으로 취급하지 않습니다.

**호출 방법:**

```text
$execute-configured-gitflow-releases Run the standard release route declared by this project and verify the resulting production identity.
$execute-configured-gitflow-releases Run an explicit hotfix release and verify its reintegration into the declared development line.
```

#### `execute-verified-development-lifecycle` (실험적)

기능 준비부터 검토된 개발 통합, 전달 관찰, 문서화, 증거로 입증된 정리까지
프로젝트가 선언한 경로를 계획하고 검증합니다.

**수행하는 작업:**

- 편집 전에 다이제스트로 연결된 계획을 고정하고 보존된 증거를 사용하여 순서대로 체크포인트를 진행합니다.
- 관리형 업데이트 또는 첫 사용 시 저장소 루트, 추적 중인 업스트림, 검사, 문서를 관찰할 수 있으면
  보수적인 프로젝트 설정을 만들고 적용한 모든 기본값을 보고합니다.
- 편집 전 기능 브랜치 준비, 테스트 우선, 변경 범위 사전 점검, 리뷰, 정확한 상태의 푸시,
  파이프라인, 문서화, 개발 통합, 위임된 운영 작업, 전달, 스모크 테스트, 알림, 정리 조건을 검증합니다.
- 실패 후 선언된 체크포인트로 돌아가 오래된 후속 증거를 무효화합니다.

**수행하지 않는 작업:**

- 프로젝트 증거가 모호하면 제공업체별 어댑터, 저장소 역할, 전달 정책, 승인을 추측하지 않습니다.
- 직접 푸시하거나, 리뷰를 열거나 병합하거나, 배포하거나, 알림을 보내거나, 문서를 편집하거나,
  리소스를 삭제하지 않습니다.
- 운영 전달을 실행하지 않습니다. 이는 `$execute-configured-gitflow-releases` 같은
  승인된 릴리스 워크플로에 계속 위임됩니다.

필수 스킬 `$synchronize-git-repositories`, `$develop-with-test-first-evidence`,
`$verify-before-push`, `$review-code-changes`를 먼저 설치하고 설정하세요.
프로젝트가 관리하는 버전 1 수명 주기 계약이 없으면 첫 계획 전에 관찰 가능한 프로젝트
정보에서 초기화합니다. 프로젝트에 더 구체적인 정책이 선언되면 보고된 기본값을 검토하고
정교화하세요. 선택적 스킬은 프로젝트에서 대응하는 체크포인트를 활성화한 경우에만
설치하세요. 해당 스킬은 `$orchestrate-agent-work`, `$diagnose-software-defects`,
`$resolve-git-conflicts`, `$coordinate-code-documentation-repositories`,
`$maintain-work-log`, `$maintain-project-digest`, `$notify-via-telegram`,
`$execute-configured-gitflow-releases`입니다.

**호출 방법:**

```text
$execute-verified-development-lifecycle Plan and verify this change through the project's configured development lifecycle.
```

### 프로젝트 지식 및 연속성

#### `maintain-work-log`

`docs/reports/work-log.md`에 날짜별 기준 프로젝트 작업 일지를 유지합니다.

**수행하는 작업:**

- 중요한 변경, 운영 작업, 진단, 결정, 검증, 차단 요인, 롤백 결과를 기록합니다.
- 프로젝트의 기존 일지 형식을 보존합니다.
- 사용 가능한 Git 및 프로젝트 작업 증거에서 누락된 이력을 재구성합니다.

**수행하지 않는 작업:**

- 프로젝트 정책이나 사용자가 요구하지 않는 일반 작업에서는 활성화되지 않습니다.
- 비밀 정보, 애플리케이션 로그, 시간 추적 또는 개인 메모를 쓰지 않습니다.
- 사용 가능한 증거로 뒷받침할 수 없는 사건을 주장하지 않습니다.

**호출 방법:**

```text
$maintain-work-log Configure this project to maintain its dated work log.
```

#### `maintain-project-digest` (실험적)

완료된 프로젝트 변경의 사용자용 일일 요약을 프로젝트 문서에 유지합니다.

**수행하는 작업:**

- 완료된 변경을 오늘 날짜 아래에 새 기능, 개선, 수정, 보안, 문서, 중요한 동작 변경으로 묶습니다.
- 짧고 비기술적인 결과를 작성하고 비어 있는 범주는 생략합니다.
- 최신 날짜를 앞에 두고 이전의 모든 날짜는 변경하지 않습니다.
- 콘텐츠에 연결된 계획, 협력적 잠금, 원자적 교체, 중복 탐지를 사용하여 여러 개발자가
  같은 날 안전하게 기여할 수 있도록 합니다.

**수행하지 않는 작업:**

- 프로젝트가 문서 위치를 명확히 지정하지 않았다면 위치를 선택하거나 만들지 않습니다.
- 계획, 실패한 실험, 내부 구현 활동, 근거 없는 사용자 이점을 기록하지 않습니다.
- 기술 작업 일지, 버전 릴리스 노트 또는 일반적인 변경 이력을 대체하지 않습니다.
- 일반적인 당일 업데이트 중 과거 요약 기간을 다시 작성하지 않습니다.

**호출 방법:**

```text
$maintain-project-digest Add today's completed user-visible changes to the project digest.
```

#### `sync-project-context`

민감한 정보를 제거한 비공개 프로젝트 상태와 채팅별 이어서 작업하기 위한 상태를
컴퓨터 간에 동기화합니다. 이 스킬은 독립적인 실제 기기 Google Drive 실행 두 번이
결정적 승격 조건을 통과하여 안정 상태가 되었습니다.

**수행하는 작업:**

- 승인된 동기화 폴더나 연결된 Google Drive에 변경 불가능한 체크포인트를 저장하며,
  기기별 로컬 설정은 저장소 밖에 둡니다.
- 별도 조건 없는 동기화 요청은 연결된 Google Drive를 기본으로 사용하되 기존 백엔드를
  보존하고, 로컬 동기화 폴더 사용 전에는 명시적 동의를 요구합니다.
- 새 컴퓨터에서 원격 폴더를 만들기 전에 저장소 지문으로 검증된 기존 Google Drive 매핑을
  찾으며, 불완전한 목록, 신뢰할 수 없는 가시성 또는 중복 일치가 있으면 차단합니다.
- 프로젝트 작업마다 불투명한 스트림 하나를 유지합니다. 상세 기준 상태에 이어 짧은 차이 기록,
  표시된 제목의 정확한 값, 결정, 검증, 미해결 질문, 다음 단계, Git 지문을 보관합니다.
- 최근 및 고정된 모든 프로젝트 작업을 저장하거나 복원하거나 양방향으로 계획하되,
  변경되지 않았거나 진행 중인 작업은 건너뛰고 충돌을 명시적으로 드러냅니다.
- 다운로드한 스냅샷을 검증하고, 업로드를 다시 읽어 확인하며, 다른 프로젝트로의 복원을 방지하고,
  비밀 정보일 가능성이 높은 패턴을 거부합니다.
- Git이 아직 제공하지 않는 선언된 규칙, 스킬, 플러그인, 안전한 스칼라 설정을 별도의
  환경 매니페스트에 기록합니다.

**수행하지 않는 작업:**

- 소스 파일, diff, 원시 대화 기록, 숨겨진 추론, 자격 증명, OAuth 토큰 또는
  설치된 스킬과 플러그인을 복사하지 않습니다.
- Git이 이미 전달하는 규칙이나 의존성을 중복하지 않습니다.
- Git이 관리하는 대상 규칙을 알리지 않고 덮어쓰지 않습니다. 적용 단계에서는 명시적 계획 후,
  현재 에이전트용으로 선택된 누락된 비추적 `AGENTS.md` 또는 `CLAUDE.md`만 만들 수 있습니다.
- 메타데이터 전용 모드에서 브랜치 이름이나 파일 경로를 포함하지 않습니다.
  표시된 작업 제목은 의도적으로 계속 포함합니다.

Codex Desktop은 문서화된 일괄 작업 검색, 생성, 이름 변경, Google Drive 커넥터
워크플로를 지원합니다. Claude Code는 이식 가능한 체크포인트, 로컬 폴더 저장,
환경 조정의 핵심 기능을 사용할 수 있지만 세션 저장소는 검사하지 않으며,
Codex 전용 일괄 작업은 지원되지 않는 것으로 안전하게 차단됩니다.

**호출 방법:**

각 컴퓨터에서 한 번 설정하세요.

```text
$sync-project-context Configure this clone in metadata-only mode. Use connected Google Drive by default unless I explicitly request another approved channel.
```

이후 작업 단위 또는 일괄 명령을 사용하세요. 예:

```text
$sync-project-context Save the current task state.
$sync-project-context Restore all project tasks on this computer.
$sync-project-context Synchronize all project tasks bidirectionally and show conflicts before applying changes.
```

Claude Code에서는 이 예시의 `$` 접두사를 `/`로 바꾸세요.

### 조율 및 소통

#### `orchestrate-agent-work` (실험적)

통합 결과에 대한 책임을 유지하면서 명시적으로 승인된 하위 에이전트를 조율합니다.

**수행하는 작업:**

- 병렬 작업을 범위가 한정되고 겹치지 않는 과제로 나눕니다.
- 공유 제약 조건에 따라 에이전트 결과를 관찰하고 조정합니다.
- 완료를 보고하기 전에 통합 결과를 검증합니다.

**수행하지 않는 작업:**

- 사용자나 프로젝트 지침이 하위 에이전트를 허용하지 않으면 위임하지 않습니다.
- 승인 권한, 비밀 정보, 파괴적 정리 또는 승인되지 않은 외부 변경을 다른 에이전트에
  넘기지 않습니다.
- 독립적으로 완료된 하위 작업을 통합 성공의 증거로 취급하지 않습니다.

**호출 방법:**

```text
$orchestrate-agent-work Delegate these independent subtasks to agents and verify the integrated result.
```

#### `synchronize-team-skills` (실험적)

각 팀원의 전역 스킬을 프로젝트 문서의 검토된 매니페스트에 맞추고 프로젝트 설정은 로컬에 유지합니다.

**수행하는 작업:**

- 승인된 문서 루트에 `team-agent-skills.md`를 만들거나 읽습니다.
- 선언된 Codex 및 Claude Code 스킬을 검증된 전역 복사본과 비교합니다.
- 환경을 변경하지 않고 누락, 오래됨, 더 최신, 미검증, 프로젝트 재정의, 보존된 추가 항목 상태를
  보고합니다.
- 하나의 고정된 모음 버전에 대해 매니페스트 다이제스트에 연결된 설치 계획을 만듭니다.
- 승인 후 검토된 구성만 설치하고 관찰 가능한 상태를 검증합니다.

**수행하지 않는 작업:**

- 한 워크스테이션의 우연한 상태를 자동으로 팀 정책으로 만들지 않습니다.
- 비밀 정보, 사용자 설정, 기기 경로 또는 플러그인 인증 정보를 저장하지 않습니다.
- 추가 스킬을 제거하거나, 더 최신인 복사본을 다운그레이드하거나, 승인 없이 기존 프로젝트 복사본을 삭제하지 않습니다.
- 실행 중인 에이전트 작업이 새로 설치한 스킬을 다시 불러왔다고 주장하지 않습니다.

**호출 방법:**

```text
$synchronize-team-skills Check this project's installed skills against the reviewed team manifest.
$synchronize-team-skills Align my project skills with the team documentation after showing the plan.
$synchronize-team-skills Add maintain-project-digest to the reviewed team skill set.
```

#### `report-skill-feedback` (실험적)

명시적 동의를 받은 뒤 관찰된 스킬 사용에 관한 제한적이고 비식별화된 보고서를 작성합니다. 초안에는 코드, 전체 대화, 비밀, 이름, 경로, URL을 포함하지 않습니다. 전체 내용을 미리 보여 주며 별도의 제출 승인을 받은 경우에만 `kolabse/skills`로 전송합니다. GitHub Issue는 제출 계정과 연결되므로 익명이 아닙니다.

**Aufruf / Invocation:**

```text
$report-skill-feedback Prepare a de-identified preview about this observed skill use; do not submit it yet.
```

#### `notify-via-telegram`

오래 실행되는 에이전트 작업의 수명 주기 소식을 Telegram으로 보냅니다.

**수행하는 작업:**

- 시작, 주요 단계, 중간 결과, 문제, 차단 요인, 완료를 보고합니다.
- 대화형으로 봇을 검증하고 대상 채팅을 찾도록 돕습니다.
- Windows의 Codex Desktop에서 값을 가려 표시하고 붙여넣기 쉬운 첫 사용 양식을 제공합니다.
- 자격 증명을 사용자 설정 디렉터리에 저장하고 설정 중 테스트 알림을 보냅니다.
- 프로젝트별 별도 채팅 또는 포럼 토픽을 지원하며, 전역 및 프로젝트에 함께 전달할지
  프로젝트에만 전달할지 명시적으로 선택하게 합니다.
- `sync-project-context`를 통한 조정을 위해 비밀 정보가 없는 프로젝트 라우팅 값을 내보냅니다.
- Windows, macOS, Linux에서 Python 3 표준 라이브러리로 실행됩니다.

**수행하지 않는 작업:**

- 봇 토큰을 대화, 셸 기록 또는 저장소에 넣지 않습니다.
- 전역 봇 토큰이나 Telegram 인증 상태를 컴퓨터 간에 복사하지 않습니다.
- 사용자가 진행 상황을 현재 작업 안에만 남겨 달라고 요청하면 알림을 보내지 않습니다.
- 일반적인 Telegram 봇 개발 프레임워크 역할을 하지 않습니다.

**호출 방법:**

```text
$notify-via-telegram Configure Telegram notifications for long tasks.
$notify-via-telegram Configure this project to notify its team chat only, instead of the global destination.
```

### 인프라 및 운영

#### `operate-yandex-cloud`

명시적으로 설정된 프로젝트 범위의 Yandex Cloud 인프라를 운영합니다.

**수행하는 작업:**

- 공유 Cloud/Folder ID를 프로젝트 설정에 저장하고 워크스테이션의 `yc` 프로필은
  Git 추적에서 제외된 로컬 설정에 보관합니다.
- 필요한 도구 모음을 감지하고 최소 버전을 확인하며 읽기 전용 컨텍스트 사전 점검을 실행합니다.
- 범위가 한정된 CLI, SSH, Terraform, Ansible, Helm, Kubernetes, 배포, 데이터베이스,
  스토리지, DNS, 모니터링, 백업, 사고 대응 워크플로를 지원합니다.
- JSON 출력과 교차 플랫폼 Python 도우미를 제공합니다.

**수행하지 않는 작업:**

- 제공업체 컨텍스트가 없는 일반적인 SSH, Kubernetes, Terraform 또는 배포 요청에서
  Yandex Cloud를 추측하지 않습니다.
- 공유 프로젝트 설정에 자격 증명을 저장하지 않습니다.
- 대상, 컨텍스트, 승인이 확정되기 전에 변경을 적용하지 않습니다.

**호출 방법:**

```text
$operate-yandex-cloud Configure this project for Yandex Cloud operations.
```

### 스킬 모음의 발전

#### `discover-skill-candidates` (실험적)

스킬을 만들지 않고 범위가 한정된 프로젝트 및 컨텍스트 증거에서 재사용 가능한 스킬 아이디어를 찾습니다.

**수행하는 작업:**

- 범위가 한정된 프로젝트 상대 경로의 `AGENTS.md` 파일 목록을 Git 및 줄 단위 출처와 함께 정리합니다.
- 선택적으로 프로젝트 문서, 선택된 파일, 범위가 한정된 Git 이력, 구조 메타데이터,
  사용 가능한 채팅이나 `sync-project-context` 인계에서 사용자가 확인한 요약을 정리합니다.
- 후보를 추천, 조사 필요, 거부로 분류하고 기존 카탈로그와 비교합니다.
- 자격을 갖춘 모든 후보에 대해 `kolabse/skills`로 안전하게 기여하거나, 로컬에서 만들거나,
  보류할 것을 선제적으로 제안합니다.
- 유지관리자가 독립적으로 검증할 수 있도록 선택된 아이디어를 민감한 정보를 제거하고
  다이제스트로 연결한 기여 패키지로 내보냅니다.

**수행하지 않는 작업:**

- 프로젝트 규칙을 수정하거나 스킬의 뼈대를 만들거나 게시하거나 설치하지 않습니다.
- 채팅을 열거하거나, 원시 대화 기록을 수집하거나, 소스 코드를 광범위하게 검색하지 않습니다.
- 원시 규칙, 로컬 경로, 비밀 정보, URL 또는 이메일 주소를 내보내지 않습니다.
- 검토 없이 정책만 담은 규칙, 변동이 심한 규칙, 민감한 규칙 또는 일회성 규칙을
  재사용 가능한 워크플로로 승격하지 않습니다.

**호출 방법:**

```text
$discover-skill-candidates Analyze this project's local rules and prepare an evidence-backed backlog of reusable skill ideas without creating anything.
```

#### `release-skill-collection`

결정적으로 재현 가능한 스킬 모음 릴리스를 계획, 검증, 감사하고 정리합니다.

**수행하는 작업:**

- 버전, 변경 이력 준비 상태, 저장소 상태, 테스트, 보안, 결정적 아카이브, 체크섬을 검사합니다.
- 커밋에 연결된 홀드아웃, 대상 에이전트 설치, 플랫폼, 리뷰, 로컬 검사 증거를 검증합니다.
- 변경 불가능한 GitHub 에셋, 매니페스트, 체크섬, 증명에 대한 감사를 수행합니다.
- 정리 전에 임시 브랜치가 병합되었는지, 동일한 트리인지, 패치가 동등한지 입증합니다.
- 변경되지 않은 안전한 계획과 다이제스트가 유효한 게시 릴리스 감사가 있을 때만
  명시적으로 확인된 정리를 적용합니다.

**수행하지 않는 작업:**

- 커밋, 태그 생성, 푸시, 워크플로 실행 요청 또는 에셋 게시 권한을 추측하지 않습니다.
- 기존 태그를 이동하거나 게시된 에셋을 교체하지 않습니다.
- 이름만 보고, 오래된 계획으로, 또는 감사되지 않은 릴리스에서 브랜치를 삭제하지 않습니다.

**호출 방법:**

```text
$release-skill-collection Plan and verify release vX.Y.Z of this skill collection, but do not publish it yet.
```

## 지원하는 조합

카탈로그는 재사용 가능한 세 가지 순서 있는 워크플로를 정의합니다.

- `protected-push`: 저장소를 동기화한 다음 최신 검증 증거를 생성합니다.
  작업 일지와 Telegram 알림은 선택 사항입니다.
- `yandex-cloud-operation`: 저장소를 동기화한 다음 범위가 한정된 클라우드 작업을 실행합니다.
  검증, 작업 일지, Telegram 알림은 프로젝트 정책으로 활성화했을 때 선택적으로 수행합니다.
- `skill-collection-release`: 저장소를 동기화하고 모음 릴리스를 계획하여 로컬에서 검증한 다음,
  푸시 전 증거를 연결합니다. 작업 일지와 Telegram 알림은 선택 사항입니다.

필수 단계는 실패 시 진행을 차단합니다. 선택적 로깅 및 알림은 기본 작업의 관찰된 결과를
바꾸지 않고 자체 실패를 보고합니다. `scripts/compose_skills.py`로 정확한 계획을 확인하세요.
단계 순서, 필수 결과, 진행을 차단하지 않는 선택적 실패를 검증하려면
`schemas/composition-evidence.schema.json`에 맞는 다이제스트 연결 문서를
`--evidence`로 전달하세요. 검증된 결과는 `schemas/composition-result.schema.json`을 따릅니다.

## 스킬 추가

[CONTRIBUTING.md](CONTRIBUTING.md)를 따르고
[`templates/skill-template.md`](../../../templates/skill-template.md)에서 시작하세요.
모든 스킬에는 소유자, 플랫폼, 상태, 라이선스, 출처를 기록한 해당 `skill-catalog.json`
항목이 있어야 합니다. 업데이트가 덮어쓰지 못하도록 프로젝트별 설정은 설치된 스킬 폴더 밖에 두세요.

개별 스킬을 위한 저장소 수준 설치 프로그램을 추가하지 마세요. ChatGPT와 Codex 전반에서
관리형 설치 및 업데이트가 필요하다면, 이 교차 에이전트 배치에 더해 모음을 OpenAI
플러그인으로 패키징하세요.

로컬에서 다음 모음 검사를 실행하세요.

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py
```

에이전트나 모델 선택기용 블라인드 호출 조건 테스트 모음을 준비하세요.

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
```

테스트 모음에는 스킬 이름, 공개 설명, 불투명한 사례 ID, 프롬프트만 포함됩니다.
예상 레이블과 작성자의 이유는 제외됩니다. 선택기는 각 사례에서 선택한 모든 스킬을
나열한 엄격한 JSON을 반환합니다. 관찰 결과를 다음과 같이 채점하세요.

```shell
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

표준 입력에서 테스트 모음을 읽고 표준 출력으로 예측을 쓰는 선택기를 호출하려면
`run`과 함께 `--` 뒤에 명령을 지정하세요. 제공업체 자격 증명은 명령 인수 밖에 보관하세요.
추적에서 제외된 `.trigger-evals/` 디렉터리를 사용하면 생성된 테스트 모음, 예측, 보고서가
기본적으로 커밋에 포함되지 않습니다. 큰 개발용 테스트 모음은 엄격한 JSON 응답이 길어져
불투명한 사례 ID가 잘리지 않도록 기본적으로 64개 사례씩 다이제스트에 연결된 배치로
전송됩니다. 예상 레이블을 선택기에 노출하지 않고 `--batch-size`로 한도를 조정하세요.

릴리스 전에는 별도로 버전 관리되고 다이제스트가 고정된 홀드아웃을 실행하세요.
개발 중 설명을 조정하는 데 사용하지 마세요.

```shell
python scripts/trigger_evals.py prepare \
  --corpus release-holdout \
  --output .trigger-evals/release-holdout.json
```

동일한 홀드아웃 버전으로 생성한 보고서와 후보 보고서를 비교하세요.

```shell
python scripts/trigger_evals.py compare \
  --candidate .trigger-evals/candidate-report.json \
  --markdown-output .trigger-evals/comparison.md
```

검증 항목 다이제스트가 다르거나 전체 정확도, 정밀도, 재현율 또는 스킬별 지표가 설정된
한도를 넘어 떨어지면 비교는 안전하게 실패 처리됩니다. 기본적으로 `skill-catalog.json`에
지정된 게시 기준 보고서를 사용합니다. 의도적으로 다른 호환 보고서와 비교하는 경우에만
`--baseline`을 전달하세요.

비결정적인 모델 선택기는 최소 세 번 이상 홀수 회의 블라인드 예측 실행을 수집하고
다수결 결정을 채점하세요.

```shell
python scripts/trigger_evals.py aggregate \
  --corpus release-holdout \
  --predictions run-1.json run-2.json run-3.json \
  --predictions-output .trigger-evals/aggregate.json \
  --json-output .trigger-evals/candidate-report.json
```

## 릴리스 검증

버전이 지정된 릴리스에는 결정적으로 재현 가능한 ZIP 및 TAR.GZ 아카이브,
`release-manifest.json`, `SHA256SUMS`가 포함됩니다. 네 에셋을 모두 한 디렉터리에
다운로드하고 다음 명령으로 검증하세요.

```shell
python scripts/build_release.py --verify <download-directory>/SHA256SUMS
```

GitHub는 업로드된 모든 릴리스 에셋에 대해 SHA-256 `digest`도 제공합니다.
릴리스 워크플로는 GitHub 산출물 증명도 게시합니다. 다운로드한 산출물을
이 저장소와 대조하여 검증하세요.

```shell
gh attestation verify <artifact> --repo kolabse/skills
```
