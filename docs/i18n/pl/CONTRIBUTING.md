# Dodawanie umiejętności

[English](../../../CONTRIBUTING.md) | [Русский](../ru/CONTRIBUTING.md) | [Español](../es/CONTRIBUTING.md) | [Français](../fr/CONTRIBUTING.md) | [Deutsch](../de/CONTRIBUTING.md) | [Português (Brasil)](../pt-BR/CONTRIBUTING.md) | [日本語](../ja/CONTRIBUTING.md) | [Italiano](../it/CONTRIBUTING.md) | [한국어](../ko/CONTRIBUTING.md) | [简体中文](../zh-CN/CONTRIBUTING.md) | [Türkçe](../tr/CONTRIBUTING.md) | Polski | [Українська](../uk/CONTRIBUTING.md)

> To jest tłumaczenie dla ułatwienia czytania. Jest kanoniczny
> [Wersja angielska](../../../CONTRIBUTING.md).

To repozytorium jest kanonicznym miejscem dla ponownie wykorzystywanych umiejętności kolabse.
Każda umiejętność musi pozostać skupiona, możliwa do przeniesienia, przypisania i
nadaje się do samodzielnego montażu.

## Przed dodaniem umiejętności

1. Zidentyfikuj źródło kanoniczne i zdecyduj, czy repozytorium będzie jego właścicielem
   umiejętności lub odzwierciedlić inne źródło.
2. Potwierdź swoje prawo do rozpowszechniania każdej skopiowanej instrukcji, skryptu,
   materiał i źródło odniesienia. Oryginalne materiały są akceptowane przez
   Apache-2.0, chyba że wyraźnie określono inaczej. Zachowaj licencje stron trzecich,
   powiadomienia o prawach autorskich, przypisaniach i zmianach; wskazać SPDX w katalogu.
   Nie publikuj nieautoryzowanych materiałów.
3. Znajdź nakładające się wyzwalacze w istniejących opisach. Rozwiń swoje umiejętności
   jeśli cel procesu jest taki sam; utwórz nowy z samoczynnym wyzwalaniem i
   kryteria ukończenia.
4. Wybierz nazwę zaczynającą się od czasownika, oddzieloną myślnikami i nie dłuższą niż
   63 znaki.

Kryterium ukończenia: przed skopiowaniem plików właściciel, pochodzenie,
licencja, obszar odpowiedzialności i nazwa umiejętności.

## Towarzyszenie kandydatowi aż do wdrożenia

Jeśli nowa lub rozszerzona umiejętność pochodzi z problemu GitHub, zapisz problem jako
kanoniczny element pracy, dopóki implementacja nie pojawi się w głównej gałęzi.

1. Określ pierwotny problem w implementacji żądania ściągnięcia.
2. Dodaj `Closes #<issue-number>` do opisu żądania ściągnięcia. Jeśli wydanie nie jest możliwe
   zamknąć, jasno wyjaśnić przyczynę i dalsze losy.
3. Po połączeniu sprawdź problem, nie polegając wyłącznie na słowie kluczowym. Jeśli on
   nieoczekiwanie otwarty, zamknij jako gotowy z linkami do PR i wydania.
4. Jeżeli realizacja zostanie odrzucona, zastąpiona lub częściowo ukończona, odejdź
   wyjaśnienie i wybierz odpowiedni Status Sprawy. Obecność oddziału lub PR nie jest
   potwierdza ukończenie kandydata.

Kryteria ukończenia: Każdy wdrożony kandydat jest śledzony od wydania do
połączył PR, a Emisja ma zweryfikowany status końcowy i wyjaśnienie wyniku.

## Dodawanie lub przenoszenie umiejętności

1. Zsynchronizuj repozytoria źródłowe i docelowe bez nadpisywania repozytorium lokalnego
   praca.
2. Utwórz `skills/<skill-name>/SKILL.md`. Na froncie tylko wyjdź
   `name` i `description`; Nazwa folderu musi być zgodna z `name`.
3. Umieść pomocniki deterministyczne w `scripts/`, szczegóły agenta -
   do `references/`, materiały wyjściowe do `assets/`, opcjonalne metadane interfejsu użytkownika
   - w `agents/openai.yaml`. Konfiguracja projektu pozostaje poza folderem umiejętności.
4. Zapisz kroki imperatywne z weryfikowalnymi kryteriami ukończenia. Ciało musi
   być krótszy niż 500 linii; Umieść szczegóły poszczególnych oddziałów w linkach bezpośrednich.
5. Dodaj jeden wpis do `skill-catalog.json`:
   - `name` i ścieżka względna `path`;
   - dokładnie jeden główny `category`, biorąc pod uwagę udokumentowane zamówienie
     priorytet;
   - jeden lub więcej kontrolowanych `tags` dla etapu cyklu życia,
     dziedziny działania, zachowań i integracji;
   - `status`: `experimental`, `stable` lub `deprecated`;
   - Nazwy GitHub w `maintainers`;
   - obsługiwane przez `platforms`;
   - wyrażenie SPDX w `license`;
   - rodzaj pochodzenia, źródło, dawne nazwy i repozytorium kanoniczne.
   Sprawdź kategorię i wartości tagów według
   `schemas/skill-catalog.schema.json`; status dojrzałości nie jest od nich zależny.
6. Dodaj umiejętność do katalogu README z podaniem celu, instalacji i wymagań
   pierwsza akcja.
7. Dodaj deterministyczne testy skryptowe i realistyczne pozytywne i
   zamknij negatywne prośby. Przechowuj co najmniej trzy skrzynki na
   `evals/<skill-name>.json` i wskaż plik jako `trigger_evals` w katalogu.

W przypadku przeniesionej umiejętności zachowaj historię pochodzenia nawet po przeniesieniu
do tego repozytorium. W przypadku umiejętności oferowanej przez dostawcę zatwierdź niezmienną wersję
źródło, licencja i informacja; oddzielić zmiany wstępne od zmian lokalnych.
Sprawdź zgodność licencji przed połączeniem materiałów stron trzecich z
Apache-2.0.

Kryteria ukończenia: Czytelnik może zidentyfikować źródło, właściciela, licencję,
obsługiwane środowiska i sposób testowania umiejętności.

## Umowa konfiguracyjna

Każda umiejętność niestandardowa deklaruje obiekt `configuration`
`skill-catalog.json` i spełnia następujące zasady:

- `configure` jest przechowywany jako tablica argv, powtórz bezpieczne, zapisuje
  obcy tekst i nie zmienia identycznej konfiguracji;
- `status` jest tylko do odczytu, obsługuje natywny JSON, kończy się pomyślnie
  tylko przy poprawnej konfiguracji i nie wyświetla sekretów;
- obszar `project` lub `user` jest określony jawnie, konfiguracja jest na zewnątrz
  zainstalowany folder umiejętności;
- Konfiguracja JSON/YAML ma wersję pozytywną, schemat JSON i jest zamknięta w trybie awaryjnym
  zespół migracyjny;
- tekst prowadzony wykorzystuje sparowane znaczniki umiejętności, odrzuca uszkodzone
  lub powtarzających się punktorów i nie przepisuje reszty tekstu;
- umiejętności bez statusu użyj formatu `none`, tylko status tylko do odczytu i nie
  utwórz fikcyjne pliki konfiguracyjne.

Polecenia są przechowywane w tablicach, a nie w ciągach powłoki. Użyj symboli zastępczych, takich jak
`<project-root>` i nigdy nie umieszczaj danych uwierzytelniających w poleceniach katalogowych.
Migracje muszą być sekwencyjne i idempotentne; nie jest już znany
nową wersję należy raczej odrzucić, niż próbować obniżyć jej wersję.

Kryterium zakończenia: wielokrotna konfiguracja daje wynik identyczny co do bajta,
status nic nie zapisuje, migracje zachowują obsługiwane dane wejściowe, testy
okładka brakująca, uszkodzona, aktualna i przestarzała konfiguracja.

## Zapisz ścieżkę aktualizacji klienta

- Wersje `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`,
  `skill-catalog.json.collection_version` i wszyscy
  `skills/*/collection-metadata.json` musi pasować do wersji.
- Sprawdź skopiowaną instalację i zaktualizuj najstarszą obsługiwaną wersję
  wersje przypisanego `skills` CLI dla `codex` i `claude-code`.
- Ustaw kolekcję globalnie dla każdego agenta. Zapisz konfigurację
  kierowane zasady i zamierzone ustawienia projektowe wykraczające poza ustalone umiejętności. Nie
  utwórz nieużywaną konfigurację umiejętności podczas aktualizacji.
- Po aktualizacji wykryj stare kopie projektu i wyświetl powiadomienie
  o centralizacji. Migrację należy najpierw zbudować plan bez zapisu, sprawdź
  kopie globalne przed usunięciem, zachowaj dodatkowe umiejętności i ustawienia,
  zostaw odzyskiwalną kopię zapasową i poproś o zgodę na zweryfikowany plan.
- Migracje dokumentów i ograniczenia wycofywania zmian w pliku README i dzienniku zmian. Degradacja
  konfiguracja nie jest obsługiwana bez osobnego testu.
- Zmieniając rynek osobisty, zapisz niepotrzebne wpisy, dodaj
  jeden cachebuster do kopii wtyczki i wymaga nowego zadania Kodeksu po aktywacji.

Kryteria ukończenia: Konsument widzi wersje, może aktualizować i migrować
konfigurację, zdiagnozuj wersje mieszane i zainstaluj ponownie poprzedni tag.

## Zachowaj zachowanie między agentami

Ogólne `SKILL.md` i pomocnicy powinni być przenośni. Kodeks pozostaje
wartość domyślna; jawny kod Claude używa `.claude/skills`,
`CLAUDE.md` i `/skill-name`. Nie zastępuj istniejących interfejsów API `.agents` ze względu na
zmiana nazwy dla innego użytkownika.

`agents/openai.yaml` - metadane OpenAI UI, `.codex-plugin` - opakowanie Codexu,
a pakiet Claude znajduje się w `.claude-plugin`. Jeden manifest nie zastępuje
sprawdzam inny. Jeśli agent nie obsługuje funkcji takiej jak wyliczanie
Zadania Codex Desktop, ograniczona operacja musi zakończyć się niepowodzeniem, ponieważ jest nieobsługiwana,
utrzymywanie jądra jako przenośnego.

Kryteria ukończenia: Obie globalne instalacje zawierają te same umiejętności, szacunek
Natywne zasady i układy, wartości Kodeksu nie ulegają zmianie, ale konsumpcyjny dym
wymienia obu agentów.

## Skład umiejętności według możliwości

Zadeklaruj małe nazwy w `provides`, obowiązkowe zależności w `requires`,
nieblokujące się integracje w `optional_integrations`. Nazwany skład
Tylko powtarzalny proces wymaga co najmniej dwóch umiejętności. Ona
`required_steps` są zamawiane, a `optional_steps` są wyzwalane tylko wtedy, gdy
możliwości udostępnione przez projekt lub użytkownika.

Nie kopiuj procesu jednej umiejętności do drugiej. Bądź uzależniający, wykorzystuj
obserwowalny wynik i zatrzymanie, jeśli jest to obowiązkowe
niedostępne. Opcjonalne powiadomienia i rejestrowanie nie powodują wystąpienia błędu
sukcesu i nie zamieniaj udanego wyniku głównego na porażkę.

Kryteria ukończenia: każda wymagana funkcja ma dostawcę i kroki
jednokrotne odniesienie się do istniejących umiejętności, kolejność objęta testem integracyjnym
lub kryterium wykonywalności.

## Zarządzanie statusem cyklu życia

- Nowa lub znacznie przerobiona umiejętność pozostaje `experimental` do
  przekaże metadane, pomocniki deterministyczne, testy międzyplatformowe,
  korpus wyzwalaczy programistycznych, niezależny test do przodu, dym z kopiowaną instalacją i
  zwolnić wstrzymanie. Wymagania, które nie mają zastosowania, mogą być oznaczone jako N/A.
- `stable` jest przypisany tylko w wersjonowanej wersji kolekcji wraz z
  `stable_since`. Stable gwarantuje zgodność udokumentowanych wejść,
  konfiguracje, granice bezpieczeństwa i CLI w ramach głównej wersji lub instrukcji
  migracja.
- Przed usunięciem przypisz `deprecated`, określ wymianę lub migrację i
  zachowaj tę umiejętność przez co najmniej jedną pomniejszą wersję, z wyjątkiem pilnych problemów związanych z bezpieczeństwem.

Kryterium ukończenia: status jest potwierdzony poprzez obserwowalną weryfikację i jasno komunikuje
kompatybilność.

## Zachowaj pochodzenie zainstalowanych umiejętności

Znana nazwa umiejętności to tylko kandydat, a nie identyfikator kolekcji. Sprawdź
źródło zewnętrznego pliku blokady z `collection-metadata.json`. Normalizuj
obsługiwane formularze GitHub do `https://github.com/kolabse/skills`; lokalny
sprawdzaj źródła według manifestu, katalogu i treści umiejętności bez zależności
w imieniu kasy.

Błąd zamknięty, jeśli istnieje pasująca nazwa z innego źródła lub jest ona sprzeczna
metadane. Przyjęcie starszej wersji pozostaje jednoznaczne i jest dozwolone tylko po zweryfikowaniu
źródło blokady; efektem powinny być aktualne metadane i rzetelna diagnostyka.

Kryterium ukończenia: status pokazuje pochodzenie, aktualizacja wybiera tylko
sprawdzone umiejętności lub wyraźnie przyjęte dziedzictwo, testy obejmują kolizje,
wydania referencyjne, zmieniono nazwę kasy i starsze instalacje.

## Weryfikowalna automatyzacja konsumencka

`plan` pozostaje tylko do odczytu: nie wywołuje instalatorów, migracji ani sieci.
Opublikuj wersjonowany schemat JSON dla planu/wyniku i rozróżnij między niezmienionymi,
aktualizowane, migrowane, pomijane, blokowane i kończyły się niepowodzeniem bez analizowania czytelnego dla człowieka interfejsu CLI.

Ogranicz globalne wykrywanie do udokumentowanych katalogów głównych zamków i instalacji,
nie skanuj swojego katalogu domowego. Zastosuj te same zasady pochodzenia, wyraźne
selekcja i diagnostyka poaktualizacyjna.

Samodzielny pasek startowy sprawdza sumę kontrolną przed rozpakowaniem, pochodzenie z GitHub wcześniej
wykonanie, odrzuca wpisy przejścia i dowiązań symbolicznych, używa folderu tymczasowego i
zwraca menedżera kodu. Tryb bez zaświadczenia jest dostępny tylko poprzez jawne
flaga trybu awaryjnego.

Kryteria ukończenia: schematy są czytelne, próba próbna nie powoduje zmiany osprzętu, globalna
oprawy obejmują obsługiwane i niejednoznaczne układy, dym ładujący
działa na wszystkich obsługiwanych systemach operacyjnych.

## Sprawdzanie zmian

Uruchomić:

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py --agent codex
python scripts/smoke_install.py --agent claude-code
```

Przetestuj korpus wyzwalacza na prawdziwym agencie, łącznie z pierwszym uruchomieniem umiejętności.
Strukturalny CI potwierdza kompletność korpusu, ale nie zastępuje obserwacji rozmów
modele. Dodaj żądania i wyniki do listy kontrolnej żądań ściągnięcia.

W celu ogólnej oceny wyzwalacza przygotuj zestaw ślepych prób i oceń reakcje selektora:

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

Selektor może wybrać wiele umiejętności lub żadną. Nie pokazuj mu
źródłowe pliki eval, oczekiwane etykiety, powody autora, podejrzenia błędów i
raporty z przeszłości. Napraw dostawcę/model, zapisz nieprzetworzone prognozy i
sprawdź każdy fałszywy wynik pozytywny/negatywny. Wzrost wyniku nie uzasadnia ekspansji
wyzwalacz, tworząc niejednoznaczność.

`evals/release-holdout-vN.json` — dowód wydania, który można tylko dołączyć. Nie czytaj lub
uruchom aktywne wstrzymanie podczas konfigurowania opisów. Opublikowane wersje
niezmienne: utwórz `vN+1`, zaktualizuj nazwę, ścieżkę i podsumowanie kanoniczne, zapisz
wszystkie wersje. Po zamrożeniu opisów uruchom wstrzymanie i porównaj z wartością bazową
ta sama wersja i konfiguracja selektora. Podsumowanie asercji musi być zgodne.
Zaakceptowany raport zostaje zapisany w `evals/baselines/`, a indeks katalogu zostaje zaktualizowany.
W przypadku selektora niedeterministycznego użyj liczby nieparzystej wynoszącej co najmniej trzy
niezależne ślepe biegi i głosowanie większością. Nie możesz powtarzać jednego biegu aż do skutku
lub odrzuć prawidłowe, nieudane obserwacje.

Kryteria ukończenia: Wszystkie polecenia są przekazywane w każdym obsługiwanym systemie operacyjnym i PR
lista kontrolna zawiera dowody dotyczące danej umiejętności.

## Zwolnij zabezpieczenie łańcucha

- Przypnij akcje GitHub z pełnym SHA i zostaw wersję w komentarzu.
  Aktualizacje SHA są sprawdzane przez Depabot.
- Wydaj `GITHUB_TOKEN` tylko niezbędne uprawnienia.
- Zbierz archiwa poprzez `scripts/build_release.py` i sprawdź `SHA256SUMS`.
- Opublikuj atesty artefaktów GitHub dla każdego zasobu i sprawdź je
  przez zespół `gh attestation verify <artifact> --repo kolabse/skills`.

- Nie zastępuj istniejącego zasobu. Powtarzający się przepływ pracy musi zostać potwierdzony
  identycznych bajtów lub zakończyć się błędem.
- Nie przesuwaj znaczników wersji; poprawka zostaje opublikowana w nowej wersji.

Kryteria ukończenia: znacznik wskazuje sprawdzone zatwierdzenie, dopasowanie zasobów
`SHA256SUMS`, zależności przepływu pracy są zabezpieczone przez niezmienne łącza.
