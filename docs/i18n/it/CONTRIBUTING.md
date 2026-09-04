# Contribuire alle skill

[English](../../../CONTRIBUTING.md) | [Русский](../ru/CONTRIBUTING.md) | [Español](../es/CONTRIBUTING.md) | [Français](../fr/CONTRIBUTING.md) | [Deutsch](../de/CONTRIBUTING.md) | [Português (Brasil)](../pt-BR/CONTRIBUTING.md) | [日本語](../ja/CONTRIBUTING.md) | Italiano | [한국어](../ko/CONTRIBUTING.md) | [简体中文](../zh-CN/CONTRIBUTING.md) | [Türkçe](../tr/CONTRIBUTING.md) | [Polski](../pl/CONTRIBUTING.md) | [Українська](../uk/CONTRIBUTING.md)

Questa è una traduzione italiana. In caso di discrepanze, fa fede la [versione inglese canonica](../../../CONTRIBUTING.md).

Questo repository è la sede canonica delle skill riutilizzabili di kolabse.
Mantieni ogni skill mirata, portabile, con attribuzione chiara e installabile
indipendentemente.

## Prima di aggiungere una skill

1. Identifica la fonte canonica. Decidi se questo repository sarà responsabile
   della skill o replicherà un'altra fonte.
2. Accerta il diritto di ridistribuire ogni istruzione, script, riferimento e
   risorsa copiati. I contributi originali sono accettati con la licenza
   Apache-2.0 del repository, salvo diversa indicazione esplicita. Conserva i
   file di licenza, gli avvisi di copyright, le attribuzioni e gli avvisi di
   modifica di terze parti; registra la loro espressione SPDX nel catalogo.
   Non pubblicare materiale di terze parti con licenza non chiarita.
3. Cerca nelle descrizioni esistenti condizioni di attivazione sovrapposte.
   Estendi una skill esistente quando il flusso di lavoro ha lo stesso scopo;
   aggiungine una nuova quando ha una condizione di attivazione e un criterio
   di completamento utili in modo indipendente.
4. Scegli un nome minuscolo, che inizi con un verbo, separato da trattini e di
   non oltre 63 caratteri.

Criterio di completamento: responsabilità, provenienza, licenza, ambito e nome
della skill sono noti prima di copiare i file.

## Seguire una proposta durante l'implementazione

Quando una skill nuova o estesa nasce da una GitHub Issue, mantieni quella
Issue come elemento di lavoro canonico finché l'implementazione non è presente
nel branch principale.

1. Registra l'Issue di origine nella pull request di implementazione.
2. Inserisci `Closes #<issue-number>` nel corpo della pull request. Se la
   modifica non deve chiudere l'Issue, indica esplicitamente il motivo e l'esito
   previsto.
3. Dopo il merge, esamina l'Issue senza presumere che la parola chiave di
   chiusura sia stata applicata. Se è ancora aperta inaspettatamente, chiudila
   come completata con collegamenti alla pull request di implementazione e,
   quando disponibile, al rilascio.
4. Se l'implementazione viene rifiutata, sostituita o consegnata solo in parte,
   lascia un commento esplicativo e assegna all'Issue l'esito corrispondente;
   non dichiarare mai completata una proposta solo perché esistevano un branch
   o una pull request.

Criterio di completamento: ogni proposta implementata è tracciabile dall'Issue
di origine alla pull request integrata, e l'Issue ha uno stato finale verificato
con una spiegazione dell'implementazione o del mancato completamento.

## Aggiungere o migrare la skill

1. Sincronizza entrambi i repository, di origine e destinazione, senza
   sovrascrivere il lavoro locale.
2. Crea `skills/<skill-name>/SKILL.md`. Mantieni solo `name` e `description`
   nei metadati YAML iniziali e fai corrispondere il nome della cartella a `name`.
3. Colloca gli strumenti ausiliari deterministici in `scripts/`, i dettagli
   destinati all'agente in `references/`, i materiali di output in `assets/` e
   i metadati UI facoltativi in `agents/openai.yaml`. Mantieni la configurazione
   del progetto fuori dalla cartella della skill.
4. Scrivi passaggi all'imperativo con criteri di completamento verificabili.
   Mantieni il corpo sotto le 500 righe; rendi disponibili i dettagli specifici
   delle varianti del flusso tramite riferimenti diretti.
5. Aggiungi una voce a `skill-catalog.json`:
   - `name` e `path` relativo al repository;
   - esattamente una `category` principale, secondo l'ordine di priorità documentato;
   - uno o più `tags` controllati per fase del ciclo di vita, ambito,
     comportamento e integrazioni;
   - `status`: `experimental`, `stable` o `deprecated`;
   - nomi utente GitHub in `maintainers`;
   - `platforms` supportate;
   - espressione SPDX in `license`;
   - tipo di provenienza, fonte, nomi precedenti e repository canonico.
   Valida i valori delle categorie e dei tag rispetto a
   `schemas/skill-catalog.schema.json`; lo stato di maturità è indipendente da entrambi.
6. Aggiungi la skill al catalogo del README con scopo, note di installazione e
   azione richiesta al primo utilizzo.
7. Aggiungi test per gli script deterministici e prompt realistici che devono
   e non devono attivare la skill. Memorizza almeno tre casi positivi e tre casi
   negativi affini in `evals/<skill-name>.json` e fai riferimento a quel file
   da `skill-catalog.json` come `trigger_evals`.

Per una skill migrata, conserva la sua storia nel catalogo anche dopo che questo
repository diventa canonico. Per una skill importata da terze parti, registra
una revisione immutabile della fonte, mantieni licenza e avvisi nella cartella
della skill e separa le modifiche upstream dalle patch locali. Conferma la
compatibilità delle licenze prima di combinare contenuti di terze parti con
contenuti Apache-2.0.

Criterio di completamento: un lettore può stabilire da dove proviene la skill,
chi ne è responsabile, con quale licenza è distribuita, dove funziona e come validarla.

## Contratto di configurazione

Ogni skill configurabile dichiara un oggetto `configuration` in
`skill-catalog.json` e segue queste regole:

- `configure` è un array argv, può essere ripetuto in sicurezza, preserva i
  contenuti del progetto non pertinenti e non segnala modifiche al secondo
  passaggio identico;
- `status` è di sola lettura, supporta JSON leggibile dalle macchine, termina
  con codice zero solo se la configurazione dichiarata è presente e valida e
  non stampa mai segreti;
- gli ambiti progetto e utente sono espliciti; la configurazione resta fuori
  dalla directory della skill installata;
- la configurazione JSON e YAML ha una versione intera positiva, uno schema
  JSON incluso che descrive il documento decodificato e un comando di
  migrazione che si blocca in caso di incertezza o errore;
- il testo gestito usa marcatori accoppiati specifici della skill, rifiuta
  marcatori malformati o duplicati e non riscrive testo esterno al proprio blocco.
- le skill senza stato usano il formato `none`, espongono solo un comando di
  stato di sola lettura e non devono inventare artefatti di configurazione segnaposto.

I comandi sono memorizzati come array anziché come stringhe shell. Usa
segnaposto come `<project-root>` per i valori forniti dal chiamante e non
inserire mai credenziali in un comando del catalogo. Mantieni i passaggi di
migrazione incrementali e idempotenti; rifiuta una versione più recente
sconosciuta invece di indovinare come retrocederla.

Criterio di completamento: ripetere configure produce output identico byte per
byte dove la configurazione esiste, status non scrive nulla, le migrazioni
preservano gli input supportati e i test coprono configurazioni mancanti,
malformate, attuali e precedenti.

## Preservare il percorso di aggiornamento degli agenti destinatari

- Mantieni identiche in un rilascio le versioni di `.codex-plugin/plugin.json`,
  `.claude-plugin/plugin.json`, `skill-catalog.json.collection_version` e di
  ogni `skills/*/collection-metadata.json`.
- Verifica l'installazione mediante copia e l'aggiornamento dalla più vecchia
  versione precedente supportata attraverso la CLI `skills` fissata, sia per
  `codex` sia per `claude-code`.
- Installa globalmente la raccolta per ogni agente. Mantieni la configurazione,
  le regole gestite e le impostazioni intenzionali del progetto fuori dalle cartelle
  delle skill installate. Non fare mai creare silenziosamente a un programma
  di aggiornamento la configurazione per una skill non utilizzata.
- Dopo un aggiornamento rileva le copie legacy del progetto e mostra un avviso di
  centralizzazione. La migrazione deve pianificare senza scrivere, verificare le
  copie globali prima della rimozione, preservare skill estranee e configurazione,
  conservare un backup recuperabile e richiedere l'approvazione del piano esaminato.
- Documenta nel README e nel changelog le migrazioni necessarie e i limiti del
  ripristino. Considera non supportata la retrocessione della configurazione
  se non è stata verificata con test.
- Preserva le voci non pertinenti quando modifichi il marketplace personale.
  Applica un solo suffisso di invalidazione della cache alla copia installata
  del plugin e richiedi una nuova attività Codex dopo l'attivazione.

Criterio di completamento: chi utilizza l'installazione per un agente può
identificare le versioni installate, aggiornarle, migrare la configurazione
esistente, diagnosticare versioni miste e reinstallare un tag precedente senza
dipendere da conoscenze interne al repository.

## Preservare il comportamento tra agenti

Mantieni portabili le istruzioni condivise in `SKILL.md` e gli strumenti
ausiliari. Codex rimane il predefinito per le interfacce a riga di comando
esistenti; un destinatario Claude Code esplicito usa `.claude/skills`,
`CLAUDE.md` e `/skill-name`. Non sostituire le API di configurazione `.agents`
esistenti solo per rinominarle per un altro agente destinatario.

Considera `agents/openai.yaml` metadati UI OpenAI e `.codex-plugin` il
confezionamento per Codex. Il confezionamento Claude appartiene a
`.claude-plugin`; nessun manifesto può sostituire silenziosamente la validazione
dell'altro. Quando un agente non dispone di una capacità, come l'enumerazione
delle attività di Codex Desktop, segnala come non supportata quella specifica
operazione mantenendo il sottoinsieme portabile.

Criterio di completamento: entrambe le installazioni globali per gli agenti destinatari
contengono payload delle skill identici, rispettano i layout nativi delle regole
di progetto e delle skill, mantengono invariati i valori predefiniti Codex e le
evidenze degli smoke test nominano esplicitamente entrambi gli agenti.

## Comporre le skill per capacità

Dichiara nomi di capacità circoscritti in `provides`, prerequisiti obbligatori
in `requires` e integrazioni non bloccanti in `optional_integrations`. Aggiungi
una composizione della raccolta con un nome solo per un flusso ricorrente con
almeno due skill. I suoi `required_steps` sono ordinati; gli `optional_steps`
si eseguono solo quando il progetto o l'utente ne ha abilitato la capacità.

Non copiare il flusso di lavoro di una skill in un'altra. Richiama la skill
prerequisita, usa il suo risultato di completamento osservabile e fermati
quando manca una capacità obbligatoria. Notifiche o registrazioni facoltative
non devono mai trasformare un'operazione primaria riuscita in un falso successo,
né nasconderne il fallimento.

Criterio di completamento: ogni capacità richiesta ha un fornitore, i passaggi
della composizione fanno riferimento una sola volta a skill esistenti e
l'ordine ha un test d'integrazione o un criterio di completamento eseguibile.

## Gestire lo stato del ciclo di vita

- Mantieni una skill nuova o sostanzialmente riprogettata `experimental` finché
  non hanno superato la verifica metadati, strumenti deterministici, test
  multipiattaforma, corpus di sviluppo delle attivazioni, test prospettico
  indipendente, smoke test dell'installazione mediante copia e holdout di
  rilascio. I requisiti non applicabili, come script inclusi per un flusso
  composto solo da testo, possono essere registrati come non applicabili.
- Contrassegna una skill come `stable` solo in un rilascio versionato della
  raccolta. Aggiungi `stable_since` con quella versione. Stabile significa che
  input documentati, posizioni della configurazione, limiti di sicurezza e
  comportamento CLI rimarranno compatibili nella versione principale corrente
  della raccolta oppure riceveranno indicazioni di migrazione.
- Contrassegna una skill come `deprecated` prima della rimozione. Indica nella
  skill e nel changelog la sostituzione supportata o il percorso di migrazione,
  e conservala per almeno un rilascio minore, salvo che un problema urgente di
  sicurezza imponga una rimozione anticipata.

Criterio di completamento: lo stato del ciclo di vita è sostenuto da una
validazione osservabile e comunica una chiara aspettativa di compatibilità.

## Preservare la provenienza dell'installazione

Considera un nome di skill noto solo un candidato, mai una prova dell'identità
della raccolta. Metti in relazione la fonte del lock esterno con il
`collection-metadata.json` installato. Normalizza le forme GitHub supportate in
`https://github.com/kolabse/skills`; verifica le fonti di sviluppo locali tramite
manifesto del plugin, catalogo e contenuto della skill richiesta senza dipendere
dal nome della directory del checkout.

Blocca l'operazione in presenza di una skill omonima da un'altra fonte o di
metadati contraddittori. Mantieni esplicita l'adozione delle installazioni
precedenti e consentila solo quando la stessa fonte del lock è verificata;
un'adozione riuscita deve terminare con metadati aggiornati e una diagnosi
post-aggiornamento senza problemi.

Criterio di completamento: status espone la classificazione della provenienza,
update seleziona solo skill verificate (o skill precedenti adottate
esplicitamente) e i test coprono collisioni di fonti, riferimenti di rilascio,
checkout locali rinominati e installazioni precedenti.

## Mantenere ispezionabile l'automazione per gli agenti destinatari

Mantieni `plan` di sola lettura: non deve richiamare programmi di installazione,
migrazioni o operazioni di rete. Pubblica schemi JSON versionati per i payload
di piano e risultato e distingui gli stati invariato, aggiornato, migrato,
saltato, bloccato e fallito senza analizzare l'output CLI destinato alle persone.

Limita il rilevamento globale alle radici documentate dei lock e delle
installazioni. Non cercare possibili installazioni in tutta la directory home.
Applica le stesse regole di provenienza, selezione esplicita e diagnosi
post-aggiornamento nell'ambito globale.

Il bootstrap autonomo deve verificare il checksum dell'archivio prima
dell'estrazione, verificare la provenienza della build GitHub prima
dell'esecuzione, rifiutare voci dell'archivio con attraversamento di directory
o link simbolici, usare una directory temporanea e propagare il codice di
uscita del gestore. Consenti l'esecuzione offline senza attestazione solo
tramite un'opzione esplicita di modalità degradata.

Criterio di completamento: gli schemi sono analizzabili, la simulazione lascia
le fixture identiche byte per byte, le fixture globali coprono layout supportati
e ambigui e lo smoke test del bootstrap passa su ogni sistema operativo CI supportato.

## Validare la modifica

Esegui:

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py --agent codex
python scripts/smoke_install.py --agent claude-code
```

Prova il corpus delle attivazioni con un agente reale, incluso il percorso di
primo utilizzo della skill. I controlli strutturali CI mantengono completo il
corpus, ma non sostituiscono l'osservazione dell'invocazione del modello.
Includi nella pull request i prompt e il risultato osservato.

Per valutare le attivazioni dell'intera raccolta, prepara una suite cieca e
assegna un punteggio alle osservazioni del selettore:

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

I selettori possono scegliere più skill o nessuna. Non esporre al selettore i
file sorgente delle valutazioni, le etichette attese, le motivazioni degli
autori, i sospetti errori o i rapporti precedenti. Registra l'identità del
fornitore e del modello nei metadati delle predizioni, conserva le predizioni
grezze insieme alle evidenze di revisione ed esamina ogni falso positivo e
falso negativo prima di modificare una descrizione. Un punteggio più alto non
è una ragione sufficiente per ampliare una condizione di attivazione se ciò
renderebbe ambigui i flussi di lavoro affini.

Considera `evals/release-holdout-vN.json` evidenza di rilascio a sola aggiunta.
Non leggere né eseguire l'holdout attivo mentre affini le descrizioni. Le
versioni esistenti dell'holdout sono immutabili: crea `vN+1`, aggiorna nome,
percorso e digest canonico nel catalogo e conserva ogni versione pubblicata.
Esegui l'holdout attivo solo dopo aver congelato le descrizioni candidate,
quindi confrontane il rapporto con una baseline generata dalla stessa versione
di holdout e configurazione del selettore. Non confrontare mai rapporti con
digest delle asserzioni diversi. Dopo il rilascio, conserva il rapporto
accettato in `evals/baselines/` e aggiorna il puntatore alla baseline nel
catalogo; i file di baseline sono evidenze di rilascio e non devono essere
riscritti. Quando il selettore non è deterministico, usa un numero dispari di
almeno tre esecuzioni cieche indipendenti e confronta l'aggregato a maggioranza.
Non ripetere una singola osservazione finché non passa né scartare osservazioni
fallite valide.

Criterio di completamento: ogni comando passa su ciascun sistema operativo
supportato e la checklist della pull request contiene evidenze per la skill
interessata.

## Proteggere la catena di rilascio

- Fissa ogni GitHub Action esterna a uno SHA completo di commit e conserva la
  versione di rilascio in un commento. Lascia che Dependabot proponga
  aggiornamenti SHA soggetti a revisione.
- Assegna a ogni workflow solo i permessi `GITHUB_TOKEN` necessari.
- Crea gli archivi di rilascio tramite `scripts/build_release.py`; verifica
  `SHA256SUMS` prima di caricare gli artefatti.
- Pubblica attestazioni GitHub per ogni artefatto di rilascio e verificale con
  `gh attestation verify <artifact> --repo kolabse/skills`.
- Non sostituire mai un artefatto di rilascio esistente. Una riesecuzione del
  workflow deve verificare che i byte pubblicati siano identici oppure fallire.
- Mantieni immutabili i tag di versione. Pubblica una correzione come nuova
  versione invece di spostare un tag esistente o sostituirne il commit sorgente.

Criterio di completamento: il tag punta al commit revisionato, gli artefatti
caricati corrispondono a `SHA256SUMS` e le dipendenze dei workflow sono
riferimenti immutabili.
