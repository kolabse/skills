# kolabse/skills

[English](../../../README.md) | [Русский](../ru/README.md) | [Español](../es/README.md) | [Français](../fr/README.md) | Deutsch | [Português (Brasil)](../pt-BR/README.md) | [日本語](../ja/README.md) | [Italiano](../it/README.md) | [한국어](../ko/README.md) | [简体中文](../zh-CN/README.md) | [Türkçe](../tr/README.md) | [Polski](../pl/README.md) | [Українська](../uk/README.md)

Diese Übersetzung dient der Orientierung. Maßgeblich ist die [englische Originalfassung](../../../README.md).

Wiederverwendbare Agenten-Skills, gepflegt von kolabse.

Lizenziert unter der [Apache License 2.0](../../../LICENSE). Copyright 2026 kolabse.

## Inhaltsverzeichnis

- [Skills installieren](#skills-installieren)
  - [Aus den Git-Marketplaces installieren](#aus-den-git-marketplaces-installieren)
- [Installierte Skills aktualisieren](#installierte-skills-aktualisieren)
  - [Ohne Klonen des Repositories ausführen](#ohne-klonen-des-repositories-ausführen)
  - [Globale Installationen prüfen](#globale-installationen-prüfen)
- [Ein Codex-Plugin für die lokale Entwicklung installieren oder aktualisieren](#ein-codex-plugin-für-die-lokale-entwicklung-installieren-oder-aktualisieren)
- [Verfügbare Skills](#verfügbare-skills)
  - [Entwicklung und Codequalität](#entwicklung-und-codequalität)
    - [`develop-with-test-first-evidence`](#develop-with-test-first-evidence-experimentell)
    - [`review-code-changes`](#review-code-changes-experimentell)
    - [`diagnose-software-defects`](#diagnose-software-defects-experimentell)
    - [`resolve-git-conflicts`](#resolve-git-conflicts-experimentell)
  - [Repositories und Bereitstellung von Änderungen](#repositories-und-bereitstellung-von-änderungen)
    - [`synchronize-git-repositories`](#synchronize-git-repositories)
    - [`verify-before-push`](#verify-before-push)
    - [`coordinate-code-documentation-repositories`](#coordinate-code-documentation-repositories-experimentell)
    - [`execute-configured-gitflow-releases`](#execute-configured-gitflow-releases-experimentell)
    - [`execute-verified-development-lifecycle`](#execute-verified-development-lifecycle-experimentell)
  - [Projektwissen und Kontinuität](#projektwissen-und-kontinuität)
    - [`maintain-work-log`](#maintain-work-log)
    - [`maintain-project-digest`](#maintain-project-digest-experimentell)
    - [`sync-project-context`](#sync-project-context)
  - [Koordination und Kommunikation](#koordination-und-kommunikation)
    - [`orchestrate-agent-work`](#orchestrate-agent-work-experimentell)
    - [`synchronize-team-skills`](#synchronize-team-skills-experimentell)
    - [`report-skill-feedback`](#report-skill-feedback-experimentell)
    - [`notify-via-telegram`](#notify-via-telegram)
  - [Infrastruktur und Betrieb](#infrastruktur-und-betrieb)
    - [`operate-yandex-cloud`](#operate-yandex-cloud)
  - [Weiterentwicklung der Skill-Sammlung](#weiterentwicklung-der-skill-sammlung)
    - [`discover-skill-candidates`](#discover-skill-candidates-experimentell)
    - [`release-skill-collection`](#release-skill-collection)
- [Unterstützte Kombinationen](#unterstützte-kombinationen)
- [Einen Skill hinzufügen](#einen-skill-hinzufügen)
- [Ein Release verifizieren](#ein-release-verifizieren)

## Skills installieren

Installieren Sie einen oder mehrere Skills mit der agentenübergreifenden
[`skills`](https://skills.sh)-CLI global für den aktuellen Benutzer:

```shell
npx skills@latest add kolabse/skills --global
```

Die CLI erkennt die Ordner unter `skills/`, lässt Sie die zu installierenden
Skills auswählen und kopiert sie zu den ausgewählten Coding-Agenten. Sie ist
ein externer Installer; dieses Repository veröffentlicht oder führt kein
eigenes npm-Paket aus.

Codex-Nutzer können alternativ `$skill-installer` bitten, einen Skill aus diesem
Repository zu installieren, beispielsweise von:

```text
https://github.com/kolabse/skills/tree/main/skills/operate-yandex-cloud
```

Wählen Sie für eine nicht interaktive Installation einen Agenten ausdrücklich aus:

```shell
npx skills@1.5.22 add kolabse/skills --agent codex --copy --global -y
npx skills@1.5.22 add kolabse/skills --agent claude-code --copy --global -y
```

Bitten Sie Ihren Agenten: „Installiere die ausgewählten Skills global und
initialisiere nur fehlende Einstellungen dieses Projekts, ohne bestehende
Regeln zu ersetzen.“ Verwenden Sie danach den globalen Skill-Pfad:

```shell
python ~/.agents/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent codex --apply --yes --json
python ~/.claude/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent claude-code --apply --yes --json
```

Fehlende Konventionen verwenden standardmäßig `feature/`, `bugfix/`, `release/`,
`hotfix/` sowie die Commit-Typen `feat`, `fix`, `refactor`, `docs`, `test`,
`chore`. Explizite Projektpräfixe, Branch-Rollen und Commit-Formate bleiben
maßgeblich. Es werden keine dauerhaften Branches oder Git-Hooks erstellt.
Globale verwaltete Updates führen denselben Bootstrap für das ausdrücklich
ausgewählte aktive Projekt aus; unbestätigte Updates planen ihn lediglich.

Initialisieren Sie den Projekt-Lebenszyklusvertrag sofort, wenn seine
beobachtbaren Standardwerte ausreichen
(verwenden Sie den Pfad für Ihren Agenten):

```shell
python ~/.agents/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent codex --apply --yes --json
python ~/.claude/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent claude-code --apply --yes --json
```

Marketplace-/Plugin-Installationen sind global und haben kein aktives
Projektstammverzeichnis; daher führt der Skill diesen Bootstrap bei der ersten
Verwendung im Projekt aus.

Die unterstützten globalen Pfade sind `~/.agents/skills/` für Codex und
`~/.claude/skills/` für Claude Code. Projekte enthalten nur Konfiguration,
verwaltete Regeln und ausdrücklich abweichende Projekteinstellungen außerhalb
dieser Payload-Ordner.

Das Repository wird auch als reines Skill-Plugin `kolabse-skills` für
ChatGPT/Codex und Claude Code paketiert. Jeder Ordner unter `skills/` ist
enthalten. Die agentenübergreifende Installation mit `npx skills` bleibt
unabhängig von beiden Plugin-Formaten verfügbar.

### Aus den Git-Marketplaces installieren

Codex-Nutzer können den Repository-Marketplace registrieren und die vollständige
Sammlung wie folgt installieren:

```shell
codex plugin marketplace add kolabse/skills --ref main
codex plugin add kolabse-skills@kolabse
```

Aktualisieren Sie den Git-Snapshot und installieren Sie die aktuelle
Plugin-Version erneut mit:

```shell
codex plugin marketplace upgrade kolabse
codex plugin add kolabse-skills@kolabse
```

Claude-Code-Nutzer können dasselbe Repository registrieren und das Plugin so installieren:

```shell
claude plugin marketplace add kolabse/skills
claude plugin install kolabse-skills@kolabse
```

Aktualisieren Sie es ausdrücklich mit `claude plugin marketplace update kolabse`
oder aktivieren Sie die automatische Marketplace-Aktualisierung in Claude Code.
Starten Sie nach Installation oder Update eine neue Agentensitzung, damit sie
den aktuellen Skill-Satz erkennt.

Die Marketplace-Kataloge sind
[`.agents/plugins/marketplace.json`](../../../.agents/plugins/marketplace.json)
und [`.claude-plugin/marketplace.json`](../../../.claude-plugin/marketplace.json).
Ihre Plugin-Nutzdaten werden durch
[`.codex-plugin/plugin.json`](../../../.codex-plugin/plugin.json) und
[`.claude-plugin/plugin.json`](../../../.claude-plugin/plugin.json) beschrieben.
Beide Kataloge beziehen das maßgebliche Repository `kolabse/skills` von `main`;
die Release-Versionierung bleibt in den Plugin-Manifesten maßgeblich.

Materialien für öffentliche Verzeichniseinträge werden mit dem Quellcode gepflegt:
[Support](SUPPORT.md), [Datenschutzerklärung](PRIVACY.md),
[Nutzungsbedingungen](TERMS.md) und das reproduzierbare
[Marketplace-Einreichungspaket](../../../docs/marketplace-submissions/).
Die Veröffentlichung in einem offiziellen Verzeichnis bleibt eine geprüfte
Aktion der Maintainer; die Installation aus den Git-Marketplaces erfordert
keine Verzeichnisfreigabe.

Claude Code kann beim Testen ein entpacktes Release oder einen vertrauenswürdigen
Checkout direkt mit `claude --plugin-dir <collection-root>` laden. Für die
gewöhnliche persönliche oder projektbezogene Nutzung bevorzugen Sie den
Git-Marketplace oder den obigen expliziten Befehl
`npx skills ... --agent claude-code`. Claude Code liest `CLAUDE.md`, nicht
`AGENTS.md`; wenn ein Projekt bereits gemeinsame `AGENTS.md`-Regeln besitzt,
bewahrt eine minimale `CLAUDE.md` mit `@AGENTS.md` ein einziges maßgebliches
Regeldokument.

## Installierte Skills aktualisieren

Die `skills`-CLI erfasst globale Quellen und Inhalts-Hashes in
`~/.agents/.skill-lock.json`. Aktualisieren Sie globale Installationen aus den
verzeichneten Quellen:

```shell
npx skills@1.5.22 update -g -y
```

Aktualisieren Sie einen einzelnen Skill oder globale Installationen mit:

```shell
npx skills@1.5.22 update verify-before-push -g -y
npx skills@1.5.22 update -g -y
```

Frühere projektbezogene Kopien müssen nach einer sichtbaren Planung zentralisiert werden.
Die Migration installiert und prüft zuerst die globale Kopie, sichert danach
die alte Payload und bewahrt Projektkonfiguration sowie fremde Skills:

```shell
python scripts/centralize_skill_installations.py plan --project-path . --json
python scripts/centralize_skill_installations.py apply --project-path . --expected-plan-sha256 <plan-value> --yes --json
```

Ein nicht weiter qualifizierter `kolabse/skills`-Lock folgt dem Standardbranch
des Repositories; er bindet die Installation nicht an ein Sammlungsrelease.
Bearbeiten Sie keine global kopierten Payloads, da ein Update sie ersetzen
kann. Projekt- und Benutzerkonfiguration bleiben außerhalb installierter
Skill-Ordner.

Aktualisieren und migrieren Sie unterstützte Projektkonfiguration aus einem
geklonten Checkout oder Release-Archiv in einem expliziten Vorgang:

```shell
python scripts/manage_installed_skills.py update --scope global --project-path . --yes --migrate
python scripts/manage_installed_skills.py doctor --scope global --project-path . --json
```

Zeigen Sie eine Vorschau der genauen Auswahl an, ohne den externen Installer
aufzurufen oder die Konfiguration zu ändern:

```shell
python scripts/manage_installed_skills.py plan --scope global --project-path . --json
```

Der Plan meldet Quellidentität, aktuelle und Zielversionen, Herkunft,
Migrationskandidaten sowie Aktionen `update`, `unchanged`, `adopt-and-update`
oder `blocked`. Sein Schema ist `schemas/manager-plan.schema.json`. Ergänzen
Sie `update` um `--json`; Update- und Migrationsergebnisse folgen
`schemas/manager-result.schema.json`.

Ohne Namensangaben ermittelt der Manager nur kolabse-Skills aus dem globalen
Lock; unabhängige globale Skills werden niemals aufgenommen. Das alte
Projektupdate bleibt nur als Übergang für Hinweis und Migration erhalten. Wenn
`execute-verified-development-lifecycle` global aktualisiert wird,
initialisiert der Manager außerdem dessen fehlende Konfiguration, sofern die
Projektfakten ausreichen, und liefert ein Konfigurationsergebnis `created`,
`configured` oder `blocked` zurück.

Ergänzen Sie `--include-user-config` nur, wenn auch die Telegram-Benutzerkonfiguration
migriert werden soll. `status` und `doctor` sind schreibgeschützt. `migrate`
ändert nur bereits vorhandene Konfigurationsdateien; es konfiguriert keine
ungenutzten Skills. Jeder installierte Skill enthält `collection-metadata.json`,
sodass `status` seine Sammlungsversion meldet, obwohl das externe Lock-Format
kein Versionsfeld hat. Es meldet auch `provenance_status`: `verified` erfordert
sowohl Sammlungsmetadaten als auch eine maßgebliche GitHub-Lock-Quelle oder
eine inhaltlich verifizierte lokale Lock-Quelle; `legacy-unverified` kennzeichnet
eine Installation vor Einführung der Metadaten; `mismatch` wird niemals
aktualisiert. Ein Checkout darf umbenannt werden, weil die lokale Identität aus
Plugin-Manifest, Katalog und Skill-Inhalten statt aus dem Verzeichnisnamen abgeleitet wird.

Übernehmen Sie eine metadatenfreie Installation vor v1.2 erst nach Prüfung der
gemeldeten Quelle:

```shell
python scripts/manage_installed_skills.py status --scope global --project-path . --json
python scripts/manage_installed_skills.py update --scope global --project-path . --yes --adopt-legacy
```

Die Übernahmeoption legitimiert keine beliebigen Dateien: Die Quelle muss
bereits zu `kolabse/skills` normalisierbar sein oder die lokale
Checkout-Validierung bestehen; die normale Diagnose nach dem Update muss die
installierten Metadaten verifizieren. Die externe CLI aktualisiert
Entwicklungs-Locks mit `sourceType: local` nicht an Ort und Stelle. Der Manager
behandelt diese wirkungslose CLI-Ausführung als Fehler; fügen Sie diese Skills
aus ihrer lokalen Quelle mit der ursprünglichen `--skill`- und `--agent`-Auswahl
erneut hinzu.

### Ohne Klonen des Repositories ausführen

Laden Sie `scripts/bootstrap_update.py` aus einem vertrauenswürdigen Release
oder diesem Repository herunter. Lassen Sie es dann das neueste stabile
Release ermitteln, das Release-ZIP anhand von `SHA256SUMS` und der
GitHub-Build-Herkunft verifizieren und den Manager aus einem isolierten,
temporär entpackten Verzeichnis ausführen:

```shell
python bootstrap_update.py doctor --json
python bootstrap_update.py plan --json
python bootstrap_update.py update --yes --migrate --json
```

Verwenden Sie `--release v1.15.0`, um eine Version festzulegen. Der Bootstrap
benötigt `gh` zur Prüfung der Attestierung und entfernt sein temporäres
Verzeichnis nach Abschluss. Geben Sie für einen Offline-Cache sowohl
`--offline-archive` als auch `--offline-checksums` an. Die Herkunftsprüfung
bleibt erforderlich, wenn `gh` GitHub erreichen kann.
`--allow-unattested-offline` ist ein ausdrücklich eingeschränkter Modus:
Er prüft nur die zwischengespeicherte Prüfsumme und sollte nur für Artefakte
verwendet werden, die über einen unabhängig vertrauenswürdigen Kanal
übertragen wurden. Ein Rollback erfolgt durch Auswahl eines älteren Releases
und das bestehende Rollback-Verfahren; Konfigurationsmigrationen bleiben
ausschließlich vorwärtsgerichtet.

### Globale Installationen prüfen

Der unterstützte globale Zustand ist bewusst auf den gemeinsamen v3-Lock
`~/.agents/.skill-lock.json` beschränkt. Installierte Nutzdaten liegen für Codex
in `~/.agents/skills` und für Claude Code in `~/.claude/skills`. Der Manager
durchsucht keine anderen Benutzerverzeichnisse. Codex bleibt der Standard;
geben Sie für die Claude-Nutzdatenstruktur `--agent claude-code` an:

```shell
python scripts/manage_installed_skills.py status --scope global --json
python scripts/manage_installed_skills.py doctor --scope global --json
python scripts/manage_installed_skills.py plan verify-before-push --scope global --json
python scripts/manage_installed_skills.py update verify-before-push --scope global --yes --json
python scripts/manage_installed_skills.py status --scope global --agent claude-code --json
```

Verwenden Sie `--global-root` zur schreibgeschützten Prüfung einer Teststruktur
oder einer ausdrücklich verlagerten kompatiblen Struktur. Verlagerte Wurzeln
können nicht aktualisiert werden, weil die externe CLI sie nicht gezielt
ansprechen kann. Unbekannte Lock-Formate werden ohne Änderungen gemeldet.

Um Skill-Dateien zurückzusetzen, sichern Sie zuerst die Projekt-/Benutzerkonfiguration
und installieren Sie dann den benötigten Release-Tag mit denselben Skills und
Agentenzielen wie bei der ursprünglichen Installation erneut, zum Beispiel:

```shell
npx skills@1.5.22 add kolabse/skills@v1.1.0 --skill verify-before-push --agent codex --copy --global -y
```

Konfigurationsmigrationen sind ausschließlich vorwärtsgerichtet, sofern ein
Release nicht ausdrücklich einen Downgrade dokumentiert. Das Wiederherstellen
älterer Skill-Dateien stuft die Konfiguration nicht herab; stellen Sie die
passende Konfigurationssicherung wieder her, wenn das ältere Release das neuere
Format nicht lesen kann.

## Ein Codex-Plugin für die lokale Entwicklung installieren oder aktualisieren

Erstellen oder aktualisieren Sie für die lokale Plugin-Entwicklung den
standardmäßigen persönlichen Marketplace-Eintrag, kopieren Sie das Plugin in
das lokale Plugin-Verzeichnis, ergänzen Sie einen Codex-Cachebuster und
aktivieren Sie es:

```shell
python scripts/install_personal_plugin.py --activate
```

Der Installer bewahrt andere persönliche Marketplace-Einträge und ändert das
Repository-Manifest nicht. Dies ist ein alternativer Entwicklungsweg, nicht
die gewöhnliche Installation über den Git-Marketplace. Führen Sie ihn nach
einem Update des Checkouts erneut aus und starten Sie anschließend eine neue
Codex-Aufgabe, damit die aktualisierten Skills geladen werden. Verwenden Sie
`--json`, um installierte Version, Plugin-Pfad, Marketplace-Pfad und
Marketplace-Namen zu erfassen.

## Verfügbare Skills

Stabile Skills und experimentelle Ergänzungen sind in `skill-catalog.json`
gekennzeichnet. Ihre projektbezogenen Konfigurationspfade, Sicherheitsgrenzen
und dokumentierten Befehlsschnittstellen folgen der Kompatibilitätsrichtlinie
in [CONTRIBUTING.md](CONTRIBUTING.md).

Jeder Katalogeintrag deklariert nun seinen Konfigurationsumfang, einen
schreibgeschützten JSON-Statusbefehl, Fähigkeiten, Voraussetzungen und optionale
Integrationen. Zustandsbehaftete Skills deklarieren außerdem einen idempotenten
Konfigurationsbefehl; versionierte JSON-/YAML-Konfigurationen veröffentlichen
ein JSON Schema und einen Migrationsbefehl neben dem Skill.

Der Katalog ist nach dem primären, nutzerbezogenen Zweck in der unten gezeigten
Prioritätsreihenfolge gegliedert. Jeder Skill hat genau eine primäre Kategorie.
Unabhängige Tags beschreiben Lebenszyklusphase, Umfang, Verhalten und
Integrationen; der Reifegrad bleibt davon unabhängig. Die maßgeblichen
maschinenlesbaren Zuordnungen und das kontrollierte Vokabular stehen in
[`skill-catalog.json`](../../../skill-catalog.json), validiert gegen
[`schemas/skill-catalog.schema.json`](../../../schemas/skill-catalog.schema.json).

Die kontrollierten Tag-Achsen sind:

- Lebenszyklusphase: `prepare`, `investigate`, `implement`, `verify`, `publish`,
  `operate`, `document` und `handoff`;
- Umfang: `project`, `repository`, `multi-repository`, `workstation`,
  `external-service` und `skill-collection`;
- Verhalten: `read-only-planning`, `mutation`, `evidence-producing`,
  `orchestration` und `notification`;
- Integration: `git`, `github`, `telegram`, `google-drive` und `yandex-cloud`.

### Entwicklung und Codequalität

#### `develop-with-test-first-evidence` (experimentell)

Verhalten durch nachweisgestützte Red-Green-Refactor-Zyklen implementieren.

**Was der Skill tut:**

- zeichnet vor der Implementierung auf, dass ein gezielter Test aus dem
  beabsichtigten verhaltensbezogenen Grund fehlschlägt;
- bindet erfolgreiche gezielte und umfassendere Testergebnisse an den
  endgültigen Änderungsstand;
- validiert dauerhaft gespeicherte Nachweise mit seinem mitgelieferten Schema
  und Hilfsprogramm.

**Was der Skill nicht tut:**

- ein rotes Ergebnis durch Beschädigung unabhängigen Verhaltens herbeiführen;
- nachträgliche Tests als Test-first-Entwicklung bezeichnen;
- bereits bestehende, umgebungsbedingte oder im Endzustand auftretende Fehler verbergen.

**Aufruf:**

```text
$develop-with-test-first-evidence Implement this behavior with a recorded red-green-refactor cycle.
```

#### `review-code-changes` (experimentell)

Eine abgegrenzte Änderung auf behebbare Fehler bei Korrektheit, Sicherheit,
Zuverlässigkeit und Kompatibilität prüfen.

**Was der Skill tut:**

- ermittelt eine genaue Baseline und den geänderten Stand;
- meldet nachweisgestützte Befunde mit Auswirkungen, Auslöser, Priorität und
  eng eingegrenzten Fundstellen;
- benennt Unsicherheit und wesentliche Testlücken ausdrücklich.

**Was der Skill nicht tut:**

- Stilvorlieben oder unbelegte Vermutungen als Fehler melden;
- Befunde umsetzen, Kommentare veröffentlichen oder ein Review ohne gesonderte
  Genehmigung freigeben;
- ein abgegrenztes Review durch eine allgemeine Codeerklärung ersetzen.

**Aufruf:**

```text
$review-code-changes Review this branch against its declared baseline and report actionable findings.
```

#### `diagnose-software-defects` (experimentell)

Fehler und Regressionen untersuchen, um eine belegte kausale Erklärung oder
nach Plausibilität geordnete Hypothesen zu liefern.

**Was der Skill tut:**

- grenzt das Symptom ein und reproduziert es nach Möglichkeit sicher;
- prüft konkurrierende Hypothesen anhand relevanter Nachweise;
- meldet Grundursache, beitragende Bedingungen, Auswirkungsbereich, Konfidenz
  und einen Plan zur Verifikation der Fehlerbehebung.

**Was der Skill nicht tut:**

- Kausalität aus Korrelation ableiten;
- die Produktionsumgebung verändern oder Fehlernachweise verwerfen;
- einen spekulativen Fix implementieren, wenn nur eine Diagnose angefordert wurde.

**Aufruf:**

```text
$diagnose-software-defects Diagnose this regression and distinguish evidence from hypotheses.
```

#### `resolve-git-conflicts` (experimentell)

Autorisierte Merge-, Rebase- oder Cherry-Pick-Konflikte semantisch auflösen und
dabei unabhängige Arbeit bewahren.

**Was der Skill tut:**

- prüft die aktive Operation, die Basis, beide Seiten und jeden nicht gemergten Pfad;
- löst nur Konflikte, deren beabsichtigtes kombiniertes Verhalten verstanden ist;
- validiert aufgelöste Pfade und benennt den verbleibenden Schritt der
  Git-Operation ausdrücklich.

**Was der Skill nicht tut:**

- gewöhnliche Repository-Divergenz als Dateikonfliktaufgabe behandeln;
- automatisch stash, reset, abort, continue oder force-push ausführen oder
  unabhängige Pfade stagen;
- bei mehrdeutigen generierten Dateien, Binärdateien, Schema- oder
  Produktentscheidungen raten.

**Aufruf:**

```text
$resolve-git-conflicts Resolve the active merge conflicts path by path and validate the result.
```


### Repositories und Bereitstellung von Änderungen

#### `synchronize-git-repositories`

Den aktuellen Remote-Zustand feststellen, ohne lokale Arbeit zu überschreiben.

**Was der Skill tut:**

- erkennt nur aufgabenrelevante Repositories und ruft deren verfolgte Remotes ab;
- aktualisiert saubere Branches, die ausschließlich zurückliegen, per Fast-Forward;
- meldet uncommittete Änderungen, vorausliegende oder divergierte Branches,
  losgelösten HEAD, fehlende Upstreams und laufende Git-Operationen;
- veröffentlicht vor der ersten Änderung einen autorisierten Feature-Branch
  vom verifizierten aktuellen `main`, wenn die Projektrichtlinie dies verlangt.

**Was der Skill nicht tut:**

- automatisch stash, reset, rebase, merge, clean, switch oder force-push ausführen;
- Divergenz verbergen oder einen erfolgreichen Fetch als Beweis dafür behandeln,
  dass der lokale Branch aktualisiert wurde;
- unabhängige Repositories durchsuchen oder aktualisieren.

**Aufruf:**

```text
$synchronize-git-repositories Configure this project's repository synchronization policy.
```

#### `verify-before-push`

Vom Projekt deklarierte Prüfungen an den genauen zu pushenden Git-Zustand binden.

**Was der Skill tut:**

- konfiguriert eine repositoryeigene Verifikationsrichtlinie außerhalb des
  installierten Skill-Ordners;
- führt deklarierte Prüfungen aus und erfasst Nachweise für genaue Commits,
  Worktrees, Upstream-Zustände und die Verifikationskonfiguration;
- blockiert sicher, wenn geschützte Nachweise fehlen, fehlgeschlagen,
  fehlerhaft oder veraltet sind.

**Was der Skill nicht tut:**

- unabhängige Repositories blockieren, die nicht unter die Richtlinie fallen;
- beliebige Shell-Befehle parsen oder IDE- beziehungsweise agentenspezifische
  Hooks installieren;
- eine erfolgreiche Prüfung eines älteren Git-Zustands als aktuellen Nachweis behandeln.

**Aufruf:**

```text
$verify-before-push Configure this project's verification policy and checks.
```

#### `coordinate-code-documentation-repositories` (experimentell)

Eine überprüfbare Projektänderung koordinieren, wenn Implementierung und
maßgebliche Dokumentation in getrennten Git-Repositories liegen.

**Was der Skill tut:**

- ermittelt die vom Projekt deklarierten Rollen für Implementierungs- und
  Dokumentationsrepository;
- erstellt einen schreibgeschützten Plan, der an beide Ausgangscommits und
  die maßgeblichen Dokumentationsquellen gebunden ist;
- verlangt Dokumentationsnachweise für konfigurierte Themen wie Anforderungen,
  Verhalten, Validierung, betriebliche Auswirkungen und Einschränkungen;
- verifiziert die Identitäten beider veröffentlichten Commits,
  Validierungsnachweise und repositoryübergreifende Nachverfolgbarkeit,
  bevor er den gemeinsamen Abschluss meldet.

**Was der Skill nicht tut:**

- Repository-Rollen aus Verzeichnis- oder Repository-Namen ableiten;
- maßgebliche Dokumentation durch eine tägliche Zusammenfassung ersetzen;
- selbst Repositories bearbeiten, committen, pushen, mergen oder solche mit
  uncommitteten Änderungen beziehungsweise Divergenz reparieren;
- inhaltliche Übereinstimmung allein deshalb behaupten, weil erwartete
  Dokumentationsdateien existieren.

**Aufruf:**

```text
$coordinate-code-documentation-repositories Implement this change across the declared code and canonical documentation repositories and verify both published outcomes.
```

#### `execute-configured-gitflow-releases` (experimentell)

Standard- und Hotfix-Release-Pfade anhand eines vom Projekt deklarierten
GitFlow-Vertrags ausführen.

**Was der Skill tut:**

- ermittelt Entwicklung, Produktion, Hotfix-Namensraum, Remote, Prüfschranken
  und Standardpfad-Richtlinie aus versionierter Projektkonfiguration;
- friert einen schreibgeschützten Plan ein, der an den Quellcommit und die
  Identitäten der Remote-Branches gebunden ist;
- wendet dieselben deklarierten gemeinsamen Prüfschranken auf Standard- und
  Hotfix-Pfade an;
- verifiziert die geprüfte Veröffentlichung in Produktion, Deployment-Nachweise
  und die zwingende Rückintegration eines Hotfixes in die Entwicklungslinie.

**Was der Skill nicht tut:**

- konventionelle Branch-Namen annehmen oder Hotfix als Standardpfad verwenden;
- Trunk-basierte Auslieferung oder die spezialisierte Release-Kette dieser
  Sammlung unterstützen;
- direkt in geschützte Produktions-Branches pushen, Prüfschranken umgehen,
  Verlauf umschreiben oder Divergenz stillschweigend reparieren;
- einen Produktions-Hotfix vor verifizierter Rückintegration als vollständig
  abgeschlossen behandeln.

**Aufruf:**

```text
$execute-configured-gitflow-releases Run the standard release route declared by this project and verify the resulting production identity.
$execute-configured-gitflow-releases Run an explicit hotfix release and verify its reintegration into the declared development line.
```

#### `execute-verified-development-lifecycle` (experimentell)

Einen vom Projekt deklarierten Weg von der Feature-Vorbereitung über geprüfte
Integration in die Entwicklung, Beobachtung der Auslieferung und Dokumentation
bis zur nachgewiesenen Bereinigung planen und verifizieren.

**Was der Skill tut:**

- friert vor der Bearbeitung einen Digest-gebundenen Plan ein und durchläuft
  geordnete Prüfpunkte anhand aufbewahrter Nachweise;
- erstellt bei einem verwalteten Update oder Erstaufruf eine zurückhaltende
  Projektkonfiguration, wenn Repository-Wurzeln, verfolgte Upstreams, Prüfungen
  und Dokumentation beobachtbar sind, und meldet jeden angewendeten Standardwert;
- verifiziert Prüfschranken für Feature-vor-Bearbeitung, Test-first,
  Preflight des Änderungsumfangs, Review, Push des exakten Zustands, Pipeline,
  Dokumentation, Entwicklungsintegration, delegierte Produktion, Auslieferung,
  Smoke-Test, Benachrichtigung und Bereinigung;
- kehrt nach einem Fehler zu einem deklarierten Prüfpunkt zurück und erklärt
  veraltete nachgelagerte Nachweise für ungültig.

**Was der Skill nicht tut:**

- anbieterspezifische Adapter, Repository-Rollen, Auslieferungsrichtlinien
  oder Genehmigungen erraten, wenn Projektnachweise mehrdeutig sind;
- selbst pushen, Reviews eröffnen oder mergen, deployen, benachrichtigen,
  Dokumentation bearbeiten oder Ressourcen löschen;
- die Produktionsauslieferung ausführen; sie bleibt an den genehmigten
  Release-Arbeitsablauf delegiert, etwa `$execute-configured-gitflow-releases`.

Installieren und konfigurieren Sie zuerst seine erforderlichen Skills:
`$synchronize-git-repositories`, `$develop-with-test-first-evidence`,
`$verify-before-push` und `$review-code-changes`. Ein fehlender projekteigener
Lebenszyklusvertrag der Version 1 wird vor dem ersten Plan anhand beobachtbarer
Projektfakten initialisiert; prüfen und präzisieren Sie seine gemeldeten
Standardwerte, wenn das Projekt spezifischere Richtlinien deklariert.
Installieren Sie optionale Skills nur, wenn das Projekt deren entsprechende
Prüfpunkte aktiviert: `$orchestrate-agent-work`, `$diagnose-software-defects`,
`$resolve-git-conflicts`, `$coordinate-code-documentation-repositories`,
`$maintain-work-log`, `$maintain-project-digest`, `$notify-via-telegram` und
`$execute-configured-gitflow-releases`.

**Aufruf:**

```text
$execute-verified-development-lifecycle Plan and verify this change through the project's configured development lifecycle.
```


### Projektwissen und Kontinuität

#### `maintain-work-log`

Das maßgebliche datierte Projektjournal unter `docs/reports/work-log.md` pflegen.

**Was der Skill tut:**

- erfasst wesentliche Änderungen, Operationen, Diagnosen, Entscheidungen,
  Verifikation, Blockaden und Rollback-Ergebnisse;
- bewahrt das bestehende Journalformat des Projekts;
- rekonstruiert fehlenden Verlauf aus verfügbaren Git- und Projektaufgabennachweisen.

**Was der Skill nicht tut:**

- sich für gewöhnliche Arbeit aktivieren, sofern Projektrichtlinie oder Benutzer
  dies nicht verlangen;
- Geheimnisse, Anwendungsprotokolle, Zeiterfassung oder persönliche Notizen schreiben;
- Ereignisse behaupten, die sich nicht durch verfügbare Nachweise belegen lassen.

**Aufruf:**

```text
$maintain-work-log Configure this project to maintain its dated work log.
```

#### `maintain-project-digest` (experimentell)

Eine tägliche nutzerorientierte Zusammenfassung abgeschlossener Projektänderungen
in der Projektdokumentation pflegen.

**Was der Skill tut:**

- gruppiert abgeschlossene Änderungen unter dem heutigen Datum als neue
  Fähigkeiten, Verbesserungen, Fehlerbehebungen, Sicherheit, Dokumentation
  oder wichtige Verhaltensänderungen;
- schreibt kurze, nicht technische Ergebnisse und lässt leere Kategorien aus;
- stellt neueste Daten voran und lässt jedes frühere Datum unverändert;
- verwendet einen inhaltsgebundenen Plan, eine kooperative Sperre, atomaren
  Austausch und Duplikaterkennung, damit mehrere Entwickler an einem Tag
  sicher beitragen können.

**Was der Skill nicht tut:**

- einen Dokumentationsort auswählen oder erstellen, wenn das Projekt keinen
  eindeutig vorgibt;
- Pläne, fehlgeschlagene Experimente, interne Implementierungsaktivitäten
  oder unbelegte Nutzervorteile erfassen;
- das technische Arbeitsprotokoll, Versionshinweise oder ein herkömmliches
  Changelog ersetzen;
- historische Zeiträume der Zusammenfassung bei einem gewöhnlichen Update
  am selben Tag umschreiben.

**Aufruf:**

```text
$maintain-project-digest Add today's completed user-visible changes to the project digest.
```

#### `sync-project-context`

Privaten, bereinigten Projekt- und chatbezogenen Fortsetzungszustand zwischen
Computern synchronisieren. Der Skill ist stabil, nachdem zwei unabhängige
Google-Drive-Läufe auf realen Geräten seine deterministische
Stabilitätsfreigabeprüfung bestanden haben.

**Was der Skill tut:**

- speichert unveränderliche Checkpoints in einem genehmigten synchronisierten
  Ordner oder verbundenen Google Drive; die rechnerlokale Konfiguration bleibt
  außerhalb des Repositories;
- verwendet bei nicht näher qualifizierten Synchronisierungsanfragen
  standardmäßig verbundenes Google Drive, bewahrt aber ein vorhandenes Backend
  und verlangt ausdrückliche Zustimmung vor Nutzung eines lokal synchronisierten Ordners;
- findet auf einem neuen Computer anhand des Repository-Fingerabdrucks eine
  verifizierte bestehende Google-Drive-Zuordnung, bevor es einen Remote-Ordner
  erstellt, und blockiert bei unvollständigen Auflistungen, nicht
  vertrauenswürdiger Sichtbarkeit oder doppelten Treffern;
- hält einen opaken Datenstrom pro Projektaufgabe vor: eine detaillierte
  Baseline, gefolgt von kurzen Deltas, genauen sichtbaren Titeln, Entscheidungen,
  Verifikation, offenen Fragen, nächsten Schritten und Git-Fingerabdrücken;
- speichert oder stellt alle aktuellen und angehefteten Projektaufgaben wieder
  her oder plant ihre bidirektionale Synchronisierung, überspringt dabei
  unveränderte/aktive Aufgaben und zeigt Konflikte ausdrücklich auf;
- validiert heruntergeladene Snapshots, liest Uploads zur Prüfung zurück,
  verhindert projektübergreifende Wiederherstellung und weist mit hoher
  Sicherheit erkannte Geheimnismuster zurück;
- erfasst ein separates Umgebungsmanifest für deklarierte Regeln, Skills,
  Plugins und sichere skalare Einstellungen, die Git nicht bereits bereitstellt.

**Was der Skill nicht tut:**

- Quelldateien, Diffs, Rohtranskripte, verborgenes Reasoning, Zugangsdaten,
  OAuth-Token oder Skill-/Plugin-Installationen kopieren;
- Regeln oder Abhängigkeiten duplizieren, die bereits über Git mitgeführt werden;
- Git-verwaltete Zielregeln stillschweigend überschreiben: Die Anwendung darf
  nach einem expliziten Plan nur eine fehlende unversionierte `AGENTS.md` oder
  `CLAUDE.md` für den aktiven Agenten erstellen;
- im Nur-Metadaten-Modus Branch-Namen oder Dateipfade aufnehmen; sichtbare
  Aufgabentitel bleiben absichtlich enthalten.

Codex Desktop unterstützt die dokumentierten Arbeitsabläufe für stapelweise
Aufgabenerkennung, Erstellung, Umbenennung und den Google-Drive-Connector.
Claude Code kann den portablen Kern für Checkpoints, lokale Ordnerspeicherung
und Umgebungsabgleich nutzen; sein Sitzungsspeicher wird jedoch nicht
untersucht, und ausschließlich für Codex bestimmte stapelweise
Aufgabenoperationen werden sicher als nicht unterstützt blockiert.

**Aufruf:**

Konfigurieren Sie jeden Computer einmal:

```text
$sync-project-context Configure this clone in metadata-only mode. Use connected Google Drive by default unless I explicitly request another approved channel.
```

Verwenden Sie danach aufgabenbezogene oder Stapelbefehle, zum Beispiel:

```text
$sync-project-context Save the current task state.
$sync-project-context Restore all project tasks on this computer.
$sync-project-context Synchronize all project tasks bidirectionally and show conflicts before applying changes.
```

Ersetzen Sie in Claude Code das Präfix `$` in diesen Beispielen durch `/`.


### Koordination und Kommunikation

#### `orchestrate-agent-work` (experimentell)

Ausdrücklich autorisierte Subagenten koordinieren und dabei für das integrierte
Ergebnis verantwortlich bleiben.

**Was der Skill tut:**

- teilt parallele Arbeit in abgegrenzte, überschneidungsfreie Aufträge auf;
- überwacht Agentenergebnisse und gleicht sie mit gemeinsamen Vorgaben ab;
- verifiziert das Gesamtergebnis, bevor er den Abschluss meldet.

**Was der Skill nicht tut:**

- delegieren, sofern Benutzer oder Projektanweisungen keine Subagenten autorisieren;
- Genehmigungsbefugnis, Geheimnisse, destruktive Bereinigung oder nicht
  genehmigte externe Änderungen an einen anderen Agenten übertragen;
- unabhängig abgeschlossene Teilaufgaben als Beweis erfolgreicher Integration behandeln.

**Aufruf:**

```text
$orchestrate-agent-work Delegate these independent subtasks to agents and verify the integrated result.
```

#### `synchronize-team-skills` (experimentell)

Die global installierten Agenten-Skills aller Teammitglieder an einem geprüften
Manifest in der Projektdokumentation ausrichten; Projekteinstellungen bleiben lokal.

**Was der Skill tut:**

- erstellt oder liest `team-agent-skills.md` in einer genehmigten Dokumentationswurzel;
- vergleicht deklarierte Codex- und Claude-Code-Skills mit verifizierten globalen Kopien;
- meldet fehlende, veraltete, neuere, unverifizierte, projektspezifisch
  überschriebene und zusätzlich bewahrte Zustände, ohne die Umgebung zu ändern;
- erstellt einen an den Manifest-Digest gebundenen Installationsplan für eine
  festgelegte Sammlungsversion;
- installiert nach Genehmigung nur den geprüften Satz und verifiziert
  anschließend den beobachtbaren Zustand.

**Was der Skill nicht tut:**

- den zufälligen Zustand eines Arbeitsplatzes automatisch zur Teamrichtlinie machen;
- Geheimnisse, Benutzerkonfiguration, Rechnerpfade oder Plugin-Authentifizierung speichern;
- zusätzliche Skills entfernen, neuere Kopien herabstufen oder alte
  Projektkopien ohne bestätigte Zentralisierung löschen;
- behaupten, dass eine laufende Agentenaufgabe neu installierte Skills neu geladen hat.

**Aufruf:**

```text
$synchronize-team-skills Check this project's installed skills against the reviewed team manifest.
$synchronize-team-skills Align my project skills with the team documentation after showing the plan.
$synchronize-team-skills Add maintain-project-digest to the reviewed team skill set.
```

#### `report-skill-feedback` (experimentell)

Erstellt nach ausdrücklicher Zustimmung einen begrenzten, anonymisierten Bericht über eine beobachtete Skill-Nutzung. Der Entwurf enthält weder Code, Chatverläufe, Geheimnisse, Namen, Pfade noch URLs. Er wird vollständig angezeigt und nur nach einer zweiten Zustimmung als dem GitHub-Konto zuordenbares Issue an `kolabse/skills` gesendet.

**Aufruf / Invocation:**

```text
$report-skill-feedback Prepare a de-identified preview about this observed skill use; do not submit it yet.
```

#### `notify-via-telegram`

Statusmeldungen zum Lebenszyklus lang laufender Agentenaufgaben über Telegram senden.

**Was der Skill tut:**

- meldet Start, Meilensteine, Zwischenergebnisse, Probleme, Blockaden und Abschluss;
- validiert den Bot interaktiv und hilft, einen Zielchat zu finden;
- bietet für Codex Desktop unter Windows ein maskiertes, zum Einfügen
  geeignetes Formular für die Erstverwendung;
- speichert Zugangsdaten im Benutzerkonfigurationsverzeichnis und sendet
  während der Einrichtung eine Testbenachrichtigung;
- unterstützt einen separaten Chat oder ein Forumthema pro Projekt mit
  ausdrücklicher Wahl zwischen globaler plus projektbezogener Zustellung
  und ausschließlich projektbezogener Zustellung;
- exportiert geheimnisfreie Projektroutingwerte für den Abgleich über
  `sync-project-context`;
- läuft mit der Python-3-Standardbibliothek auf Windows, macOS und Linux.

**Was der Skill nicht tut:**

- den Bot-Token in die Unterhaltung, den Shell-Verlauf oder das Repository aufnehmen;
- den globalen Bot-Token oder Telegram-Authentifizierungszustand zwischen
  Computern kopieren;
- Benachrichtigungen senden, wenn der Benutzer Fortschrittsmeldungen auf die
  aktuelle Aufgabe beschränken möchte;
- als allgemeines Framework zur Entwicklung von Telegram-Bots dienen.

**Aufruf:**

```text
$notify-via-telegram Configure Telegram notifications for long tasks.
$notify-via-telegram Configure this project to notify its team chat only, instead of the global destination.
```


### Infrastruktur und Betrieb

#### `operate-yandex-cloud`

Explizit konfigurierte, projektbezogene Yandex-Cloud-Infrastruktur betreiben.

**Was der Skill tut:**

- speichert gemeinsame Cloud-/Folder-IDs in der Projektkonfiguration und
  das rechnerbezogene `yc`-Profil in ignorierter lokaler Konfiguration;
- erkennt erforderliche Werkzeuge, prüft Mindestversionen und führt einen
  schreibgeschützten Kontext-Preflight aus;
- unterstützt abgegrenzte Arbeitsabläufe für CLI, SSH, Terraform, Ansible,
  Helm, Kubernetes, Deployment, Datenbanken, Speicher, DNS, Monitoring,
  Sicherungen und Störungsbearbeitung;
- stellt JSON-Ausgabe und plattformübergreifende Python-Hilfsprogramme bereit.

**Was der Skill nicht tut:**

- Yandex Cloud aus allgemeinen SSH-, Kubernetes-, Terraform- oder
  Deployment-Anfragen ohne Anbieterkontext ableiten;
- Zugangsdaten in gemeinsamer Projektkonfiguration speichern;
- eine Änderung vornehmen, bevor Ziel, Kontext und Genehmigung feststehen.

**Aufruf:**

```text
$operate-yandex-cloud Configure this project for Yandex Cloud operations.
```


### Weiterentwicklung der Skill-Sammlung

#### `discover-skill-candidates` (experimentell)

Wiederverwendbare Skill-Ideen in abgegrenzten Projekt- und Kontextnachweisen
finden, ohne einen Skill zu erstellen.

**Was der Skill tut:**

- inventarisiert abgegrenzte projektrelative `AGENTS.md`-Dateien mit Git- und
  zeilengenauer Herkunft;
- inventarisiert optional Projektdokumentation, ausgewählte Dateien,
  begrenzten Git-Verlauf, Strukturmetadaten und vom Benutzer bestätigte
  Zusammenfassungen aus verfügbaren Chats oder `sync-project-context`-Übergaben;
- ordnet Kandidaten als empfohlen, zu untersuchen oder abgelehnt ein und
  vergleicht sie mit bestehenden Katalogen;
- bietet jeden geeigneten Kandidaten proaktiv für einen sicheren Beitrag zu
  `kolabse/skills`, lokale Erstellung oder Zurückstellung an;
- exportiert eine ausgewählte Idee als bereinigtes, Digest-gebundenes
  Beitragspaket, das Maintainer unabhängig validieren können.

**Was der Skill nicht tut:**

- Projektregeln ändern oder einen Skill anlegen, veröffentlichen oder installieren;
- Chats aufzählen, Rohtranskripte einlesen oder Quellcode breit durchsuchen;
- rohe Regeln, lokale Pfade, Geheimnisse, URLs oder E-Mail-Adressen exportieren;
- reine Richtlinien, kurzlebige, sensible oder einmalige Konventionen ohne
  Prüfung als wiederverwendbare Arbeitsabläufe empfehlen.

**Aufruf:**

```text
$discover-skill-candidates Analyze this project's local rules and prepare an evidence-backed backlog of reusable skill ideas without creating anything.
```

#### `release-skill-collection`

Deterministische Releases einer Skill-Sammlung planen, verifizieren, auditieren
und bereinigen.

**Was der Skill tut:**

- prüft Versionen, Changelog-Bereitschaft, Repository-Zustand, Tests,
  Sicherheit, deterministische Archive und Prüfsummen;
- validiert Commit-gebundene Nachweise für Holdout, Nutzerinstallation,
  Plattformen, Review und lokale Prüfungen;
- auditiert unveränderliche GitHub-Artefakte, Manifeste, Prüfsummen und Attestierungen;
- weist vor der Bereinigung nach, ob temporäre Branches gemergt, baumidentisch
  oder patchäquivalent sind;
- führt eine ausdrücklich bestätigte Bereinigung nur auf Grundlage eines
  unveränderten sicheren Plans und eines Digest-gültigen Audits des
  veröffentlichten Releases durch.

**Was der Skill nicht tut:**

- Erlaubnis zum Committen, Taggen, Pushen, Starten von Workflows oder
  Veröffentlichen von Artefakten ableiten;
- einen vorhandenen Tag verschieben oder veröffentlichte Artefakte ersetzen;
- Branches allein anhand von Namen, eines veralteten Plans oder eines nicht
  auditierten Releases löschen.

**Aufruf:**

```text
$release-skill-collection Plan and verify release vX.Y.Z of this skill collection, but do not publish it yet.
```

## Unterstützte Kombinationen

Der Katalog definiert drei wiederverwendbare geordnete Arbeitsabläufe:

- `protected-push`: Repositories synchronisieren, dann aktuelle
  Verifikationsnachweise erzeugen; Arbeitsprotokollierung und
  Telegram-Benachrichtigung sind optional.
- `yandex-cloud-operation`: Repositories synchronisieren, dann die abgegrenzte
  Cloud-Operation ausführen; Verifikation, Arbeitsprotokollierung und
  Telegram-Benachrichtigung sind optional, wenn die Projektrichtlinie sie aktiviert.
- `skill-collection-release`: Repository synchronisieren, Sammlungsrelease
  planen und lokal verifizieren, dann Pre-Push-Nachweise binden;
  Arbeitsprotokollierung und Telegram-Benachrichtigung sind optional.

Erforderliche Schritte blockieren bei Fehlern oder Unsicherheit sicher.
Optionale Protokollierung und Benachrichtigung melden ihren eigenen Fehlschlag,
ohne das beobachtete Ergebnis der primären Operation zu ändern. Ermitteln Sie
einen genauen Plan mit `scripts/compose_skills.py`; übergeben Sie `--evidence`
mit einem Digest-gebundenen Dokument gemäß
`schemas/composition-evidence.schema.json`, um Schrittreihenfolge, erforderliche
Ergebnisse und nicht blockierende optionale Fehler zu verifizieren. Das
verifizierte Ergebnis folgt `schemas/composition-result.schema.json`.

## Einen Skill hinzufügen

Folgen Sie [CONTRIBUTING.md](CONTRIBUTING.md) und beginnen Sie mit
[`templates/skill-template.md`](../../../templates/skill-template.md). Jeder
Skill muss einen passenden Eintrag in `skill-catalog.json` haben, der
Verantwortliche, Plattformen, Status, Lizenz und Herkunft erfasst. Halten Sie
projektspezifische Konfiguration außerhalb des installierten Skill-Ordners,
damit Updates sie nicht überschreiben können.

Fügen Sie keinen Installer auf Repository-Ebene für einen einzelnen Skill
hinzu. Wenn die Sammlung verwaltete Installation und Updates über ChatGPT und
Codex hinweg benötigt, paketieren Sie sie zusätzlich zu dieser
agentenübergreifenden Struktur als OpenAI-Plugin.

Führen Sie die Prüfungen der Sammlung lokal aus:

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py
```

Bereiten Sie eine Blind-Trigger-Suite für einen Agenten- oder Modellselektor vor:

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
```

Die Suite enthält nur Skill-Namen, öffentliche Beschreibungen, opake Fall-IDs
und Prompts. Erwartete Labels und Autorenbegründungen werden ausgelassen.
Ein Selektor liefert striktes JSON mit allen ausgewählten Skills je Fall;
bewerten Sie die Beobachtungen mit:

```shell
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

Verwenden Sie `run` mit einem Befehl nach `--`, um einen Selektor aufzurufen,
der die Suite von der Standardeingabe liest und Vorhersagen auf die
Standardausgabe schreibt. Halten Sie Anbieterzugangsdaten außerhalb von
Befehlsargumenten. Das ignorierte Verzeichnis `.trigger-evals/` hält generierte
Suites, Vorhersagen und Berichte standardmäßig aus Commits heraus. Große
Entwicklungssuites werden standardmäßig in Digest-gebundenen Paketen von 64
Fällen gesendet, damit lange strikte JSON-Antworten keine opaken Fall-IDs
abschneiden. Passen Sie das Limit mit `--batch-size` an, ohne dem Selektor
erwartete Labels offenzulegen.

Führen Sie vor einem Release den separat versionierten und per Digest fixierten
Holdout aus, ohne ihn während der Entwicklung zur Optimierung von
Beschreibungen zu verwenden:

```shell
python scripts/trigger_evals.py prepare \
  --corpus release-holdout \
  --output .trigger-evals/release-holdout.json
```

Vergleichen Sie einen Kandidatenbericht mit einem Bericht derselben Holdout-Version:

```shell
python scripts/trigger_evals.py compare \
  --candidate .trigger-evals/candidate-report.json \
  --markdown-output .trigger-evals/comparison.md
```

Der Vergleich blockiert sicher, wenn Assertion-Digests abweichen oder
Gesamtgenauigkeit, Präzision, Trefferquote oder eine skillbezogene Metrik über
die konfigurierten Grenzen hinaus sinken. Standardmäßig verwendet er die in
`skill-catalog.json` benannte veröffentlichte Baseline; geben Sie `--baseline`
nur an, wenn Sie bewusst mit einem anderen kompatiblen Bericht vergleichen.

Sammeln Sie für nicht deterministische Modellselektoren eine ungerade Anzahl
von mindestens drei blinden Vorhersageläufen und bewerten Sie ihre
Mehrheitsentscheidung:

```shell
python scripts/trigger_evals.py aggregate \
  --corpus release-holdout \
  --predictions run-1.json run-2.json run-3.json \
  --predictions-output .trigger-evals/aggregate.json \
  --json-output .trigger-evals/candidate-report.json
```

## Ein Release verifizieren

Versionierte Releases enthalten deterministische ZIP- und TAR.GZ-Archive,
`release-manifest.json` und `SHA256SUMS`. Laden Sie alle vier Artefakte in ein
Verzeichnis herunter und verifizieren Sie sie mit:

```shell
python scripts/build_release.py --verify <download-directory>/SHA256SUMS
```

GitHub stellt außerdem für jedes hochgeladene Release-Artefakt einen
SHA-256-`digest` bereit. Release-Workflows veröffentlichen zusätzlich
GitHub-Artefaktattestierungen. Verifizieren Sie ein heruntergeladenes Artefakt
gegen dieses Repository mit:

```shell
gh attestation verify <artifact> --repo kolabse/skills
```
