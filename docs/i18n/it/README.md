# kolabse/skills

[English](../../../README.md) | [Русский](../ru/README.md) | [Español](../es/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Português (Brasil)](../pt-BR/README.md) | [日本語](../ja/README.md) | Italiano | [한국어](../ko/README.md) | [简体中文](../zh-CN/README.md) | [Türkçe](../tr/README.md)

Questa è una traduzione italiana. In caso di discrepanze, fa fede la [versione inglese canonica](../../../README.md).

Skill riutilizzabili per agenti, mantenute da kolabse.

Distribuito con la [Apache License 2.0](../../../LICENSE). Copyright 2026 kolabse.

## Indice

- [Installare le skill](#installare-le-skill)
  - [Installare dai marketplace Git](#installare-dai-marketplace-git)
- [Aggiornare le skill installate](#aggiornare-le-skill-installate)
  - [Eseguire senza clonare il repository](#eseguire-senza-clonare-il-repository)
  - [Esaminare le installazioni globali](#esaminare-le-installazioni-globali)
- [Installare o aggiornare un plugin Codex per lo sviluppo locale](#installare-o-aggiornare-un-plugin-codex-per-lo-sviluppo-locale)
- [Skill disponibili](#skill-disponibili)
  - [Sviluppo e qualità del codice](#sviluppo-e-qualità-del-codice)
    - [`develop-with-test-first-evidence`](#develop-with-test-first-evidence-sperimentale)
    - [`review-code-changes`](#review-code-changes-sperimentale)
    - [`diagnose-software-defects`](#diagnose-software-defects-sperimentale)
    - [`resolve-git-conflicts`](#resolve-git-conflicts-sperimentale)
  - [Repository e consegna delle modifiche](#repository-e-consegna-delle-modifiche)
    - [`synchronize-git-repositories`](#synchronize-git-repositories)
    - [`verify-before-push`](#verify-before-push)
    - [`coordinate-code-documentation-repositories`](#coordinate-code-documentation-repositories-sperimentale)
    - [`execute-configured-gitflow-releases`](#execute-configured-gitflow-releases-sperimentale)
    - [`execute-verified-development-lifecycle`](#execute-verified-development-lifecycle-sperimentale)
  - [Conoscenza e continuità del progetto](#conoscenza-e-continuità-del-progetto)
    - [`maintain-work-log`](#maintain-work-log)
    - [`maintain-project-digest`](#maintain-project-digest-sperimentale)
    - [`sync-project-context`](#sync-project-context)
  - [Coordinamento e comunicazione](#coordinamento-e-comunicazione)
    - [`orchestrate-agent-work`](#orchestrate-agent-work-sperimentale)
    - [`synchronize-team-skills`](#synchronize-team-skills-sperimentale)
    - [`notify-via-telegram`](#notify-via-telegram)
  - [Infrastruttura e operazioni](#infrastruttura-e-operazioni)
    - [`operate-yandex-cloud`](#operate-yandex-cloud)
  - [Evoluzione della raccolta di skill](#evoluzione-della-raccolta-di-skill)
    - [`discover-skill-candidates`](#discover-skill-candidates-sperimentale)
    - [`release-skill-collection`](#release-skill-collection)
- [Composizioni supportate](#composizioni-supportate)
- [Aggiungere una skill](#aggiungere-una-skill)
- [Verificare un rilascio](#verificare-un-rilascio)

## Installare le skill

Installa una o più skill nel progetto corrente con la CLI multiagente
[`skills`](https://skills.sh):

```shell
npx skills@latest add kolabse/skills
```

La CLI rileva le cartelle in `skills/`, permette di selezionare le skill da
installare e le copia per gli agenti di programmazione selezionati. È un
programma di installazione esterno; questo repository non pubblica né esegue
un proprio pacchetto npm.

In alternativa, gli utenti Codex possono chiedere a `$skill-installer` di
installare una skill da questo repository, ad esempio da:

```text
https://github.com/kolabse/skills/tree/main/skills/operate-yandex-cloud
```

Per l'installazione non interattiva, scegli esplicitamente l'agente destinatario:

```shell
npx skills@1.5.22 add kolabse/skills --agent codex --copy -y
npx skills@1.5.22 add kolabse/skills --agent claude-code --copy -y
```

Per l'installazione nel progetto, chiedi all'agente: «Installa le skill
selezionate e inizializza i valori predefiniti mancanti del progetto senza
sostituire le nostre regole esistenti». Al termine dell'installazione esterna,
inizializza le regole Git per il tuo agente:

```shell
python .agents/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent codex --apply --yes --json
python .claude/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent claude-code --apply --yes --json
```

Le convenzioni mancanti assumono i valori `feature/`, `bugfix/`, `release/`,
`hotfix/` e i tipi di commit `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
I prefissi espliciti del progetto, i ruoli dei branch e i formati di commit
restano autorevoli. Non vengono creati branch persistenti né hook Git.
Gli aggiornamenti gestiti nell'ambito del progetto applicano questa stessa
inizializzazione per le skill pertinenti; gli aggiornamenti non confermati
si limitano a pianificarla.

Per un'installazione nel progetto, inizializza subito il contratto del ciclo
di vita quando i suoi valori predefiniti osservabili sono sufficienti
(usa il percorso del tuo agente):

```shell
python .agents/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent codex --apply --yes --json
python .claude/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent claude-code --apply --yes --json
```

Le installazioni da marketplace/plugin sono globali e non hanno una radice di
progetto attiva, quindi la skill esegue questa stessa inizializzazione al primo
utilizzo in un progetto.

Codex rileva le skill di progetto in `.agents/skills/` e le richiama come
`$skill-name`. Claude Code le rileva in `.claude/skills/` e le richiama come
`/skill-name`. Le istruzioni delle skill e gli script inclusi sono condivisi;
i file di regole e la sintassi di invocazione specifici dell'agente destinatario
vengono selezionati durante la configurazione.

Il repository è distribuito anche come plugin `kolabse-skills`, contenente
solo skill, per ChatGPT/Codex e Claude Code. Include ogni cartella in `skills/`.
L'installazione multiagente con `npx skills` rimane disponibile
indipendentemente dai due formati di plugin.

### Installare dai marketplace Git

Gli utenti Codex possono registrare il marketplace del repository e installare
l'intera raccolta con:

```shell
codex plugin marketplace add kolabse/skills --ref main
codex plugin add kolabse-skills@kolabse
```

Aggiorna l'istantanea Git e reinstalla la versione corrente del plugin con:

```shell
codex plugin marketplace upgrade kolabse
codex plugin add kolabse-skills@kolabse
```

Gli utenti Claude Code possono registrare lo stesso repository e installare
il plugin con:

```shell
claude plugin marketplace add kolabse/skills
claude plugin install kolabse-skills@kolabse
```

Aggiornalo esplicitamente con `claude plugin marketplace update kolabse`,
oppure abilita l'aggiornamento automatico del marketplace in Claude Code.
Avvia una nuova sessione dell'agente dopo l'installazione o l'aggiornamento
affinché rilevi l'insieme attuale di skill.

I cataloghi dei marketplace sono
[`.agents/plugins/marketplace.json`](../../../.agents/plugins/marketplace.json) e
[`.claude-plugin/marketplace.json`](../../../.claude-plugin/marketplace.json).
I relativi payload dei plugin sono descritti da
[`.codex-plugin/plugin.json`](../../../.codex-plugin/plugin.json) e
[`.claude-plugin/plugin.json`](../../../.claude-plugin/plugin.json).
Entrambi i cataloghi recuperano il repository canonico `kolabse/skills` da
`main`; il versionamento dei rilasci resta autorevole nei manifesti dei plugin.

I materiali per la pubblicazione negli elenchi pubblici sono mantenuti insieme
al sorgente: [assistenza](SUPPORT.md), [informativa sulla privacy](PRIVACY.md),
[condizioni d'uso](TERMS.md) e il riproducibile
[pacchetto di candidatura ai marketplace](../../../docs/marketplace-submissions/).
La pubblicazione in un elenco ufficiale resta un'azione dei manutentori
soggetta a revisione; l'installazione dai marketplace Git non richiede
l'approvazione dell'elenco.

Durante i test, Claude Code può caricare direttamente un rilascio estratto o un
checkout attendibile con `claude --plugin-dir <collection-root>`. Per il normale
uso personale o di progetto, preferisci il marketplace Git o il comando
esplicito `npx skills ... --agent claude-code` indicato sopra. Claude Code legge
`CLAUDE.md`, non `AGENTS.md`; quando un progetto ha già regole condivise in
`AGENTS.md`, un `CLAUDE.md` minimo contenente `@AGENTS.md` mantiene un unico
documento canonico delle regole.

## Aggiornare le skill installate

La CLI `skills` registra la fonte GitHub e un hash del contenuto in
`skills-lock.json`. Aggiorna ogni installazione di progetto dalla fonte registrata:

```shell
npx skills@1.5.22 update -p -y
```

Aggiorna una skill o le installazioni globali con:

```shell
npx skills@1.5.22 update verify-before-push -p -y
npx skills@1.5.22 update -g -y
```

Un lock `kolabse/skills` senza qualificazioni segue il branch predefinito del
repository; non fissa un rilascio della raccolta. Non modificare i file copiati
in `.agents/skills/`, perché un aggiornamento potrebbe sostituirli. La
configurazione del progetto e dell'utente resta fuori dalle cartelle delle
skill installate.

Da un checkout clonato o da un archivio di rilascio, aggiorna e migra la
configurazione di progetto supportata in un'unica operazione esplicita:

```shell
python scripts/manage_installed_skills.py update --project-path . --yes --migrate
python scripts/manage_installed_skills.py doctor --project-path . --json
```

Visualizza in anteprima la selezione esatta senza richiamare il programma di
installazione esterno o modificare la configurazione:

```shell
python scripts/manage_installed_skills.py plan --project-path . --json
```

Il piano riporta identità della fonte, versioni attuali e di destinazione,
provenienza, candidati alla migrazione e azioni `update`, `unchanged`,
`adopt-and-update` o `blocked`. Il suo schema è
`schemas/manager-plan.schema.json`. Aggiungi `--json` a `update`; gli esiti
di aggiornamento e migrazione seguono `schemas/manager-result.schema.json`.

Senza nomi, il gestore risolve le skill kolabse installate dal lock del progetto
e passa esplicitamente quei nomi alla CLI esterna; le skill di progetto non
pertinenti non fanno mai parte dell'aggiornamento. Gli aggiornamenti globali
richiedono nomi espliciti di skill della raccolta. Gli aggiornamenti di progetto
terminano con la stessa diagnosi di `doctor`, che blocca in caso di incertezza
o errore. Quando `execute-verified-development-lifecycle` fa parte di un
aggiornamento di progetto, il gestore inizializza anche la configurazione
mancante dove i fatti del progetto sono sufficienti e restituisce un esito
di configurazione `created`, `configured` o `blocked`.

Aggiungi `--include-user-config` solo quando deve essere migrata anche la
configurazione utente Telegram. `status` e `doctor` sono di sola lettura.
`migrate` modifica solo file di configurazione già esistenti; non configura
skill inutilizzate. Ogni skill installata contiene `collection-metadata.json`,
quindi `status` ne riporta la versione della raccolta anche se il formato del
lock esterno non ha un campo versione. Riporta anche `provenance_status`:
`verified` richiede sia i metadati della raccolta sia una fonte del lock GitHub
canonica o locale verificata tramite contenuto; `legacy-unverified` identifica
un'installazione precedente ai metadati; `mismatch` non viene mai aggiornato.
Un checkout può essere rinominato perché l'identità locale deriva dal manifesto
del plugin, dal catalogo e dai contenuti delle skill, non dal nome della directory.

Adotta un'installazione precedente alla v1.2 e priva di metadati solo dopo
averne esaminato la fonte segnalata:

```shell
python scripts/manage_installed_skills.py status --project-path . --json
python scripts/manage_installed_skills.py update --project-path . --yes --adopt-legacy
```

L'opzione di adozione non legittima file arbitrari: la fonte deve già
normalizzarsi in `kolabse/skills` o superare la validazione del checkout locale,
e la normale diagnosi post-aggiornamento deve verificare i metadati installati.
La CLI esterna non aggiorna sul posto i lock di sviluppo `sourceType: local`.
Il gestore tratta questa mancata operazione della CLI come un errore; aggiungi
nuovamente quelle skill dalla fonte locale con le selezioni originali di
`--skill` e `--agent`.

### Eseguire senza clonare il repository

Scarica `scripts/bootstrap_update.py` da un rilascio attendibile o da questo
repository, poi lascia che individui l'ultimo rilascio stabile, verifichi lo ZIP
di rilascio rispetto a `SHA256SUMS` e alla provenienza della build GitHub ed
esegua il gestore da un'estrazione temporanea isolata:

```shell
python bootstrap_update.py doctor --json
python bootstrap_update.py plan --json
python bootstrap_update.py update --yes --migrate --json
```

Usa `--release v1.15.0` per fissare una versione. Il bootstrap richiede `gh` per
verificare le attestazioni e rimuove la propria directory temporanea al termine.
Per una cache offline, fornisci sia `--offline-archive` sia
`--offline-checksums`. La verifica della provenienza rimane obbligatoria quando
`gh` può raggiungere GitHub. `--allow-unattested-offline` è una modalità degradata
esplicita: verifica solo il checksum nella cache e va usata esclusivamente per
artefatti trasferiti attraverso un canale attendibile indipendente. Per
tornare indietro, seleziona un rilascio precedente e usa la procedura di
ripristino esistente; le migrazioni della configurazione restano solo in avanti.

### Esaminare le installazioni globali

Lo stato globale supportato è deliberatamente limitato al lock condiviso v3
`~/.agents/.skill-lock.json`. I payload installati si trovano in
`~/.agents/skills` per Codex e in `~/.claude/skills` per Claude Code. Il gestore
non esamina altre directory utente. Codex resta il predefinito; passa
`--agent claude-code` per il layout dei payload Claude:

```shell
python scripts/manage_installed_skills.py status --scope global --json
python scripts/manage_installed_skills.py doctor --scope global --json
python scripts/manage_installed_skills.py plan verify-before-push --scope global --json
python scripts/manage_installed_skills.py update verify-before-push --scope global --yes --json
python scripts/manage_installed_skills.py status --scope global --agent claude-code --json
```

Usa `--global-root` per esaminare in sola lettura un layout compatibile di test
o esplicitamente spostato. Le radici spostate non possono essere aggiornate
perché la CLI esterna non può indirizzarle. I formati di lock sconosciuti sono
segnalati senza modifiche.

Per ripristinare i file delle skill, esegui prima un backup della configurazione
del progetto e dell'utente, poi reinstalla il tag di rilascio richiesto con le
stesse skill e gli stessi agenti destinatari dell'installazione originale,
ad esempio:

```shell
npx skills@1.5.22 add kolabse/skills@v1.1.0 --skill verify-before-push --agent codex --copy -y
```

Le migrazioni della configurazione procedono solo in avanti, a meno che un
rilascio non documenti esplicitamente una retrocessione. Ripristinare file delle
skill precedenti non retrocede la configurazione; ripristina il backup
corrispondente quando il rilascio precedente non può leggere il formato più recente.

## Installare o aggiornare un plugin Codex per lo sviluppo locale

Per lo sviluppo locale del plugin, crea o aggiorna la voce predefinita del
marketplace personale, copia il plugin nella directory locale dei plugin,
aggiungi un identificatore di invalidazione della cache Codex e attivalo:

```shell
python scripts/install_personal_plugin.py --activate
```

Il programma di installazione preserva le altre voci del marketplace personale
e non modifica il manifesto del repository. È un percorso di sviluppo
alternativo, non la normale installazione da marketplace Git. Eseguilo di nuovo
dopo aver aggiornato il checkout, poi avvia una nuova attività Codex per caricare
le skill aggiornate. Usa `--json` per registrare versione installata, percorso
del plugin, percorso del marketplace e nome del marketplace.

## Skill disponibili

Le skill stabili e le aggiunte sperimentali sono identificate in
`skill-catalog.json`. I loro percorsi di configurazione per i progetti, limiti
di sicurezza e interfacce di comando documentate seguono la politica di
compatibilità in [CONTRIBUTING.md](CONTRIBUTING.md).

Ogni voce del catalogo dichiara ora ambito di configurazione, comando di stato
JSON di sola lettura, capacità, prerequisiti e integrazioni facoltative. Le
skill con stato dichiarano anche un comando di configurazione idempotente;
le configurazioni JSON/YAML versionate pubblicano uno schema JSON e un comando
di migrazione accanto alla skill.

Il catalogo è raggruppato per scopo principale rivolto all'utente, nell'ordine
di priorità riportato sotto. Ogni skill ha esattamente una categoria
principale. Tag indipendenti descrivono fase del ciclo di vita, ambito,
comportamento e integrazioni; lo stato di maturità resta indipendente.
Le assegnazioni autorevoli leggibili dalle macchine e il vocabolario controllato
si trovano in [`skill-catalog.json`](../../../skill-catalog.json), validato
rispetto a [`schemas/skill-catalog.schema.json`](../../../schemas/skill-catalog.schema.json).

Gli assi dei tag controllati sono:

- fase del ciclo di vita: `prepare`, `investigate`, `implement`, `verify`,
  `publish`, `operate`, `document` e `handoff`;
- ambito: `project`, `repository`, `multi-repository`, `workstation`,
  `external-service` e `skill-collection`;
- comportamento: `read-only-planning`, `mutation`, `evidence-producing`,
  `orchestration` e `notification`;
- integrazione: `git`, `github`, `telegram`, `google-drive` e `yandex-cloud`.

### Sviluppo e qualità del codice

#### `develop-with-test-first-evidence` (sperimentale)

Implementa comportamenti attraverso cicli red-green-refactor sostenuti da evidenze.

**Cosa fa:**

- registra, prima dell'implementazione, un test mirato che fallisce per il
  motivo comportamentale previsto;
- lega i risultati positivi dei test mirati e più ampi allo stato finale della modifica;
- valida evidenze persistenti con lo schema e lo strumento ausiliario inclusi.

**Cosa non fa:**

- fabbricare un risultato negativo rompendo comportamenti non pertinenti;
- chiamare sviluppo test-first i test scritti a posteriori;
- nascondere errori preesistenti, ambientali o dello stato finale.

**Come richiamarla:**

```text
$develop-with-test-first-evidence Implement this behavior with a recorded red-green-refactor cycle.
```

#### `review-code-changes` (sperimentale)

Esamina una modifica definita alla ricerca di difetti concreti e correggibili
di correttezza, sicurezza, affidabilità e compatibilità.

**Cosa fa:**

- determina una baseline esatta e lo stato modificato;
- riporta rilievi sostenuti da evidenze con impatto, condizione di attivazione,
  priorità e posizioni circoscritte;
- rende esplicite l'incertezza e le lacune significative nei test.

**Cosa non fa:**

- segnalare preferenze stilistiche o supposizioni prive di supporto come difetti;
- implementare i rilievi, pubblicare commenti o approvare una revisione senza
  autorizzazione separata;
- sostituire una revisione circoscritta con una spiegazione generale del codice.

**Come richiamarla:**

```text
$review-code-changes Review this branch against its declared baseline and report actionable findings.
```

#### `diagnose-software-defects` (sperimentale)

Indaga guasti e regressioni per produrre una spiegazione causale supportata o
ipotesi ordinate per plausibilità.

**Cosa fa:**

- circoscrive il sintomo e, quando possibile, lo riproduce in sicurezza;
- verifica ipotesi concorrenti con evidenze pertinenti;
- riporta causa principale, condizioni concorrenti, estensione dell'impatto,
  livello di confidenza e piano di verifica della correzione.

**Cosa non fa:**

- dedurre causalità dalla correlazione;
- modificare la produzione o scartare evidenze di fallimento;
- implementare una correzione speculativa quando è stata richiesta solo la diagnosi.

**Come richiamarla:**

```text
$diagnose-software-defects Diagnose this regression and distinguish evidence from hypotheses.
```

#### `resolve-git-conflicts` (sperimentale)

Risolve semanticamente conflitti di merge, rebase o cherry-pick autorizzati,
preservando il lavoro non pertinente.

**Cosa fa:**

- esamina l'operazione attiva, la base, entrambi i lati e ogni percorso non integrato;
- riconcilia solo i conflitti il cui comportamento combinato previsto è compreso;
- valida i percorsi risolti e rende esplicito il passaggio Git ancora necessario.

**Cosa non fa:**

- trattare la normale divergenza tra repository come un'attività di conflitto tra file;
- eseguire automaticamente stash, reset, abort, continue, push forzati o
  aggiungere all'area di staging percorsi non pertinenti;
- tirare a indovinare di fronte a decisioni ambigue su file generati, binari,
  schemi o prodotto.

**Come richiamarla:**

```text
$resolve-git-conflicts Resolve the active merge conflicts path by path and validate the result.
```

### Repository e consegna delle modifiche

#### `synchronize-git-repositories`

Accerta lo stato remoto attuale senza sovrascrivere il lavoro locale.

**Cosa fa:**

- individua solo i repository pertinenti all'attività e recupera gli
  aggiornamenti dai loro remoti tracciati;
- aggiorna in fast-forward i branch puliti che sono soltanto indietro;
- segnala stati con modifiche locali, in anticipo, divergenti, con HEAD
  scollegato, senza upstream tracciato e con operazioni in corso;
- pubblica un branch di funzionalità autorizzato dal `main` corrente verificato
  prima della prima modifica, quando la politica del progetto lo richiede.

**Cosa non fa:**

- eseguire automaticamente stash, reset, rebase, merge, clean, cambio di branch
  o push forzati;
- nascondere la divergenza o considerare un fetch riuscito come prova
  dell'aggiornamento del branch locale;
- esaminare o aggiornare repository non pertinenti.

**Come richiamarla:**

```text
$synchronize-git-repositories Configure this project's repository synchronization policy.
```

#### `verify-before-push`

Lega i controlli dichiarati dal progetto allo stato Git esatto da pubblicare.

**Cosa fa:**

- configura una politica di verifica di proprietà del repository fuori dalla
  cartella della skill installata;
- esegue i controlli dichiarati e registra evidenze per commit, alberi di lavoro,
  stato upstream e configurazione di verifica esatti;
- blocca l'operazione quando le evidenze richieste per la protezione mancano,
  sono fallite, malformate o obsolete.

**Cosa non fa:**

- bloccare repository non pertinenti e non coperti dalla politica;
- analizzare comandi shell arbitrari o installare un hook specifico di un IDE o agente;
- considerare attuale un controllo riuscito su uno stato Git precedente.

**Come richiamarla:**

```text
$verify-before-push Configure this project's verification policy and checks.
```

#### `coordinate-code-documentation-repositories` (sperimentale)

Coordina una singola modifica di progetto verificabile quando implementazione
e documentazione canonica risiedono in repository Git separati.

**Cosa fa:**

- determina i ruoli dei repository di implementazione e documentazione
  dichiarati dal progetto;
- crea un piano di sola lettura legato a entrambi i commit iniziali e alle
  fonti autorevoli della documentazione;
- richiede evidenze documentali per gli argomenti configurati, come requisiti,
  comportamento, validazione, impatto operativo e limiti;
- verifica l'identità di entrambi i commit pubblicati, le evidenze di
  validazione e la tracciabilità tra repository prima di dichiarare il
  completamento congiunto.

**Cosa non fa:**

- dedurre i ruoli dei repository dai nomi delle directory o dei repository;
- sostituire la documentazione canonica con un riepilogo giornaliero;
- modificare, creare commit, eseguire push o merge oppure riparare autonomamente
  repository con modifiche locali e divergenti;
- dichiarare concordanza semantica solo perché esistono i file di
  documentazione attesi.

**Come richiamarla:**

```text
$coordinate-code-documentation-repositories Implement this change across the declared code and canonical documentation repositories and verify both published outcomes.
```

#### `execute-configured-gitflow-releases` (sperimentale)

Esegue percorsi di rilascio standard e hotfix in base a un contratto GitFlow
dichiarato dal progetto.

**Cosa fa:**

- ricava sviluppo, produzione, spazio dei nomi hotfix, remoto, controlli
  obbligatori e politica del percorso predefinito dalla configurazione
  versionata del progetto;
- congela un piano di sola lettura legato al commit sorgente e alle identità
  dei branch remoti;
- applica gli stessi controlli comuni dichiarati ai percorsi standard e hotfix;
- verifica la pubblicazione in produzione revisionata, le evidenze di
  distribuzione e la reintegrazione obbligatoria dell'hotfix nella linea di sviluppo.

**Cosa non fa:**

- dedurre nomi convenzionali di branch o usare hotfix come percorso predefinito;
- supportare la consegna trunk-based o la catena di rilascio specializzata di
  questa raccolta;
- eseguire push diretto alla produzione protetta, aggirare controlli,
  riscrivere la cronologia o riparare silenziosamente la divergenza;
- considerare del tutto completato un hotfix di produzione prima di averne
  verificato la reintegrazione.

**Come richiamarla:**

```text
$execute-configured-gitflow-releases Run the standard release route declared by this project and verify the resulting production identity.
$execute-configured-gitflow-releases Run an explicit hotfix release and verify its reintegration into the declared development line.
```

#### `execute-verified-development-lifecycle` (sperimentale)

Pianifica e verifica un percorso dichiarato dal progetto, dalla preparazione
della funzionalità all'integrazione revisionata nello sviluppo, all'osservazione
della consegna, alla documentazione e alla pulizia dimostrata sicura.

**Cosa fa:**

- congela un piano legato a un digest prima delle modifiche e avanza attraverso
  punti di controllo ordinati usando evidenze conservate;
- crea una configurazione di progetto prudente durante un aggiornamento gestito
  o al primo utilizzo quando radici dei repository, upstream tracciati,
  controlli e documentazione sono osservabili, e riporta ogni valore
  predefinito applicato;
- verifica i controlli relativi a branch di funzionalità prima delle modifiche,
  test-first, verifica preliminare dell'ambito modificato, revisione, push
  dello stato esatto, pipeline, documentazione, integrazione nello sviluppo,
  produzione delegata, consegna, smoke test, notifica e pulizia;
- torna a un punto di controllo dichiarato dopo un errore e invalida le
  evidenze successive obsolete.

**Cosa non fa:**

- indovinare adattatori specifici del fornitore, ruoli dei repository, politica
  di consegna o autorizzazione quando le evidenze di progetto sono ambigue;
- eseguire autonomamente push, aprire o integrare revisioni, distribuire,
  notificare, modificare documentazione o eliminare risorse;
- eseguire la consegna in produzione, che resta delegata al flusso di rilascio
  approvato, come `$execute-configured-gitflow-releases`.

Installa e configura prima le skill richieste: `$synchronize-git-repositories`,
`$develop-with-test-first-evidence`, `$verify-before-push` e
`$review-code-changes`. Un contratto del ciclo di vita di versione 1, di
proprietà del progetto e mancante, viene inizializzato dai fatti osservabili
del progetto prima del primo piano; esamina e affina i valori predefiniti
riportati quando il progetto dichiara una politica più specifica.
Installa le skill facoltative solo quando il progetto ne abilita i rispettivi
punti di controllo: `$orchestrate-agent-work`, `$diagnose-software-defects`,
`$resolve-git-conflicts`, `$coordinate-code-documentation-repositories`,
`$maintain-work-log`, `$maintain-project-digest`, `$notify-via-telegram` e
`$execute-configured-gitflow-releases`.

**Come richiamarla:**

```text
$execute-verified-development-lifecycle Plan and verify this change through the project's configured development lifecycle.
```

### Conoscenza e continuità del progetto

#### `maintain-work-log`

Mantiene il diario datato canonico del progetto in `docs/reports/work-log.md`.

**Cosa fa:**

- registra modifiche sostanziali, operazioni, diagnosi, decisioni, verifiche,
  impedimenti e risultati di ripristino;
- preserva il formato esistente del diario del progetto;
- ricostruisce la cronologia mancante dalle evidenze Git e delle attività di
  progetto disponibili.

**Cosa non fa:**

- attivarsi per il lavoro ordinario, salvo richiesta dell'utente o della
  politica del progetto;
- scrivere segreti, log applicativi, rilevazioni del tempo o note personali;
- dichiarare eventi non sostenibili dalle evidenze disponibili.

**Come richiamarla:**

```text
$maintain-work-log Configure this project to maintain its dated work log.
```

#### `maintain-project-digest` (sperimentale)

Mantiene nella documentazione del progetto un riepilogo giornaliero, rivolto
agli utenti, delle modifiche completate.

**Cosa fa:**

- raggruppa le modifiche completate sotto la data odierna come nuove capacità,
  miglioramenti, correzioni, sicurezza, documentazione o importanti cambiamenti
  di comportamento;
- scrive risultati brevi e non tecnici e omette le categorie vuote;
- mantiene per prime le date più recenti e lascia invariate tutte le precedenti;
- usa un piano legato al contenuto, un lock cooperativo, sostituzione atomica
  e rilevamento dei duplicati affinché più sviluppatori possano contribuire
  in sicurezza nello stesso giorno.

**Cosa non fa:**

- scegliere o creare una posizione per la documentazione quando il progetto
  non la identifica univocamente;
- registrare piani, esperimenti falliti, attività interne di implementazione
  o benefici per l'utente non supportati da evidenze;
- sostituire il diario tecnico, le note di rilascio delle versioni o un
  changelog convenzionale;
- riscrivere periodi storici del riepilogo durante un normale aggiornamento
  dello stesso giorno.

**Come richiamarla:**

```text
$maintain-project-digest Add today's completed user-visible changes to the project digest.
```

#### `sync-project-context`

Sincronizza tra computer lo stato privato, depurato dai dati sensibili, del
progetto e di continuazione delle singole conversazioni. La skill è stabile
dopo che due esecuzioni indipendenti su dispositivi reali con Google Drive
hanno superato il suo controllo deterministico di promozione.

**Cosa fa:**

- memorizza punti di ripristino immutabili in una cartella sincronizzata
  approvata o nel Google Drive collegato, con configurazione locale alla
  macchina esterna al repository;
- usa per impostazione predefinita il Google Drive collegato per le richieste
  di sincronizzazione non qualificate, preservando un backend esistente e
  richiedendo consenso esplicito prima di usare una cartella sincronizzata locale;
- su un nuovo computer individua una mappatura Google Drive esistente verificata
  tramite l'impronta del repository prima di creare qualsiasi cartella remota,
  e si blocca in caso di elenchi incompleti, visibilità non attendibile o
  corrispondenze duplicate;
- mantiene un flusso opaco per ogni attività di progetto: una baseline
  dettagliata seguita da brevi differenze, titoli visibili esatti, decisioni,
  verifiche, domande aperte, prossimi passi e impronte Git;
- salva, ripristina o pianifica bidirezionalmente tutte le attività di progetto
  recenti e fissate, saltando quelle invariate o attive e mostrando
  esplicitamente i conflitti;
- valida le istantanee scaricate, rilegge i caricamenti, impedisce ripristini
  tra progetti diversi e rifiuta schemi che indicano segreti con elevata confidenza;
- registra un manifesto dell'ambiente separato per regole, skill, plugin e
  impostazioni scalari sicure dichiarati che Git non fornisce già.

**Cosa non fa:**

- copiare file sorgente, diff, trascrizioni grezze, ragionamenti nascosti,
  credenziali, token OAuth o installazioni di skill/plugin;
- duplicare regole o dipendenze già veicolate da Git;
- sovrascrivere silenziosamente regole di destinazione gestite da Git:
  l'applicazione può solo creare un `AGENTS.md` o `CLAUDE.md` mancante e non
  tracciato, selezionato per l'agente attivo dopo un piano esplicito;
- includere nomi di branch o percorsi di file nella modalità solo metadati;
  i titoli visibili delle attività restano intenzionalmente inclusi.

Codex Desktop supporta i flussi documentati di individuazione in blocco delle
attività, creazione, rinomina e connettore Google Drive. Claude Code può usare
il nucleo portabile per punti di ripristino, archiviazione in cartelle locali
e riconciliazione dell'ambiente, ma il suo archivio di sessioni non viene
esaminato e le operazioni in blocco sulle attività riservate a Codex vengono
bloccate come non supportate.

**Come richiamarla:**

Configura ogni computer una sola volta:

```text
$sync-project-context Configure this clone in metadata-only mode. Use connected Google Drive by default unless I explicitly request another approved channel.
```

Poi usa comandi per singola attività o in blocco, ad esempio:

```text
$sync-project-context Save the current task state.
$sync-project-context Restore all project tasks on this computer.
$sync-project-context Synchronize all project tasks bidirectionally and show conflicts before applying changes.
```

In Claude Code, sostituisci il prefisso `$` di questi esempi con `/`.

### Coordinamento e comunicazione

#### `orchestrate-agent-work` (sperimentale)

Coordina subagenti esplicitamente autorizzati mantenendo la responsabilità del
risultato integrato.

**Cosa fa:**

- suddivide il lavoro parallelo in incarichi circoscritti e non sovrapposti;
- monitora e riconcilia i risultati degli agenti rispetto ai vincoli condivisi;
- verifica il risultato combinato prima di dichiarare il completamento.

**Cosa non fa:**

- delegare senza autorizzazione dell'utente o delle istruzioni del progetto
  all'uso di subagenti;
- trasferire a un altro agente l'autorità di approvazione, segreti, pulizia
  distruttiva o modifiche esterne non approvate;
- considerare sottoattività completate indipendentemente come prova della
  riuscita dell'integrazione.

**Come richiamarla:**

```text
$orchestrate-agent-work Delegate these independent subtasks to agents and verify the integrated result.
```

#### `synchronize-team-skills` (sperimentale)

Mantiene le skill degli agenti nell'ambito del progetto di ogni membro del team
allineate con un unico manifesto revisionato nella documentazione del progetto.

**Cosa fa:**

- crea o legge `team-agent-skills.md` in una radice di documentazione approvata;
- confronta le skill Codex e Claude Code dichiarate con copie di progetto verificate;
- segnala stati mancanti, obsoleti, più recenti, non verificati, con override
  di progetto ed extra preservati senza modificare l'ambiente;
- costruisce un piano di installazione legato al digest del manifesto per una
  versione fissata della raccolta;
- installa solo l'insieme revisionato dopo l'approvazione, poi verifica lo
  stato osservabile.

**Cosa non fa:**

- trasformare automaticamente lo stato accidentale di una postazione in
  politica del team;
- memorizzare segreti, configurazione utente, percorsi della macchina o
  autenticazione dei plugin;
- rimuovere skill aggiuntive, retrocedere copie più recenti o modificare
  installazioni globali;
- dichiarare che un'attività dell'agente in corso abbia ricaricato skill appena
  installate.

**Come richiamarla:**

```text
$synchronize-team-skills Check this project's installed skills against the reviewed team manifest.
$synchronize-team-skills Align my project skills with the team documentation after showing the plan.
$synchronize-team-skills Add maintain-project-digest to the reviewed team skill set.
```

#### `notify-via-telegram`

Invia tramite Telegram aggiornamenti sul ciclo di vita delle attività lunghe
degli agenti.

**Cosa fa:**

- segnala avvii, traguardi, risultati intermedi, problemi, impedimenti e completamento;
- valida interattivamente il bot e aiuta a individuare una chat di destinazione;
- fornisce per Codex Desktop su Windows un modulo di primo utilizzo con campi
  mascherati e adatti a incollare i valori;
- memorizza le credenziali nella directory di configurazione utente e invia
  una notifica di prova durante la configurazione;
- supporta una chat o un argomento di forum separato per progetto, con una
  scelta esplicita tra invio globale più progetto e invio al solo progetto;
- esporta valori di instradamento del progetto privi di segreti per la
  riconciliazione tramite `sync-project-context`;
- funziona con la libreria standard di Python 3 su Windows, macOS e Linux.

**Cosa non fa:**

- inserire il token del bot nella conversazione, nella cronologia shell o nel
  repository;
- copiare tra computer il token globale del bot o lo stato di autenticazione Telegram;
- inviare notifiche quando l'utente chiede di mantenere gli aggiornamenti
  nell'attività corrente;
- fungere da framework generico per lo sviluppo di bot Telegram.

**Come richiamarla:**

```text
$notify-via-telegram Configure Telegram notifications for long tasks.
$notify-via-telegram Configure this project to notify its team chat only, instead of the global destination.
```

### Infrastruttura e operazioni

#### `operate-yandex-cloud`

Gestisce l'infrastruttura Yandex Cloud esplicitamente configurata e limitata
all'ambito del progetto.

**Cosa fa:**

- memorizza gli ID Cloud/Folder condivisi nella configurazione di progetto e
  il profilo `yc` della postazione nella configurazione locale ignorata da Git;
- rileva gli strumenti necessari, controlla le versioni minime ed esegue una
  verifica preliminare del contesto di sola lettura;
- supporta flussi circoscritti per CLI, SSH, Terraform, Ansible, Helm,
  Kubernetes, distribuzione, database, archiviazione, DNS, monitoraggio,
  backup e incidenti;
- fornisce output JSON e strumenti ausiliari Python multipiattaforma.

**Cosa non fa:**

- dedurre Yandex Cloud da richieste generiche di SSH, Kubernetes, Terraform o
  distribuzione prive di contesto sul fornitore;
- memorizzare credenziali nella configurazione condivisa del progetto;
- applicare una modifica prima di aver accertato destinazione, contesto e
  autorizzazione.

**Come richiamarla:**

```text
$operate-yandex-cloud Configure this project for Yandex Cloud operations.
```

### Evoluzione della raccolta di skill

#### `discover-skill-candidates` (sperimentale)

Individua idee per skill riutilizzabili in evidenze circoscritte di progetto e
di contesto, senza creare una skill.

**Cosa fa:**

- inventaria file `AGENTS.md` circoscritti e relativi al progetto con
  provenienza Git e a livello di riga;
- facoltativamente inventaria documentazione di progetto, file selezionati,
  cronologia Git circoscritta, metadati strutturali e riepiloghi confermati
  dall'utente da conversazioni disponibili o passaggi di consegne di
  `sync-project-context`;
- classifica le proposte come raccomandate, da approfondire o rifiutate e le
  confronta con i cataloghi esistenti;
- propone proattivamente ogni candidato idoneo per un contributo sicuro a
  `kolabse/skills`, per la creazione locale o per un rinvio;
- esporta un'idea selezionata come pacchetto di contributo depurato dai dati
  sensibili e legato a un digest, validabile indipendentemente dai manutentori.

**Cosa non fa:**

- modificare le regole di progetto o creare lo scheletro, pubblicare o installare
  una skill;
- enumerare conversazioni, acquisire trascrizioni grezze o esaminare ampiamente
  il codice sorgente;
- esportare regole grezze, percorsi locali, segreti, URL o indirizzi email;
- promuovere convenzioni puramente normative, mutevoli, sensibili o una tantum
  come flussi riutilizzabili senza revisione.

**Come richiamarla:**

```text
$discover-skill-candidates Analyze this project's local rules and prepare an evidence-backed backlog of reusable skill ideas without creating anything.
```

#### `release-skill-collection`

Pianifica, verifica, sottopone ad audit ed esegue la pulizia dei rilasci
deterministici della raccolta di skill.

**Cosa fa:**

- controlla versioni, preparazione del changelog, stato del repository, test,
  sicurezza, archivi deterministici e checksum;
- valida evidenze legate ai commit per holdout, agenti destinatari, piattaforme,
  revisione e controlli locali;
- sottopone ad audit artefatti GitHub immutabili, manifesti, checksum e attestazioni;
- dimostra, prima della pulizia, se i branch temporanei sono integrati, hanno
  un albero identico o sono equivalenti per patch;
- applica una pulizia esplicitamente confermata solo a partire da un piano
  sicuro invariato e da un audit del rilascio pubblicato con digest valido.

**Cosa non fa:**

- dedurre il permesso di creare commit o tag, eseguire push, avviare workflow
  o pubblicare artefatti;
- spostare un tag esistente o sostituire artefatti pubblicati;
- eliminare branch in base ai soli nomi, a un piano obsoleto o a un rilascio
  non sottoposto ad audit.

**Come richiamarla:**

```text
$release-skill-collection Plan and verify release vX.Y.Z of this skill collection, but do not publish it yet.
```

## Composizioni supportate

Il catalogo definisce tre flussi ordinati riutilizzabili:

- `protected-push`: sincronizza i repository, poi produce evidenze di verifica
  attuali; diario di lavoro e notifica Telegram sono facoltativi.
- `yandex-cloud-operation`: sincronizza i repository, poi esegue l'operazione
  cloud circoscritta; verifica, diario di lavoro e notifica Telegram sono
  facoltativi quando la politica del progetto li abilita.
- `skill-collection-release`: sincronizza il repository, pianifica e verifica
  localmente il rilascio della raccolta, poi associa le evidenze pre-push;
  diario di lavoro e notifica Telegram sono facoltativi.

I passaggi obbligatori bloccano in caso di incertezza o errore. Registrazione
e notifica facoltative segnalano i propri errori senza cambiare il risultato
osservato dell'operazione primaria. Determina un piano esatto con
`scripts/compose_skills.py`; passa `--evidence` con un documento legato a un
digest conforme a `schemas/composition-evidence.schema.json` per verificare
l'ordine dei passaggi, i risultati richiesti e i fallimenti facoltativi non
bloccanti. Il risultato verificato segue `schemas/composition-result.schema.json`.

## Aggiungere una skill

Segui [CONTRIBUTING.md](CONTRIBUTING.md) e parti da
[`templates/skill-template.md`](../../../templates/skill-template.md). Ogni
skill deve avere una voce corrispondente in `skill-catalog.json` che registri
responsabile, piattaforme, stato, licenza e provenienza. Mantieni la
configurazione specifica del progetto fuori dalla cartella della skill
installata affinché gli aggiornamenti non possano sovrascriverla.

Non aggiungere un programma di installazione a livello di repository per una
singola skill. Quando la raccolta richiede installazione e aggiornamenti
gestiti tra ChatGPT e Codex, distribuiscila come plugin OpenAI in aggiunta a
questo layout multiagente.

Esegui localmente i controlli della raccolta con:

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py
```

Prepara una suite cieca delle attivazioni per un agente o un modello selettore con:

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
```

La suite contiene solo nomi delle skill, descrizioni pubbliche, ID opachi dei
casi e prompt. Omette etichette attese e motivazioni degli autori. Un selettore
restituisce JSON rigoroso che elenca ogni skill selezionata per ciascun caso;
assegna un punteggio alle osservazioni con:

```shell
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

Usa `run` con un comando dopo `--` per richiamare un selettore che legge la
suite dallo standard input e scrive le predizioni sullo standard output.
Mantieni le credenziali del fornitore fuori dagli argomenti dei comandi.
La directory ignorata `.trigger-evals/` mantiene per impostazione predefinita
suite generate, predizioni e rapporti fuori dai commit. Le grandi suite di
sviluppo sono inviate per impostazione predefinita in lotti di 64 casi legati
a un digest, così le risposte lunghe in JSON rigoroso non troncano gli ID
opachi dei casi. Regola il limite con `--batch-size` senza esporre al selettore
le etichette attese.

Prima di un rilascio, esegui l'holdout versionato separatamente e vincolato da
digest senza usarlo per affinare le descrizioni durante lo sviluppo:

```shell
python scripts/trigger_evals.py prepare \
  --corpus release-holdout \
  --output .trigger-evals/release-holdout.json
```

Confronta un rapporto candidato con un rapporto prodotto per la stessa versione
dell'holdout:

```shell
python scripts/trigger_evals.py compare \
  --candidate .trigger-evals/candidate-report.json \
  --markdown-output .trigger-evals/comparison.md
```

Il confronto blocca l'operazione quando i digest delle asserzioni differiscono
o quando accuratezza complessiva, precisione, richiamo o una metrica per skill
scendono oltre i limiti configurati. Per impostazione predefinita usa la
baseline pubblicata indicata da `skill-catalog.json`; passa `--baseline` solo
se intendi confrontare con un altro rapporto compatibile.

Per modelli selettori non deterministici, raccogli un numero dispari di almeno
tre esecuzioni cieche di predizione e valuta la loro decisione a maggioranza:

```shell
python scripts/trigger_evals.py aggregate \
  --corpus release-holdout \
  --predictions run-1.json run-2.json run-3.json \
  --predictions-output .trigger-evals/aggregate.json \
  --json-output .trigger-evals/candidate-report.json
```

## Verificare un rilascio

I rilasci versionati includono archivi ZIP e TAR.GZ deterministici,
`release-manifest.json` e `SHA256SUMS`. Scarica tutti e quattro gli artefatti
in una directory e verificali con:

```shell
python scripts/build_release.py --verify <download-directory>/SHA256SUMS
```

GitHub espone anche un `digest` SHA-256 per ogni artefatto di rilascio caricato.
I workflow di rilascio pubblicano inoltre attestazioni degli artefatti GitHub.
Verifica un artefatto scaricato rispetto a questo repository con:

```shell
gh attestation verify <artifact> --repo kolabse/skills
```
