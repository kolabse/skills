# kolabse/umiejętności

[English](../../../README.md) | [Русский](../ru/README.md) | [Español](../es/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Português (Brasil)](../pt-BR/README.md) | [日本語](../ja/README.md) | [Italiano](../it/README.md) | [한국어](../ko/README.md) | [简体中文](../zh-CN/README.md) | [Türkçe](../tr/README.md) | Polski | [Українська](../uk/README.md)

> To jest tłumaczenie dla ułatwienia czytania. Kanoniczne i najbardziej istotne jest
> [Wersja angielska](../../../README.md).

Umiejętności agenta wielokrotnego użytku, a następnie kolabse.

Licencja - [Licencja Apache 2.0](../../../LICENSE). Prawa autorskie 2026 kolabse.

## Spis treści

- [Instalowanie umiejętności](#instalowanie-umiejętności)
  - [Instalacja z rynków Git](#instalacja-z-rynków-git)
- [Aktualizacja zainstalowanych umiejętności](#aktualizowanie-zainstalowanych-umiejętności)
  - [Rozpocznij bez klonowania repozytorium](#uruchom-bez-klonowania-repozytorium)
  - [Sprawdzanie ustawień globalnych](#sprawdzanie-ustawień-globalnych)
- [Instalowanie lub aktualizacja lokalnej wtyczki Codexu w celu programowania](#zainstaluj-lub-zaktualizuj-lokalną-wtyczkę-codexu-na-potrzeby-programowania)
- [Dostępne umiejętności](#dostępne-umiejętności)
  - [Rozwój i jakość kodu](#rozwój-i-jakość-kodu)
    - [`develop-with-test-first-evidence`](#develop-with-test-first-evidence-eksperymentalny)
    - [`review-code-changes`](#review-code-changes-eksperymentalny)
    - [`diagnose-software-defects`](#diagnose-software-defects-eksperymentalny)
    - [`resolve-git-conflicts`](#resolve-git-conflicts-eksperymentalny)
  - [Repozytoria i dostarczanie zmian](#repozytoria-i-dostarczanie-zmian)
    - [`synchronize-git-repositories`](#synchronize-git-repositories)
    - [`verify-before-push`](#verify-before-push)
    - [`coordinate-code-documentation-repositories`](#coordinate-code-documentation-repositories-eksperymentalny)
    - [`execute-configured-gitflow-releases`](#execute-configured-gitflow-releases-eksperymentalny)
    - [`execute-verified-development-lifecycle`](#execute-verified-development-lifecycle-eksperymentalny)
  - [Wiedza o projekcie i ciągłość](#ciągłość-wiedzy-i-projektu)
    - [`maintain-work-log`](#maintain-work-log)
    - [`maintain-project-digest`](#maintain-project-digest-eksperymentalny)
    - [`sync-project-context`](#sync-project-context)
  - [Koordynacja i komunikacja](#koordynacja-i-komunikacja)
    - [`orchestrate-agent-work`](#orchestrate-agent-work-eksperymentalny)
    - [`synchronize-team-skills`](#synchronize-team-skills-eksperymentalny)
    - [`report-skill-feedback`](#report-skill-feedback-eksperymentalny)
    - [`notify-via-telegram`](#notify-via-telegram)
  - [Infrastruktura i operacje](#infrastruktura-i-operacje)
    - [`operate-yandex-cloud`](#operate-yandex-cloud)
  - [Rozwój gromadzenia umiejętności](#rozwój-zbioru-umiejętności)
    - [`discover-skill-candidates`](#discover-skill-candidates-eksperymentalny)
    - [`release-skill-collection`](#release-skill-collection)
- [Obsługiwane kompozycje](#obsługiwane-kompozycje)
- [Dodawanie umiejętności](#dodawanie-umiejętności)
- [Weryfikacja wydania](#weryfikacja-wydania)

## Instalowanie umiejętności

Zainstaluj jedną lub więcej umiejętności globalnie dla bieżącego użytkownika za pośrednictwem
wspólne dla agentów CLI [`skills`](https://skills.sh):

```shell
npx skills@latest add kolabse/skills --global
```

CLI znajduje foldery w `skills/`, prosi o wybranie umiejętności i kopiuje je do wybranych
agentów programistycznych. To jest instalator zewnętrzny; repozytorium nie publikuje i nie publikuje
uruchamia własny pakiet npm.

Użytkownicy Kodeksu mogą również poprosić `$skill-installer` o zainstalowanie umiejętności
to repozytorium, na przykład:

```text
https://github.com/kolabse/skills/tree/main/skills/operate-yandex-cloud
```

W przypadku instalacji nieinteraktywnej określ konsumenta:

```shell
npx skills@1.5.22 add kolabse/skills --agent codex --copy --global -y
npx skills@1.5.22 add kolabse/skills --agent claude-code --copy --global -y
```

Zapytaj agenta: „Ustaw wybrane umiejętności globalnie i tylko dodaj
brakujących ustawień dla tego projektu bez zastąpienia istniejących reguł.”
Po uruchomieniu zewnętrznego instalatora skorzystaj z globalnej ścieżki umiejętności:

```shell
python ~/.agents/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent codex --apply --yes --json
python ~/.claude/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent claude-code --apply --yes --json
```

Jeśli nie ma jeszcze umów, prefiksy `feature/`, `bugfix/`, `release/`,
`hotfix/` i typy zatwierdzeń `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
Jawne przedrostki, role gałęzi i formaty zatwierdzeń zachowują priorytet.
Stałe gałęzie i haki Git nie są tworzone. Zarządzana aktualizacja globalna
wykonuje ten sam bootstrap dla jawnie wybranego aktywnego projektu; bez
potwierdzenia to tylko plan.

Natychmiast utwórz umowę dotyczącą cyklu życia projektu, jeśli zaobserwowane naruszenia są wystarczające
(użyj ścieżki agenta):

```shell
python ~/.agents/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent codex --apply --yes --json
python ~/.claude/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent claude-code --apply --yes --json
```

Instalacja globalnego rynku/wtyczki nie zna aktywnego katalogu głównego projektu, więc
ten sam bootstrap jest wykonywany przy pierwszym użyciu umiejętności w projekcie.

Obsługiwane ścieżki globalne: `~/.agents/skills/` dla Codex i
`~/.claude/skills/` dla kodu Claude'a. Projekty spoza tych folderów ładunku są przechowywane
tylko konfiguracja, kierowanie regułami i zamierzone ustawienia projektu.

Repozytorium jest również spakowane jako wtyczka oparta wyłącznie na umiejętnościach
`kolabse-skills` dla ChatGPT/Codex i Claude Code. Zawiera wszystkie foldery z
`skills/`. Instalacja poprzez `npx skills` pozostaje niezależna od wtyczek.

### Instalacja z rynków Git

W przypadku Codexu zarejestruj platformę handlową i zainstaluj kolekcję:

```shell
codex plugin marketplace add kolabse/skills --ref main
codex plugin add kolabse-skills@kolabse
```

Zaktualizuj migawkę Git i zainstaluj ponownie bieżącą wersję:

```shell
codex plugin marketplace upgrade kolabse
codex plugin add kolabse-skills@kolabse
```

Dla Claude'a Code:

```shell
claude plugin marketplace add kolabse/skills
claude plugin install kolabse-skills@kolabse
```

Zaktualizuj go za pomocą polecenia `claude plugin marketplace update kolabse` lub włącz
automatyczna aktualizacja na rynku. Po instalacji lub aktualizacji rozpocznij nową sesję
agenta w celu odkrycia odpowiednich umiejętności.

Katalogi znajdują się w
[`.agents/plugins/marketplace.json`](../../../.agents/plugins/marketplace.json)
i [`.claude-plugin/marketplace.json`](../../../.claude-plugin/marketplace.json),
ładowność jest opisana w
[`.codex-plugin/plugin.json`](../../../.codex-plugin/plugin.json) i
[`.claude-plugin/plugin.json`](../../../.claude-plugin/plugin.json). Obydwa
katalog, kanoniczny `kolabse/skills` uzyskano z `main`; określono wersję wydania
manifestuj wtyczki.

Materiały umieszczane w miejscach publicznych przechowywane są wraz ze źródłami: [wsparcie](SUPPORT.md),
[polityka prywatności](PRIVACY.md), [warunki](TERMS.md) i możliwe do powielenia
[pakiet przesyłania na rynek](../../marketplace-submissions/). Publikacja w
katalog urzędowy wymaga przeglądu przez osobę towarzyszącą; Rynek Git – nie.

Podczas testowania Claude Code może pobrać wersję rozpakowaną lub zaufaną
płatność poprzez `claude --plugin-dir <collection-root>`. Do normalnego użytku
wolisz rynek Git lub `npx skills ... --agent claude-code`.
Claude Code czyta `CLAUDE.md`, a nie `AGENTS.md`; jeśli zasady już obowiązują
`AGENTS.md`, minimum `CLAUDE.md` z `@AGENTS.md` utrzymuje jedno źródło.

## Aktualizowanie zainstalowanych umiejętności

CLI `skills` zapisuje globalne źródła i skróty treści
`~/.agents/.skill-lock.json`. Zaktualizuj ustawienia globalne z nagranych źródeł:

```shell
npx skills@1.5.22 update -g -y
```

Zaktualizuj jedną umiejętność lub ustawienia globalne:

```shell
npx skills@1.5.22 update verify-before-push -g -y
npx skills@1.5.22 update -g -y
```

Kopie starych projektów powinny zostać scentralizowane po sprawdzeniu planu. Migracja
najpierw instaluje i weryfikuje kopię globalną, a następnie zapisuje kopię zapasową
kopię starego ładunku i nie ma wpływu na konfigurację projektu i umiejętności innych osób:

```shell
python scripts/centralize_skill_installations.py plan --project-path . --json
python scripts/centralize_skill_installations.py apply --project-path . --expected-plan-sha256 <plan-value> --yes --json
```

Blokada dla `kolabse/skills` bez kwalifikatora jest zgodna z gałęzią domyślną i tak nie jest
zabezpiecza uwolnienie. Nie edytuj kopii globalnych ładunków: aktualizacja może
wymienić. Konfiguracja projektu i użytkownika jest przechowywana poza folderami umiejętności.

Z klonu lub archiwum wersji, aktualizacja umiejętności i migracja są obsługiwane
konfiguracja w jednej jawnej operacji:

```shell
python scripts/manage_installed_skills.py update --scope global --project-path . --yes --migrate
python scripts/manage_installed_skills.py doctor --scope global --project-path . --json
```

Podgląd dokładnego wyboru bez zewnętrznego instalatora i zmian:

```shell
python scripts/manage_installed_skills.py plan --scope global --project-path . --json
```

Planuj raporty źródłowe, wersje aktualne i docelowe, pochodzenie, kandydaci
migracja i akcje `update`, `unchanged`, `adopt-and-update` lub `blocked`.
Schematy: `schemas/manager-plan.schema.json` i
`schemas/manager-result.schema.json`.

Bez nazw menedżer wybiera z globalnego zamka tylko umiejętności kolabse;
zewnętrzne umiejętności globalne nie są aktualizowane. Aktualizacja starego projektu
jest zachowywany jedynie jako ścieżka przejścia do powiadamiania i migracji. Jeśli globalnie
zaktualizowano `execute-verified-development-lifecycle`, menedżer również
tworzy brakującą konfigurację, w której jest wystarczająca liczba faktów projektowych i zwrotów
wynik konfiguracji `created`, `configured` lub `blocked`.

`--include-user-config` jest potrzebny tylko do migracji konfiguracji niestandardowej
Telegram. `status` i `doctor` tylko do odczytu. `migrate` zmienia tylko istniejące
konfiguracji i nie konfiguruje niewykorzystanych umiejętności. Przez
Stan `collection-metadata.json` określa wersję, a `provenance_status`:
`verified`, `legacy-unverified` lub `mismatch`. Lokalna kasa
na podstawie manifestu, katalogu i zawartości, a nie nazwy folderu.

Zaakceptuj instalację starszej wersji przed wersją 1.2 bez metadanych dopiero po weryfikacji
źródło:

```shell
python scripts/manage_installed_skills.py status --scope global --project-path . --json
python scripts/manage_installed_skills.py update --scope global --project-path . --yes --adopt-legacy
```

Flaga nie ufa dowolnym plikom: źródło powinno zostać znormalizowane
`kolabse/skills` lub przejść kasę lokalną i diagnostykę końcową
musi potwierdzić metadane. Zewnętrzny interfejs CLI nie aktualizuje `sourceType: local` do
miejsce; dodaj ponownie takie umiejętności z oryginalnymi `--skill` i `--agent`.

### Uruchom bez klonowania repozytorium

Pobierz `scripts/bootstrap_update.py` z zaufanej wersji lub repozytorium.
Znajduje najnowszą stabilną wersję, sprawdza ZIP za pomocą `SHA256SUMS` i kompilacji GitHub
pochodzenie i menadżer uruchomień z izolowanego tymczasowego rozpakowania:

```shell
python bootstrap_update.py doctor --json
python bootstrap_update.py plan --json
python bootstrap_update.py update --yes --migrate --json
```

`--release v1.15.0` naprawia wersję. Do zaświadczenia potrzebny jest `gh`; tymczasowe
folder zostanie usunięty. Pamięć podręczna offline wymaga `--offline-archive` wraz z
`--offline-checksums`. `--allow-unattested-offline` - ewidentnie osłabiony tryb,
sprawdzanie jedynie sumy kontrolnej powierzonego archiwum. Wycofywanie wybiera stare
uwolnić; migracje konfiguracji pozostają w toku.

### Sprawdzanie ustawień globalnych

Stan globalny jest ograniczony do ogólnego `~/.agents/.skill-lock.json` v3. Ładunek
znajduje się pod adresem `~/.agents/skills` dla Codex i `~/.claude/skills` dla Claude Code.
Inne foldery użytkownika nie są skanowane. Wartość domyślna to Kodeks;
dla przepustki Claude `--agent claude-code`:

```shell
python scripts/manage_installed_skills.py status --scope global --json
python scripts/manage_installed_skills.py doctor --scope global --json
python scripts/manage_installed_skills.py plan verify-before-push --scope global --json
python scripts/manage_installed_skills.py update verify-before-push --scope global --yes --json
python scripts/manage_installed_skills.py status --scope global --agent claude-code --json
```

`--global-root` umożliwia sprawdzenie testu lub przesłanego układu w trybie tylko do odczytu.
Nie możesz zaktualizować przeniesionych katalogów głównych, ponieważ zewnętrzny CLI nie wie, jak to zrobić
adres. Zgłaszane są tylko nieznane formaty blokad.

Aby cofnąć, najpierw zapisz konfigurację, a następnie ponownie zainstaluj z nią żądany tag
te same umiejętności i agentów, na przykład:

```shell
npx skills@1.5.22 add kolabse/skills@v1.1.0 --skill verify-before-push --agent codex --copy --global -y
```

Obniżenie wersji nie jest obsługiwane bez wyraźnej dokumentacji wydania.
Przywracanie starych plików umiejętności nie powoduje obniżenia wersji konfiguracji; w przypadku niezgodności
przywróć odpowiednią kopię zapasową.

## Zainstaluj lub zaktualizuj lokalną wtyczkę Codexu na potrzeby programowania

W celu rozwoju lokalnego utwórz lub zaktualizuj rynek osobisty, skopiuj
plugin, dodaj cachebuster Codex i aktywuj:

```shell
python scripts/install_personal_plugin.py --activate
```

Instalator zapisuje niepotrzebne wpisy z rynku i nie edytuje manifestu
repozytorium. To jest ścieżka rozwoju, a nie normalna konfiguracja rynku Git.
Powtórz tę czynność po zaktualizowaniu kasy i rozpocznij nowe zadanie Kodeksu. `--json`
pokazuje wersję i ścieżki instalacji.

## Dostępne umiejętności

Umiejętności stabilne i eksperymentalne są wymienione w `skill-catalog.json`. Ich
konfiguracja, granice bezpieczeństwa i CLI są zgodne z polityką
[CONTRIBUTING.md](CONTRIBUTING.md). Katalog deklaruje zakres, status tylko do odczytu,
możliwości, zależności i integracje; umiejętności stanowe są idempotentne
konfiguracja, schemat i migracja dla konfiguracji wersjonowanej.

Katalogi są pogrupowane według głównego celu użytkownika w następujący sposób:
kolejność priorytetów. Każda umiejętność ma dokładnie jedną główną kategorię. Niezależny
tagi opisują etap cyklu życia, zakres, zachowanie i integracje;
status dojrzałości nie jest od nich zależny. Autorytatywne przypisania do odczytu maszynowego i
kontrolowane słownictwo jest w użyciu
[`skill-catalog.json`](../../../skill-catalog.json) i są sprawdzane przez
[`schemas/skill-catalog.schema.json`](../../../schemas/skill-catalog.schema.json).

Kontrolowane grupy tagów:

- etap cyklu życia: `prepare`, `investigate`, `implement`, `verify`,
  `publish`, `operate`, `document` i `handoff`;
- zakres: `project`, `repository`, `multi-repository`, `workstation`,
  `external-service` i `skill-collection`;
- zachowanie: `read-only-planning`, `mutation`, `evidence-producing`,
  `orchestration` i `notification`;
- integracja: `git`, `github`, `telegram`, `google-drive` i `yandex-cloud`.

### Rozwój i jakość kodu

#### `develop-with-test-first-evidence` (eksperymentalny)

Implementuje zachowanie poprzez zweryfikowany refaktor czerwono-zielony.

**Co robi:** naprawia skoncentrowany test, który kończy się niepowodzeniem z właściwego powodu przed kodem;
wiąże skupioną i szerszą zieleń ze stanem końcowym i potwierdza dowody.

**Czego nie robi:** nie tworzy koloru czerwonego jako rozkładu zewnętrznego zachowania, nie wywołuje
kolejne testy są pierwszymi testami i nie ukrywają starych/środowiskowych/ostatecznych awarii.

**Dzwonić:**

```text
$develop-with-test-first-evidence Zaimplementuj zachowanie z udokumentowanym cyklem red-green-refactor.
```

#### `review-code-changes` (eksperymentalny)

Sprawdza określoną zmianę pod kątem poprawności, bezpieczeństwa, niezawodności i kompatybilności.

**Co robi:** określa poziom bazowy/zmianę, raportuje ustalenia poparte dowodami
wpływ, czynnik wyzwalający, priorytet i dokładna lokalizacja ujawnia niepewność i luki w testach.

**Czego nie robi:** nie uznaje preferencji smakowych za wady, nie wdraża i
nie publikuje ustaleń bez zgody i nie zastępuje recenzji ogólnym wyjaśnieniem.

**Dzwonić:**

```text
$review-code-changes Przejrzyj tę gałąź względem baseline i zgłoś potwierdzone defekty.
```

#### `diagnose-software-defects` (eksperymentalny)

Bada niepowodzenia i regresje do potwierdzonej przyczyny lub uszeregowanych hipotez.

**Co robi:** ogranicza i bezpiecznie odtwarza objaw, sprawdza
stawia konkurencyjne hipotezy i podaje pierwotną przyczynę, warunki, promień wybuchu, pewność
oraz plan testów środków zaradczych.

**Czego nie robi:** nie wnioskuje o przyczynowości z korelacji, nie mutuje produkcji,
nie niszczy dowodów i nie wprowadza spekulatywnej poprawki zamiast diagnozy.

**Dzwonić:**

```text
$diagnose-software-defects Zdiagnozuj regresję i oddziel dowody od hipotez.
```

#### `resolve-git-conflicts` (eksperymentalny)

Semantycznie rozwiązuje zatwierdzone konflikty dotyczące scalania/rebase/wybierania wiśniowego.

**Co robi:** sprawdza aktywną operację, bazę, boki i każdą niepołączoną ścieżkę;
łączy tylko jasne zachowanie, sprawdza ścieżki i jawnie wywołuje następną
Krok Gita.

**Czego nie robi:** Nie uważa normalnej rozbieżności za konflikt plików, tak nie jest
przechowuj/resetuj/przerwaj/kontynuuj/wymuś wypychanie automatycznie, a nie jako zbędne i nie
zgaduje niejednoznaczne rozwiązania binarne/wygenerowane/schematowe.

**Dzwonić:**

```text
$resolve-git-conflicts Rozwiąż aktywne konflikty plik po pliku i zweryfikuj wynik.
```


### Repozytoria i dostarczanie zmian

#### `synchronize-git-repositories`

Ustawia bieżący stan zdalny bez nadpisywania pracy lokalnej.

**Co robi:** znajduje tylko repozytoria istotne dla zadania, pobiera je
śledzone urządzenia zdalne, przewijanie do przodu i czyszczenie gałęzi znajdujących się tylko za nimi, raporty są niebezpieczne
state i, jeśli to konieczne, publikuje gałąź funkcji ze zweryfikowanego źródła głównego do edycji.

**Czego nie robi:** Nie przechowuje automatycznie, nie resetuje, nie zmienia bazy, nie łączy, nie czyści, nie przełącza ani
pchanie siłą; nie ukrywa rozbieżności i nie skanuje repozytoriów stron trzecich.

**Dzwonić:**

```text
$synchronize-git-repositories Skonfiguruj politykę synchronizacji repozytoriów projektu.
```

#### `verify-before-push`

Wiąże kontrole zadeklarowane w projekcie z dokładnym stanem push Git.

**Co robi:** konfiguruje zasady należące do repozytorium poza umiejętnością, przeprowadza kontrole
i zapisuje dowody dotyczące zatwierdzeń, drzewa roboczego, upstream i konfiguracji; zamknięcie nie powiodło się, kiedy
brakujące, uszkodzone lub nieaktualne dowody.

**Czego nie robi:** Nie blokuje nieosiągniętych repozytoriów, nie analizuje
dowolną powłokę i nie uważa, że stare zakończone sukcesem sprawdzenie jest istotne.

**Dzwonić:**

```text
$verify-before-push Skonfiguruj politykę weryfikacji tego projektu.
```

#### `coordinate-code-documentation-repositories` (eksperymentalny)

Koordynuje pojedynczą, weryfikowalną zmianę w kodzie i dokumentacji kanonicznej
żyją w różnych repozytoriach.

**Co robi:** określa zadeklarowane role repozytorium, tworzy plan tylko do odczytu
na oryginalnych zatwierdzeniach, wymaga dowodów dotyczących skonfigurowanych tematów i sprawdza oba
opublikowanych tożsamości i identyfikowalności między repozytoriami.

**Czego nie robi:** Nie odgaduje ról po nazwie, nie zastępuje dokumentacji
Digest, nie edytuje /commit/push/merge i nie bierze pod uwagę obecności plików
dowód zgodności semantycznej.

**Dzwonić:**

```text
$coordinate-code-documentation-repositories Wprowadź zmianę w zadeklarowanych repozytoriach kodu i dokumentacji oraz zweryfikuj oba opublikowane wyniki.
```

#### `execute-configured-gitflow-releases` (eksperymentalny)

Wykonuje trasy standardowe i poprawki zgodnie z zadeklarowanym przez projekt kontraktem GitFlow.

**Co robi:** czyta gałęzie, zdalne, bramy i trasę domyślną z wersjonowanej konfiguracji;
zatwierdza plan do zatwierdza; stosuje wspólne bramy i kontrole produkcji,
wdrożenie i obowiązkowa ponowna integracja poprawek.

**Czego nie robi:** Nie odgaduje nazw oddziałów i domyślnie wybiera poprawkę;
nie obsługuje przepływu łącza ani specjalnego łączenia tej kolekcji; nie omija
ochrony, nie zapisuje historii na nowo i nie kończy poprawki do czasu ponownej integracji.

**Dzwonić:**

```text
$execute-configured-gitflow-releases Wykonaj zadeklarowane standardowe wydanie i zweryfikuj tożsamość produkcyjną.
$execute-configured-gitflow-releases Wykonaj jawny hotfix i zweryfikuj jego powrót do linii rozwojowej.
```

#### `execute-verified-development-lifecycle` (eksperymentalny)

Planuje i weryfikuje zadeklarowaną przez projekt ścieżkę od przygotowania obiektu do
przejrzałem integrację deweloperów, obserwację dostaw, dokumentację i porządkowanie.

**Co robi:** podczas zarządzanej aktualizacji lub pierwszego wywołania tworzy konserwatywną wersję
konfiguracja projektu na podstawie obserwowalnych korzeni Git, wcześniejszych referencji, kontroli i dokumentacji
i raportuje wszystkie ustawienia domyślne; naprawia plan związany z podsumowaniem do edycji, promuje uporządkowany
punkty kontrolne zatrzymanych dowodów; sprawdza funkcję przed edycją, najpierw testuje,
inspekcja wstępna, przegląd, push, potok, dokumenty, integracja, delegowanie produkcji,
dostawa, dym, powiadomienia i sprzątanie; po błędzie wraca do zadeklarowanego
punkt i unieważnia dalsze dowody.

**Czego nie robi:** Nie zgaduje adapterów specyficznych dla dostawcy, ról repo,
polityka dostaw lub autoryzacja danych niejednoznacznych;
sam nie wypycha/otwiera/nie łączy/wdraża/nie powiadamia/edytuje dokumentów/usuwa; produkcja pozostaje z
zatwierdzony proces, taki jak `$execute-configured-gitflow-releases`.

Najpierw zainstaluj wymagany `$synchronize-git-repositories`,
`$develop-with-test-first-evidence`, `$verify-before-push` i
`$review-code-changes`. Brak umowy dotyczącej cyklu życia wersji 1 należącej do projektu
stworzony na podstawie zaobserwowanych faktów przed pierwszym planem; sprawdź i wyjaśnij domyślne ustawienia,
jeśli zasady projektu określają bardziej precyzyjną politykę. Umiejętności opcjonalne
są ustawiane tylko dla włączonych punktów kontrolnych.

**Dzwonić:**

```text
$execute-verified-development-lifecycle Zaplanuj i zweryfikuj zmianę zgodnie ze skonfigurowanym cyklem rozwoju projektu.
```


### Ciągłość wiedzy i projektu

#### `maintain-work-log`

Prowadzi kanoniczny datowany dziennik `docs/reports/work-log.md`.

**Co robi:** rejestruje istotne zmiany, operacje, diagnostykę,
decyzje, kontrole, blokady i wycofywania; zapisuje format i przywraca
historię wyłącznie w oparciu o dostępne dowody.

**Czego nie robi:** Nie działa bez wymagań, nie zapisuje sekretów,
dzienniki aplikacji, śledzenie czasu lub niepotwierdzone zdarzenia.

**Dzwonić:**

```text
$maintain-work-log Skonfiguruj prowadzenie datowanego dziennika projektu.
```

#### `maintain-project-digest` (eksperymentalny)

Utrzymuje codzienny, przyjazny dla użytkownika przegląd wprowadzonych zmian.

**Co robi:** Grupuje zmiany bieżącej daty według funkcji, ulepszeń,
poprawki, bezpieczeństwo, dokumentacja i ważne zachowania; pisze krótko,
Pomija puste kategorie, nie zmienia przeszłych dat i chroni udostępnione wpisy.

**Czego nie robi:** nie wybiera niejednoznacznego miejsca w dokumentacji, nie pisze
planów i działań wewnętrznych, nie zastępuje dziennika pracy/dziennika zmian/notatek o wydaniu i
nie zapisuje na nowo przeszłych okresów.

**Dzwonić:**

```text
$maintain-project-digest Dodaj ukończone dziś zmiany widoczne dla użytkowników do podsumowania projektu.
```

#### `sync-project-context`

Synchronizuje prywatny, wyczyszczony stan projektu i zadań między komputerami.
Umiejętność jest stabilna po dwóch niezależnych uruchomieniach Dysku Google na rzeczywistym urządzeniu.

**Co robi:** przechowuje niezmienne punkty kontrolne w zatwierdzonym folderze lub na dysku;
niekwalifikowane żądanie domyślnie korzysta z podłączonego Dysku Google; prowadzi
nieprzezroczysty strumień z linią bazową/deltami, widocznymi tytułami, decyzjami i odciskami palców Git;
planuje zapisywanie, przywracanie i synchronizację dwukierunkową zadań/wsadów; sprawdza migawki,
odczyt zwrotny i tożsamość projektu; przechowuje oddzielny manifest środowiska
reguły, umiejętności, wtyczki i bezpieczne ustawienia, których Git nie posiada.

**Czego nie robi:** nie kopiuje źródeł, różnic, surowych transkrypcji, ukrytego rozumowania,
dane uwierzytelniające, OAuth lub ustawienia; nie powiela środowiska należącego do Gita i tak nie jest
zastępuje reguły docelowe; w metadata-only nie obejmuje gałęzi/ścieżki.

Codex Desktop obsługuje wsadowe wykrywanie/tworzenie/zmianę nazwy i złącze Drive.
Claude Code wykorzystuje przenośne punkty kontrolne, folder lokalny i rdzeń środowiska,
ale nie sprawdza sesji i kończy się niepowodzeniem w przypadku operacji wsadowych opartych wyłącznie na Kodeksie.

**Dzwonić:**

Jednorazowa konfiguracja na komputer:

```text
$sync-project-context Skonfiguruj ten klon w trybie metadata-only. Domyślnie użyj połączonego Dysku Google, chyba że wyraźnie wybiorę inny kanał.
```

Następnie:

```text
$sync-project-context Zapisz stan bieżącego zadania.
$sync-project-context Przywróć wszystkie zadania projektu na tym komputerze.
$sync-project-context Zsynchronizuj wszystkie zadania dwukierunkowo i pokaż konflikty przed zastosowaniem zmian.
```

W kodzie Claude zamień `$` na `/`.


### Koordynacja i komunikacja

#### `orchestrate-agent-work` (eksperymentalny)

Koordynuje wyraźnie upoważnionych subagentów i jest odpowiedzialny za ogólny wynik.

**Co robi:** dzieli pracę równoległą na ograniczone, nienakładające się na siebie prace
zadania, obserwuje i uzgadnia wyniki, sprawdza integrację.

**Czego nie robi:** nie deleguje bez pozwolenia, nie przekazuje zgód, tajemnic,
destrukcyjne oczyszczanie lub mutacje zewnętrzne i nie liczy się indywidualnych wyników
dowód udanej integracji.

**Dzwonić:**

```text
$orchestrate-agent-work Deleguj niezależne podzadania agentom i zweryfikuj wspólny wynik.
```

#### `synchronize-team-skills` (eksperymentalny)

Synchronizuje uznane na całym świecie umiejętności członków zespołu ze sprawdzonymi
manifestować się w dokumentacji projektowej; ustawienia projektu pozostają lokalne.

**Co to robi:**

- tworzy lub odczytuje `team-agent-skills.md` w wybranym katalogu dokumentacji;
- porównuje wymagania Kodeksu i Kodeksu Claude'a ze zweryfikowanymi kopiami globalnymi;
- pokazuje brakujące, stare, nowsze, niezweryfikowane, bez zmian,
  kopie projektów obejmujące szersze obszary i dodatkowe umiejętności;
- buduje plan instalacji dla jednej wersji kolekcji powiązanej z manifestem skrótu;
- po potwierdzeniu instaluje tylko uzgodniony zestaw i go weryfikuje.

**Czego to nie robi:**

- nie zamienia losowego stanu jednego komputera w standard poleceń;
- nie zapisuje sekretów, konfiguracji użytkownika, ścieżek komputerowych ani uwierzytelniania wtyczek;
- nie usuwa dodatkowych umiejętności, nie obniża poziomu ani nie usuwa starych
  kopie projektowe bez potwierdzonej centralizacji;
- nie twierdzi, że otwarty dialog załadował już nowe umiejętności.

**Dzwonić:**

```text
$synchronize-team-skills Sprawdź umiejętności projektu względem manifestu zespołu.
$synchronize-team-skills Pokaż plan i zsynchronizuj moje umiejętności z dokumentacją zespołu.
$synchronize-team-skills Dodaj maintain-project-digest do zespołowego zestawu umiejętności.
```

#### `report-skill-feedback` (eksperymentalny)

Po wyraźnej zgodzie przygotowuje ograniczony, zanonimizowany raport z obserwowanego wykonywania umiejętności. Wersja robocza nie zawiera kodu, korespondencji, tajemnic, nazw, ścieżek ani adresów URL. Jest on pokazywany użytkownikowi w całości i wysyłany do `kolabse/skills` dopiero po odrębnym potwierdzeniu; Problem pozostaje powiązany z kontem GitHub.

**Aufruf/Inwokacja:**

```text
$report-skill-feedback Przygotuj pozbawiony danych identyfikujących podgląd tego użycia umiejętności; jeszcze go nie wysyłaj.
```

#### `notify-via-telegram`

Wysyła aktualizacje telegramu dotyczące cyklu życia długich zadań agenta.

**Co robi:** raportuje początek/kamień milowy/problem/bloker/zakończenie; konfiguruje
bot i czat, oferuje bezpieczny formularz Windows, przechowuje dane uwierzytelniające w konfiguracji użytkownika,
obsługuje oddzielny czat/temat projektu i eksportuje routing bez tajemnic
`sync-project-context`; działa na standardowej bibliotece Pythona.

**Czego nie robi:** Nie umieszcza tokena na czacie, w historii powłoki ani w repozytorium; nie mogę tego znieść
bot uwierzytelniający pomiędzy komputerami, nie powiadamia o żądaniu użytkownika i nie jest
framework do tworzenia botów Telegram.

**Dzwonić:**

```text
$notify-via-telegram Skonfiguruj powiadomienia Telegram dla długich zadań.
$notify-via-telegram Skonfiguruj projekt tak, aby wysyłał powiadomienia tylko do czatu zespołu zamiast kanału globalnego.
```


### Infrastruktura i operacje

#### `operate-yandex-cloud`

Współpracuje z jawnie skonfigurowaną infrastrukturą Yandex Cloud w ramach projektu.

**Co robi:** przechowuje identyfikatory chmur/folderów w konfiguracji projektu, lokalnym profilu `yc`
w ignorowanej konfiguracji; sprawdza narzędzia/wersje/kontekst; obsługuje zakresowy interfejs CLI,
SSH, Terraform, Ansible, Helm, Kubernetes, wdrożenie, DB, przechowywanie, DNS,
monitorowanie, tworzenie kopii zapasowych i przepływ pracy w przypadku incydentów.

**Czego nie robi:** Nie wysyła danych Yandex Cloud z ogólnego żądania SSH/Kubernetes, nie
przechowuje dane uwierzytelniające we współdzielonej konfiguracji i nie zmienia się, dopóki cel nie zostanie zdefiniowany,
kontekst i autoryzacja.

**Dzwonić:**

```text
$operate-yandex-cloud Skonfiguruj projekt do pracy z Yandex Cloud.
```


### Rozwój zbioru umiejętności

#### `discover-skill-candidates` (eksperymentalny)

Znajduje pomysły na umiejętności, które można wykorzystać ponownie w ograniczonych zasadach i kontekście, ale nie
tworzenie umiejętności.

**Co robi:** `AGENTS.md` odnoszący się do projektu inwentarza z Git/line
pochodzenie; z dokumentacją opracowań pozwolenia, wybrane pliki, zastrzeżona
historia i potwierdzone podsumowania rozmów lub przekazań; ocenia kandydatów i
porównuje z katalogami; oferuje wkład, wdrożenie lokalne lub
odroczenie; eksportuje oczyszczony pakiet związany z podsumowaniem.

**Czego nie robi:** nie zmienia zasad, nie tworzy ani nie ustanawia umiejętności; nie
wyświetla listę czatów, nie czyta surowych transkrypcji i nie skanuje szeroko kodu; nie
eksportuje reguły, ścieżki, sekrety, adresy URL i e-maile; nie promuje jednorazowych lub
wrażliwe umowy bez przeglądu.

**Dzwonić:**

```text
$discover-skill-candidates Przeanalizuj lokalne reguły projektu i przygotuj potwierdzoną listę pomysłów na umiejętności, niczego nie tworząc.
```

#### `release-skill-collection`

Planuje, sprawdza, audytuje i oczyszcza deterministyczne wydania kolekcji.

**Co robi:** sprawdza wersje, dziennik zmian, Git, testy, bezpieczeństwo, archiwa i
sumy kontrolne; sprawdza bramki powiązane z zatwierdzeniem; audytuje aktywa, manifesty i
atest potwierdza obecność gałęzi przed oczyszczeniem.

**Czego nie robi:** nie zakłada uprawnień do zatwierdzania/oznaczania/wypychania/przepływu pracy; nie
przenosi znacznik, nie zastępuje zasobów i nie usuwa oddziałów według nazwy lub nieaktualnego planu.

**Dzwonić:**

```text
$release-skill-collection Zaplanuj i zweryfikuj wydanie vX.Y.Z, ale jeszcze go nie publikuj.
```

## Obsługiwane kompozycje

Katalog definiuje trzy uporządkowane procesy:

- `protected-push`: synchronizacja, następnie aktualny dowód weryfikacji;
- `yandex-cloud-operation`: synchronizacja i obsługa w chmurze w określonym zakresie;
- `skill-collection-release`: synchronizacja, lokalna weryfikacja wydania i dowody przed publikacją.

Dziennik pracy i telegram są opcjonalne. Wymagane kroki nie zostały zamknięte; opcjonalne
błędy nie zmieniają wyniku głównego. Plan formularzy `scripts/compose_skills.py`,
i `--evidence` z obwodami `schemas/composition-evidence.schema.json` i
`schemas/composition-result.schema.json` sprawdza kolejność i wyniki.

## Dodawanie umiejętności

Śledź [CONTRIBUTING.md](CONTRIBUTING.md) i
[`templates/skill-template.md`](../../../templates/skill-template.md). Wszyscy
umiejętność ma wpis w `skill-catalog.json` z właścicielem, platformami, statusem,
licencji i pochodzenia. Konfiguracja projektu jest przechowywana poza zainstalowanym folderem.

Nie dodawaj instalatora z pojedynczą umiejętnością na poziomie repozytorium. Dla zarządzanych
ChatGPT/Codex, kolekcja jest dodatkowo wyposażona w wtyczkę OpenAI
układ międzyagentowy.

Kontrole lokalne:

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py
```

Przygotuj zestaw wyzwalaczy na ślepo:

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
```

Pakiet zawiera tylko nazwy, opisy publiczne, nieprzejrzyste identyfikatory i podpowiedzi bez
etykiety i powody autora. Selektor zwraca ścisły JSON; stopień:

```shell
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

`run -- <command>` przekazuje pakiet przez standardowe wejście. Poświadczenia nie powinny się tam znajdować
argumenty. `.trigger-evals/` jest ignorowany. Duże apartamenty są podzielone na
partie związane z trawieniem, po 64 sztuki; zmiany rozmiaru za pomocą `--batch-size`.

Przed wydaniem użyj osobnej wersji wstrzymania z zablokowanym skrótem:

```shell
python scripts/trigger_evals.py prepare \
  --corpus release-holdout \
  --output .trigger-evals/release-holdout.json
```

Porównanie tylko z wersją bazową tej samej wersji:

```shell
python scripts/trigger_evals.py compare \
  --candidate .trigger-evals/candidate-report.json \
  --markdown-output .trigger-evals/comparison.md
```

Różne podsumowania asercji są odrzucane; Porównuje się wskaźniki ogólne i dotyczące poszczególnych umiejętności.
Domyślnie linia bazowa jest pobierana z katalogu. Dla selektora niedeterministycznego
zbierz nieparzystą liczbę co najmniej trzech runów w ciemno:

```shell
python scripts/trigger_evals.py aggregate \
  --corpus release-holdout \
  --predictions run-1.json run-2.json run-3.json \
  --predictions-output .trigger-evals/aggregate.json \
  --json-output .trigger-evals/candidate-report.json
```

## Weryfikacja wydania

Wydanie zawiera deterministyczne ZIP i TAR.GZ, `release-manifest.json` i
`SHA256SUMS`. Pobierz cztery zasoby do jednego folderu i uruchom:

```shell
python scripts/build_release.py --verify <download-directory>/SHA256SUMS
```

GitHub wyświetla podsumowanie SHA-256 każdego zasobu i publikuje artefakt
atesty. Sprawdzanie pobranego pliku:

```shell
gh attestation verify <artifact> --repo kolabse/skills
```
