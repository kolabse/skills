# Skills beitragen

[English](../../../CONTRIBUTING.md) | [Русский](../ru/CONTRIBUTING.md) | [Español](../es/CONTRIBUTING.md) | [Français](../fr/CONTRIBUTING.md) | Deutsch | [Português (Brasil)](../pt-BR/CONTRIBUTING.md) | [日本語](../ja/CONTRIBUTING.md) | [Italiano](../it/CONTRIBUTING.md) | [한국어](../ko/CONTRIBUTING.md) | [简体中文](../zh-CN/CONTRIBUTING.md) | [Türkçe](../tr/CONTRIBUTING.md)

Diese Übersetzung dient der Orientierung. Maßgeblich ist die [englische Originalfassung](../../../CONTRIBUTING.md).

Dieses Repository ist die maßgebliche Heimat wiederverwendbarer kolabse-Skills.
Jeder Skill sollte klar abgegrenzt, portabel, seiner Quelle zuordenbar und
unabhängig installierbar bleiben.

## Vor dem Hinzufügen eines Skills

1. Bestimmen Sie die maßgebliche Quelle. Entscheiden Sie, ob dieses Repository
   für den Skill verantwortlich sein oder eine andere Quelle spiegeln soll.
2. Klären Sie das Recht zur Weitergabe aller kopierten Anweisungen, Skripte,
   Referenzen und Ressourcen. Eigene Beiträge werden unter der Apache-2.0-Lizenz
   des Repositories angenommen, sofern sie nicht ausdrücklich anders
   gekennzeichnet sind. Bewahren Sie Lizenzdateien Dritter, Copyright-Vermerke,
   Quellenangaben und Änderungshinweise; erfassen Sie ihren SPDX-Ausdruck im
   Katalog. Veröffentlichen Sie kein Drittmaterial mit ungeklärter Lizenz.
3. Suchen Sie in vorhandenen Beschreibungen nach überlappenden Auslösern.
   Erweitern Sie einen bestehenden Skill, wenn der Arbeitsablauf denselben Zweck
   erfüllt; fügen Sie einen neuen hinzu, wenn er einen eigenständig nützlichen
   Auslöser und ein eigenes Abschlusskriterium hat.
4. Wählen Sie einen kleingeschriebenen, mit einem Verb beginnenden und durch
   Bindestriche gegliederten Namen mit höchstens 63 Zeichen.

Abschlusskriterium: Verantwortlichkeit, Herkunft, Lizenz, Umfang und Skill-Name
sind bekannt, bevor Dateien kopiert werden.

## Einen Kandidaten bis zur Umsetzung verfolgen

Wenn ein neuer oder erweiterter Skill aus einem GitHub Issue hervorgeht, bleibt
dieses Issue die maßgebliche Arbeitseinheit, bis die Umsetzung im primären Branch
enthalten ist.

1. Vermerken Sie das ursprüngliche Issue im Pull Request zur Umsetzung.
2. Fügen Sie `Closes #<issue-number>` in den Text des Pull Requests ein. Wenn die
   Änderung das Issue nicht schließen soll, nennen Sie ausdrücklich den Grund
   und den vorgesehenen weiteren Umgang damit.
3. Prüfen Sie das Issue nach dem Merge, statt anzunehmen, dass das Schlüsselwort
   zum Schließen angewendet wurde. Falls es unerwartet offen bleibt, schließen
   Sie es als abgeschlossen mit Links zum umsetzenden Pull Request und, sofern
   vorhanden, zum Release.
4. Falls die Umsetzung abgelehnt, ersetzt oder nur teilweise geliefert wird,
   hinterlassen Sie einen erläuternden Kommentar und verwenden Sie den
   entsprechenden Issue-Abschlussstatus; melden Sie einen Kandidaten niemals
   allein deshalb als abgeschlossen, weil ein Branch oder Pull Request existierte.

Abschlusskriterium: Jeder umgesetzte Kandidat lässt sich vom ursprünglichen
Issue zum gemergten Pull Request zurückverfolgen; das Issue hat einen geprüften
Endzustand mit einer Erklärung der Umsetzung oder des Nichtabschlusses.

## Den Skill hinzufügen oder migrieren

1. Synchronisieren Sie Quell- und Zielrepository, ohne lokale Arbeit zu überschreiben.
2. Erstellen Sie `skills/<skill-name>/SKILL.md`. Behalten Sie im YAML-Frontmatter
   nur `name` und `description` bei; der Ordnername muss mit `name` übereinstimmen.
3. Legen Sie deterministische Hilfsprogramme in `scripts/`, Details für Agenten
   in `references/`, Ausgabematerial in `assets/` und optionale UI-Metadaten in
   `agents/openai.yaml` ab. Projektkonfiguration bleibt außerhalb des Skill-Ordners.
4. Schreiben Sie Schritte im Imperativ mit überprüfbaren Abschlusskriterien.
   Der Haupttext muss unter 500 Zeilen bleiben; stellen Sie verzweigungsspezifische
   Details über direkte Verweise bereit.
5. Fügen Sie einen Eintrag in `skill-catalog.json` hinzu:
   - `name` und den repositoryrelativen `path`;
   - genau eine primäre `category` nach der dokumentierten Prioritätsreihenfolge;
   - mindestens einen kontrollierten `tags`-Wert für Lebenszyklusphase, Umfang,
     Verhalten und Integrationen;
   - `status`: `experimental`, `stable` oder `deprecated`;
   - GitHub-Benutzernamen in `maintainers`;
   - unterstützte `platforms`;
   - SPDX-Ausdruck in `license`;
   - Herkunftsart, Quelle, frühere Namen und maßgebliches Repository.
   Validieren Sie Kategorie- und Tag-Werte gegen
   `schemas/skill-catalog.schema.json`; der Reifegrad ist von beiden unabhängig.
6. Fügen Sie den Skill dem README-Katalog hinzu, einschließlich Zweck,
   Installationshinweisen und erforderlicher Aktion beim ersten Aufruf.
7. Ergänzen Sie Tests für deterministische Skripte und realistische Prompts,
   die den Skill auslösen beziehungsweise nicht auslösen sollten. Speichern
   Sie mindestens drei positive und drei benachbarte negative Fälle in
   `evals/<skill-name>.json` und referenzieren Sie diese Datei in
   `skill-catalog.json` als `trigger_evals`.

Bewahren Sie bei einem migrierten Skill dessen Geschichte im Katalog, auch
nachdem dieses Repository maßgeblich geworden ist. Erfassen Sie bei einem
übernommenen Drittanbieter-Skill eine unveränderliche Quellrevision, behalten
Sie Lizenz und Hinweise im Skill-Ordner und trennen Sie Upstream-Änderungen von
lokalen Patches. Bestätigen Sie die Lizenzkompatibilität, bevor Sie Drittinhalte
mit Apache-2.0-Inhalten kombinieren.

Abschlusskriterium: Leser können feststellen, woher der Skill stammt, wer dafür
verantwortlich ist, wie er lizenziert ist, wo er läuft und wie er validiert wird.

## Konfigurationsvertrag

Jeder konfigurierbare Skill deklariert ein `configuration`-Objekt in
`skill-catalog.json` und folgt diesen Regeln:

- `configure` ist ein argv-Array, lässt sich sicher wiederholen, bewahrt
  unabhängige Projektinhalte und meldet bei einem identischen zweiten Durchlauf
  keine Änderung;
- `status` ist schreibgeschützt, unterstützt maschinenlesbares JSON, beendet
  sich nur dann mit null, wenn die deklarierte Konfiguration vorhanden und
  gültig ist, und gibt niemals Geheimnisse aus;
- Projekt- und Benutzerumfang sind ausdrücklich festgelegt; die Konfiguration
  bleibt außerhalb des installierten Skill-Verzeichnisses;
- JSON- und YAML-Konfiguration enthält eine positive ganzzahlige Version, ein
  mitgeliefertes JSON Schema für das dekodierte Dokument und einen
  Migrationsbefehl, der bei Unsicherheit sicher blockiert;
- verwalteter Text verwendet gepaarte, skillspezifische Markierungen, weist
  fehlerhafte oder doppelte Markierungen zurück und schreibt keinen Text
  außerhalb seines Blocks um.
- Zustandslose Skills verwenden das Format `none`, stellen nur einen
  schreibgeschützten Statusbefehl bereit und dürfen keine Platzhalter für
  Konfigurationsartefakte erfinden.

Befehle werden als Arrays statt als Shell-Zeichenfolgen gespeichert. Verwenden
Sie Platzhalter wie `<project-root>` für vom Aufrufer gelieferte Werte und
nehmen Sie niemals Zugangsdaten in einen Katalogbefehl auf. Migrationsschritte
müssen inkrementell und idempotent bleiben; weisen Sie eine unbekannte neuere
Version zurück, statt zu raten, wie sie herabgestuft werden kann.

Abschlusskriterium: Wiederholtes Konfigurieren erzeugt dort, wo die Konfiguration
existiert, byteidentische Ausgabe; Statusabfragen schreiben nichts, Migrationen
bewahren unterstützte Eingaben, und Tests decken fehlende, fehlerhafte, aktuelle
und ältere Konfiguration ab.

## Den Aktualisierungspfad für Nutzer bewahren

- Halten Sie die Versionen in `.codex-plugin/plugin.json`,
  `.claude-plugin/plugin.json`, `skill-catalog.json.collection_version` und
  allen `skills/*/collection-metadata.json` innerhalb eines Releases identisch.
- Testen Sie eine kopierte Installation und ein Update von der ältesten
  unterstützten Vorgängerversion über die festgelegte `skills`-CLI sowohl für
  `codex` als auch für `claude-code`.
- Halten Sie Projekt-/Benutzerkonfiguration außerhalb installierter Skill-Ordner.
  Ein Updater darf niemals stillschweigend Konfiguration für einen ungenutzten
  Skill erstellen.
- Dokumentieren Sie erforderliche Migrationen und Rollback-Einschränkungen in
  README und Changelog. Konfigurations-Downgrades gelten ohne Tests als nicht unterstützt.
- Bewahren Sie unabhängige Einträge bei Änderungen am persönlichen Marketplace.
  Wenden Sie ein Cachebuster-Suffix auf die installierte Plugin-Kopie an und
  verlangen Sie nach der Aktivierung eine neue Codex-Aufgabe.

Abschlusskriterium: Nutzer können installierte Versionen ermitteln, aktualisieren,
vorhandene Konfiguration migrieren, gemischte Versionen diagnostizieren und einen
früheren Tag neu installieren, ohne repositoryinternes Wissen zu benötigen.

## Agentenübergreifendes Verhalten bewahren

Halten Sie gemeinsame `SKILL.md`-Anweisungen und Hilfsprogramme portabel. Codex
bleibt der Standard für bestehende Befehlszeilenschnittstellen; ein ausdrücklich
gewähltes Claude-Code-Ziel verwendet `.claude/skills`, `CLAUDE.md` und
`/skill-name`. Ersetzen Sie bestehende `.agents`-Konfigurations-APIs nicht nur,
um sie für einen anderen Zielagenten umzubenennen.

Behandeln Sie `agents/openai.yaml` als OpenAI-UI-Metadaten und `.codex-plugin`
als Codex-Paketformat. Das Claude-Paketformat gehört unter `.claude-plugin`;
keines der Manifeste darf stillschweigend die Validierung des anderen ersetzen.
Wenn einem Agenten eine Fähigkeit wie das Auflisten von Aufgaben in Codex
Desktop fehlt, melden Sie diese begrenzte Operation als nicht unterstützt,
während die portable Teilmenge erhalten bleibt.

Abschlusskriterium: Beide Installationen enthalten identische Skill-Nutzdaten,
die jeweiligen Projektregel- und Skill-Verzeichnisstrukturen werden respektiert,
Codex-Standards bleiben unverändert und Consumer-Smoke-Nachweise benennen
beide Agenten ausdrücklich.

## Skills nach Fähigkeiten kombinieren

Deklarieren Sie kleine Fähigkeitsnamen in `provides`, zwingende Voraussetzungen
in `requires` und nicht blockierende Integrationen in `optional_integrations`.
Ergänzen Sie eine benannte Kombination der Sammlung nur für einen wiederkehrenden
Arbeitsablauf mit mindestens zwei Skills. Ihre `required_steps` sind geordnet;
`optional_steps` laufen nur, wenn das Projekt oder der Benutzer deren Fähigkeit
aktiviert hat.

Kopieren Sie nicht den Arbeitsablauf eines Skills in einen anderen. Rufen Sie
den vorausgesetzten Skill auf, verwenden Sie dessen beobachtbares
Abschlussergebnis und stoppen Sie, wenn eine erforderliche Fähigkeit fehlt.
Optionale Benachrichtigung oder Protokollierung darf niemals einen falschen
Erfolg der primären Operation erzeugen oder deren Fehlschlag verbergen.

Abschlusskriterium: Für jede erforderliche Fähigkeit gibt es einen Anbieter,
die Kombinationsschritte referenzieren bestehende Skills jeweils einmal, und
die Reihenfolge hat einen Integrationstest oder ein ausführbares Abschlusskriterium.

## Lebenszyklusstatus verwalten

- Belassen Sie einen neuen oder wesentlich überarbeiteten Skill auf
  `experimental`, bis Metadaten, deterministische Hilfsprogramme,
  plattformübergreifende Tests, der Entwicklungs-Trigger-Korpus, ein
  unabhängiger Forward-Test, ein Smoke-Test der kopierten Installation und der
  Release-Holdout erfolgreich geprüft wurden. Nicht zutreffende Anforderungen,
  etwa mitgelieferte Skripte für einen rein textlichen Arbeitsablauf, können
  als nicht anwendbar vermerkt werden.
- Markieren Sie einen Skill nur in einem versionierten Sammlungsrelease als
  `stable`. Ergänzen Sie `stable_since` mit dieser Release-Version. Stabil
  bedeutet, dass dokumentierte Eingaben, Konfigurationsorte, Sicherheitsgrenzen
  und CLI-Verhalten innerhalb der aktuellen Hauptversion kompatibel bleiben
  oder Migrationshinweise erhalten.
- Markieren Sie einen Skill vor seiner Entfernung als `deprecated`. Nennen
  Sie den unterstützten Ersatz oder Migrationspfad im Skill und im Changelog
  und behalten Sie ihn mindestens ein Minor-Release bei, sofern kein dringendes
  Sicherheitsproblem eine frühere Entfernung erfordert.

Abschlusskriterium: Der Lebenszyklusstatus ist durch beobachtbare Validierung
belegt und vermittelt eine klare Kompatibilitätserwartung.

## Herkunft installierter Skills bewahren

Behandeln Sie einen bekannten Skill-Namen nur als Kandidaten, niemals als
Identitätsnachweis der Sammlung. Gleichen Sie die externe Lock-Quelle mit der
installierten `collection-metadata.json` ab. Normalisieren Sie unterstützte
GitHub-Schreibweisen zu `https://github.com/kolabse/skills`; überprüfen Sie
lokale Entwicklungsquellen anhand ihres Plugin-Manifests, Katalogs und des
angeforderten Skill-Inhalts, unabhängig vom Namen des Checkout-Verzeichnisses.

Blockieren Sie sicher bei gleichnamigen Skills aus einer anderen Quelle oder
widersprüchlichen Metadaten. Die Übernahme älterer Installationen muss explizit
bleiben und ist nur erlaubt, wenn die Lock-Quelle selbst verifiziert ist;
eine erfolgreiche Übernahme muss mit aktuellen Metadaten und einer fehlerfreien
Diagnose nach dem Update enden.

Abschlusskriterium: Der Status zeigt die Herkunftsklassifikation; Updates wählen
nur verifizierte Skills oder ausdrücklich übernommene ältere Skills aus; Tests
decken Quellkollisionen, Release-Refs, umbenannte lokale Checkouts und ältere
Installationen ab.

## Automatisierung für Nutzer überprüfbar halten

Halten Sie `plan` schreibgeschützt: Es darf keine Installer, Migrationen oder
Netzwerkoperationen aufrufen. Veröffentlichen Sie versionierte JSON Schemas für
Plan- und Ergebnisdaten und unterscheiden Sie unveränderte, aktualisierte,
migrierte, übersprungene, blockierte und fehlgeschlagene Zustände, ohne
menschenlesbare CLI-Ausgaben zu parsen.

Begrenzen Sie die globale Erkennung auf dokumentierte Lock- und
Installationsverzeichnisse. Durchsuchen Sie nicht das Home-Verzeichnis nach
möglichen Installationen. Wenden Sie dieselben Regeln für Herkunft, explizite
Auswahl und Diagnose nach dem Update auch global an.

Der eigenständige Bootstrap muss die Archivprüfsumme vor dem Entpacken und die
GitHub-Build-Herkunft vor der Ausführung verifizieren, Pfadtraversierung und
Symlink-Archiveinträge zurückweisen, ein temporäres Verzeichnis verwenden und
den Exit-Code des Managers weitergeben. Offline-Ausführung ohne Attestierung
muss eine ausdrückliche Option für den eingeschränkten Modus erfordern.

Abschlusskriterium: Schemas lassen sich parsen, Dry-Runs hinterlassen
byteidentische Testdaten, globale Testdaten decken unterstützte und mehrdeutige
Strukturen ab, und der Bootstrap-Smoke-Test besteht auf jedem unterstützten
CI-Betriebssystem.

## Die Änderung validieren

Führen Sie aus:

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py --agent codex
python scripts/smoke_install.py --agent claude-code
```

Prüfen Sie den Trigger-Korpus mit einem tatsächlichen Agenten, einschließlich
des Erstaufrufpfads des Skills. Strukturelle CI-Prüfungen halten den Korpus
vollständig, ersetzen aber nicht die Beobachtung der Modellaufrufe. Nehmen Sie
die Prompts und das beobachtete Ergebnis in den Pull Request auf.

Bereiten Sie für die sammlungsweite Trigger-Evaluation eine Blindtestsuite vor
und bewerten Sie die Beobachtungen des Selektors:

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

Selektoren dürfen mehrere Skills oder keinen auswählen. Geben Sie dem Selektor
weder Quell-Evaluationsdateien noch erwartete Labels, Begründungen der Autoren,
vermutete Fehler oder frühere Berichte. Erfassen Sie Anbieter und Modell in den
Vorhersagemetadaten, bewahren Sie Rohvorhersagen mit den Review-Nachweisen auf
und untersuchen Sie jedes falsch positive und falsch negative Ergebnis, bevor
Sie eine Beschreibung ändern. Ein höherer Wert allein rechtfertigt keine
Erweiterung eines Auslösers, wenn benachbarte Arbeitsabläufe dadurch mehrdeutig werden.

Behandeln Sie `evals/release-holdout-vN.json` als ausschließlich ergänzbaren
Release-Nachweis. Lesen oder verwenden Sie den aktiven Holdout nicht während
der Optimierung von Beschreibungen. Vorhandene Holdout-Versionen sind
unveränderlich: Erstellen Sie `vN+1`, aktualisieren Sie Katalognamen, Pfad und
maßgeblichen Digest und bewahren Sie jede veröffentlichte Version. Führen Sie
den aktiven Holdout erst aus, wenn die Kandidatenbeschreibungen eingefroren
sind, und vergleichen Sie seinen Bericht mit einer Baseline aus derselben
Holdout-Version und Selektorkonfiguration. Vergleichen Sie niemals Berichte mit
unterschiedlichen Assertion-Digests. Bewahren Sie nach dem Release den
akzeptierten Bericht unter `evals/baselines/` auf und aktualisieren Sie den
Baseline-Verweis im Katalog; Baseline-Dateien sind Release-Nachweise und dürfen
nicht umgeschrieben werden. Ist der Selektor nicht deterministisch, verwenden
Sie eine ungerade Anzahl von mindestens drei unabhängigen Blindläufen und
vergleichen Sie das Mehrheitsaggregat. Wiederholen Sie keine Einzelbeobachtung
so lange, bis sie besteht, und verwerfen Sie keine gültigen Fehlbeobachtungen.

Abschlusskriterium: Jeder Befehl besteht auf jedem unterstützten Betriebssystem,
und die Pull-Request-Checkliste enthält Nachweise für den betroffenen Skill.

## Die Release-Kette schützen

- Binden Sie jede externe GitHub Action an einen vollständigen Commit-SHA und
  bewahren Sie ihre Release-Version in einem Kommentar. Lassen Sie Dependabot
  SHA-Aktualisierungen zur Prüfung vorschlagen.
- Gewähren Sie jedem Workflow nur die benötigten `GITHUB_TOKEN`-Berechtigungen.
- Erstellen Sie Release-Archive mit `scripts/build_release.py`; verifizieren
  Sie `SHA256SUMS`, bevor Sie Artefakte hochladen.
- Veröffentlichen Sie GitHub-Artefaktattestierungen für jedes Release-Artefakt
  und prüfen Sie sie mit `gh attestation verify <artifact> --repo kolabse/skills`.
- Ersetzen Sie niemals ein vorhandenes Release-Artefakt. Ein wiederholter
  Workflow-Lauf muss nachweisen, dass die veröffentlichten Bytes identisch
  sind, oder fehlschlagen.
- Halten Sie Versions-Tags unveränderlich. Veröffentlichen Sie eine Korrektur
  als neue Version, statt einen bestehenden Tag zu verschieben oder seinen
  Quellcommit zu ersetzen.

Abschlusskriterium: Der Tag verweist auf den geprüften Commit, die hochgeladenen
Artefakte stimmen mit `SHA256SUMS` überein, und Workflow-Abhängigkeiten sind
unveränderliche Referenzen.
