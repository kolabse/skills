# kolabse/skills

[English](../../../README.md) | [Русский](../ru/README.md) | [Español](../es/README.md) | Français | [Deutsch](../de/README.md) | [Português (Brasil)](../pt-BR/README.md) | [日本語](../ja/README.md) | [Italiano](../it/README.md) | [한국어](../ko/README.md) | [简体中文](../zh-CN/README.md) | [Türkçe](../tr/README.md)

Cette traduction est fournie à titre informatif ; la [version anglaise canonique](../../../README.md) fait foi en cas de divergence.

Skills réutilisables pour agents, maintenus par kolabse.

Sous [licence Apache 2.0](../../../LICENSE). Copyright 2026 kolabse.

## Table des matières

- [Installer des skills](#installer-des-skills)
  - [Installer depuis les marketplaces Git](#installer-depuis-les-marketplaces-git)
- [Mettre à jour les skills installés](#mettre-à-jour-les-skills-installés)
  - [Exécuter sans cloner le dépôt](#exécuter-sans-cloner-le-dépôt)
  - [Inspecter les installations globales](#inspecter-les-installations-globales)
- [Installer ou mettre à jour un plugin Codex de développement local](#installer-ou-mettre-à-jour-un-plugin-codex-de-développement-local)
- [Skills disponibles](#skills-disponibles)
  - [Développement et qualité du code](#développement-et-qualité-du-code)
    - [`develop-with-test-first-evidence`](#develop-with-test-first-evidence-expérimental)
    - [`review-code-changes`](#review-code-changes-expérimental)
    - [`diagnose-software-defects`](#diagnose-software-defects-expérimental)
    - [`resolve-git-conflicts`](#resolve-git-conflicts-expérimental)
  - [Dépôts et livraison des modifications](#dépôts-et-livraison-des-modifications)
    - [`synchronize-git-repositories`](#synchronize-git-repositories)
    - [`verify-before-push`](#verify-before-push)
    - [`coordinate-code-documentation-repositories`](#coordinate-code-documentation-repositories-expérimental)
    - [`execute-configured-gitflow-releases`](#execute-configured-gitflow-releases-expérimental)
    - [`execute-verified-development-lifecycle`](#execute-verified-development-lifecycle-expérimental)
  - [Connaissances du projet et continuité](#connaissances-du-projet-et-continuité)
    - [`maintain-work-log`](#maintain-work-log)
    - [`maintain-project-digest`](#maintain-project-digest-expérimental)
    - [`sync-project-context`](#sync-project-context)
  - [Coordination et communication](#coordination-et-communication)
    - [`orchestrate-agent-work`](#orchestrate-agent-work-expérimental)
    - [`synchronize-team-skills`](#synchronize-team-skills-expérimental)
    - [`notify-via-telegram`](#notify-via-telegram)
  - [Infrastructure et opérations](#infrastructure-et-opérations)
    - [`operate-yandex-cloud`](#operate-yandex-cloud)
  - [Évolution de la collection de skills](#évolution-de-la-collection-de-skills)
    - [`discover-skill-candidates`](#discover-skill-candidates-expérimental)
    - [`release-skill-collection`](#release-skill-collection)
- [Compositions prises en charge](#compositions-prises-en-charge)
- [Ajouter un skill](#ajouter-un-skill)
- [Vérifier une version publiée](#vérifier-une-version-publiée)

## Installer des skills

Installez un ou plusieurs skills dans le projet courant avec la CLI multi-agent
[`skills`](https://skills.sh) :

```shell
npx skills@latest add kolabse/skills
```

La CLI découvre les dossiers sous `skills/`, vous laisse choisir les skills à
installer et les copie pour les agents de programmation sélectionnés. Il
s’agit d’un installateur externe ; ce dépôt ne publie ni n’exécute son propre
package npm.

Les utilisateurs de Codex peuvent aussi demander à `$skill-installer`
d’installer un skill depuis ce dépôt, par exemple depuis :

```text
https://github.com/kolabse/skills/tree/main/skills/operate-yandex-cloud
```

Choisissez explicitement l’agent cible pour une installation non interactive :

```shell
npx skills@1.5.22 add kolabse/skills --agent codex --copy -y
npx skills@1.5.22 add kolabse/skills --agent claude-code --copy -y
```

Pour une installation de projet, demandez à votre agent : « Installe les
skills sélectionnés et initialise les valeurs par défaut manquantes du projet
sans remplacer nos règles existantes. » Après l’installation externe,
initialisez les règles Git de votre agent avec le bootstrap :

```shell
python .agents/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent codex --apply --yes --json
python .claude/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent claude-code --apply --yes --json
```

Les conventions manquantes prennent par défaut les préfixes `feature/`,
`bugfix/`, `release/`, `hotfix/` et les types de commits `feat`, `fix`,
`refactor`, `docs`, `test`, `chore`. Les préfixes, rôles de branches et formats
de commits explicites du projet restent prioritaires. Aucune branche
persistante ni aucun hook Git n’est créé. Les mises à jour gérées au niveau du
projet appliquent ce même bootstrap aux skills concernés ; les mises à jour
non confirmées se contentent de le planifier.

Pour une installation au niveau du projet, initialisez immédiatement le
contrat de cycle de vie lorsque ses valeurs par défaut observables suffisent
(utilisez le chemin correspondant à votre agent) :

```shell
python .agents/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent codex --apply --yes --json
python .claude/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent claude-code --apply --yes --json
```

Les installations par marketplace ou plugin sont globales et n’ont pas de
racine de projet active ; le skill effectue donc ce même bootstrap lors de sa
première utilisation dans un projet.

Codex découvre les skills de projet sous `.agents/skills/` et les invoque sous
la forme `$skill-name`. Claude Code les découvre sous `.claude/skills/` et les
invoque sous la forme `/skill-name`. Les instructions et les scripts fournis
sont partagés ; les fichiers de règles et la syntaxe d’invocation propres à
l’agent sont choisis lors de la configuration.

Le dépôt est également distribué sous forme de plugin `kolabse-skills`, composé
uniquement de skills, pour ChatGPT/Codex et Claude Code. Chaque dossier sous
`skills/` est inclus. L’installation multi-agent par `npx skills` reste
disponible indépendamment de ces deux formats de plugin.

### Installer depuis les marketplaces Git

Les utilisateurs de Codex peuvent enregistrer la marketplace du dépôt et
installer la collection complète avec :

```shell
codex plugin marketplace add kolabse/skills --ref main
codex plugin add kolabse-skills@kolabse
```

Actualisez l’instantané Git et réinstallez la version actuelle du plugin avec :

```shell
codex plugin marketplace upgrade kolabse
codex plugin add kolabse-skills@kolabse
```

Les utilisateurs de Claude Code peuvent enregistrer le même dépôt et installer
le plugin avec :

```shell
claude plugin marketplace add kolabse/skills
claude plugin install kolabse-skills@kolabse
```

Actualisez-le explicitement avec `claude plugin marketplace update kolabse`, ou
activez la mise à jour automatique de la marketplace dans Claude Code. Démarrez
une nouvelle session d’agent après installation ou mise à jour afin qu’elle
découvre l’ensemble actuel des skills.

Les catalogues de marketplace sont
[`.agents/plugins/marketplace.json`](../../../.agents/plugins/marketplace.json)
et [`.claude-plugin/marketplace.json`](../../../.claude-plugin/marketplace.json).
Le contenu de leurs plugins est décrit par
[`.codex-plugin/plugin.json`](../../../.codex-plugin/plugin.json) et
[`.claude-plugin/plugin.json`](../../../.claude-plugin/plugin.json). Les deux
catalogues récupèrent le dépôt canonique `kolabse/skills` depuis `main` ; les
versions des publications restent définies par les manifestes de plugin.

Les documents de référencement public sont maintenus avec les sources :
[assistance](SUPPORT.md), [politique de confidentialité](PRIVACY.md),
[conditions d’utilisation](TERMS.md) et
[dossier reproductible de soumission aux marketplaces](../../../docs/marketplace-submissions/).
La publication dans un annuaire officiel reste une action des responsables de
maintenance soumise à revue ; l’installation depuis les marketplaces Git ne
nécessite pas l’approbation d’un annuaire.

Claude Code peut charger directement une version extraite ou une copie de
travail de confiance lors des tests avec `claude --plugin-dir <collection-root>`.
Pour un usage personnel ou de projet courant, préférez la marketplace Git ou
la commande explicite `npx skills ... --agent claude-code` ci-dessus. Claude
Code lit `CLAUDE.md`, et non `AGENTS.md` ; lorsqu’un projet possède déjà des
règles partagées dans `AGENTS.md`, un `CLAUDE.md` minimal contenant `@AGENTS.md`
permet de conserver un seul document de règles canonique.

## Mettre à jour les skills installés

La CLI `skills` consigne la source GitHub et une empreinte du contenu dans
`skills-lock.json`. Mettez à jour toutes les installations de projet depuis
leur source enregistrée :

```shell
npx skills@1.5.22 update -p -y
```

Mettez à jour un seul skill ou les installations globales avec :

```shell
npx skills@1.5.22 update verify-before-push -p -y
npx skills@1.5.22 update -g -y
```

Un verrouillage `kolabse/skills` sans référence explicite suit la branche par
défaut du dépôt ; il ne fixe pas une version de la collection. Ne modifiez pas
les fichiers copiés sous `.agents/skills/`, car une mise à jour peut les
remplacer. La configuration du projet et de l’utilisateur reste hors des
dossiers des skills installés.

Depuis une copie clonée ou une archive de version, mettez à jour et migrez la
configuration de projet prise en charge en une opération explicite :

```shell
python scripts/manage_installed_skills.py update --project-path . --yes --migrate
python scripts/manage_installed_skills.py doctor --project-path . --json
```

Prévisualisez la sélection exacte sans invoquer l’installateur externe ni
modifier la configuration :

```shell
python scripts/manage_installed_skills.py plan --project-path . --json
```

Le plan indique l’identité de la source, les versions actuelle et cible, la
provenance, les candidats à la migration et les actions `update`, `unchanged`,
`adopt-and-update` ou `blocked`. Son schéma est
`schemas/manager-plan.schema.json`. Ajoutez `--json` à `update` ; les résultats
de mise à jour et de migration suivent `schemas/manager-result.schema.json`.

Sans noms fournis, le gestionnaire résout les skills kolabse installés à
partir du verrouillage du projet et transmet explicitement ces noms à la CLI
externe ; les skills sans rapport du projet ne font jamais partie de la mise
à jour. Les mises à jour globales exigent des noms explicites de skills de la
collection. Les mises à jour de projet se terminent par le même diagnostic
bloquant en cas d’anomalie que `doctor`. Lorsque
`execute-verified-development-lifecycle` fait partie d’une mise à jour de
projet, le gestionnaire initialise aussi sa configuration manquante lorsque
les faits observables du projet suffisent, et renvoie un résultat de
configuration `created`, `configured` ou `blocked`.

N’ajoutez `--include-user-config` que si la configuration utilisateur Telegram
doit également être migrée. `status` et `doctor` sont en lecture seule.
`migrate` ne modifie que les fichiers de configuration existants ; il ne
configure pas les skills inutilisés. Chaque skill installé contient
`collection-metadata.json`, de sorte que `status` indique sa version de
collection même si le format externe de verrouillage n’a pas de champ version.
Il indique aussi `provenance_status` : `verified` exige à la fois les
métadonnées de collection et une source de verrouillage GitHub canonique ou
locale dont le contenu a été vérifié ; `legacy-unverified` désigne une
installation antérieure aux métadonnées ; `mismatch` n’est jamais mis à jour.
Une copie de travail peut être renommée, car son identité locale vient de son
manifeste de plugin, de son catalogue et du contenu des skills, non du nom du dossier.

N’adoptez une installation antérieure à v1.2, sans métadonnées, qu’après avoir
examiné la source indiquée :

```shell
python scripts/manage_installed_skills.py status --project-path . --json
python scripts/manage_installed_skills.py update --project-path . --yes --adopt-legacy
```

L’option d’adoption ne rend pas acceptables des fichiers arbitraires : la
source doit déjà se normaliser en `kolabse/skills` ou réussir la validation
d’une copie de travail locale, et le diagnostic normal après mise à jour doit
vérifier les métadonnées installées. La CLI externe ne met pas à jour sur place
les verrouillages de développement `sourceType: local`. Le gestionnaire
considère cette absence d’action de la CLI comme un échec ; réajoutez ces
skills depuis leur source locale avec les sélections `--skill` et `--agent` d’origine.

### Exécuter sans cloner le dépôt

Téléchargez `scripts/bootstrap_update.py` depuis une version de confiance ou
ce dépôt, puis laissez-le résoudre la dernière version stable, vérifier son
ZIP contre `SHA256SUMS` et la provenance de build GitHub, et exécuter le
gestionnaire depuis une extraction temporaire isolée :

```shell
python bootstrap_update.py doctor --json
python bootstrap_update.py plan --json
python bootstrap_update.py update --yes --migrate --json
```

Utilisez `--release v1.15.0` pour fixer une version. Le bootstrap exige `gh`
pour vérifier les attestations et supprime son répertoire temporaire à la fin.
Pour un cache hors ligne, fournissez à la fois `--offline-archive` et
`--offline-checksums`. La vérification de provenance reste obligatoire lorsque
`gh` peut joindre GitHub. `--allow-unattested-offline` est un mode dégradé
explicite : il ne vérifie que la somme de contrôle en cache et ne doit être
utilisé que pour des artefacts transférés par un canal dont la fiabilité a été
établie indépendamment. Revenez en arrière en sélectionnant une version plus
ancienne et en suivant la procédure existante ; les migrations de
configuration restent uniquement ascendantes.

### Inspecter les installations globales

L’état global pris en charge est délibérément limité au fichier de
verrouillage partagé v3 `~/.agents/.skill-lock.json`. Les contenus installés
se trouvent dans `~/.agents/skills` pour Codex et `~/.claude/skills` pour
Claude Code. Le gestionnaire ne parcourt pas d’autres répertoires utilisateur.
Codex reste la valeur par défaut ; passez `--agent claude-code` pour la
structure de fichiers Claude :

```shell
python scripts/manage_installed_skills.py status --scope global --json
python scripts/manage_installed_skills.py doctor --scope global --json
python scripts/manage_installed_skills.py plan verify-before-push --scope global --json
python scripts/manage_installed_skills.py update verify-before-push --scope global --yes --json
python scripts/manage_installed_skills.py status --scope global --agent claude-code --json
```

Utilisez `--global-root` pour inspecter en lecture seule une structure
compatible de test ou explicitement déplacée. Les racines déplacées ne peuvent
pas être mises à jour, car la CLI externe ne peut pas les cibler. Les formats
de verrouillage inconnus sont signalés sans modification.

Pour revenir à des fichiers de skills antérieurs, sauvegardez d’abord la
configuration du projet et de l’utilisateur, puis réinstallez le tag requis
avec les mêmes skills et agents cibles que lors de l’installation d’origine,
par exemple :

```shell
npx skills@1.5.22 add kolabse/skills@v1.1.0 --skill verify-before-push --agent codex --copy -y
```

Les migrations de configuration sont uniquement ascendantes, sauf si une
version documente explicitement une rétrogradation. Restaurer d’anciens
fichiers de skills ne rétrograde pas la configuration ; restaurez la sauvegarde
de configuration correspondante lorsque l’ancienne version ne peut pas lire
le format plus récent.

## Installer ou mettre à jour un plugin Codex de développement local

Pour le développement local du plugin, créez ou mettez à jour l’entrée par
défaut de la marketplace personnelle, copiez le plugin dans le répertoire local
des plugins, ajoutez un suffixe d’invalidation du cache Codex et activez-le :

```shell
python scripts/install_personal_plugin.py --activate
```

L’installateur préserve les autres entrées de la marketplace personnelle et
ne modifie pas le manifeste du dépôt. Il s’agit d’un parcours alternatif de
développement, pas de l’installation normale par marketplace Git. Relancez-le
après avoir actualisé la copie de travail, puis démarrez une nouvelle tâche
Codex pour charger les skills mis à jour. Utilisez `--json` pour consigner la
version installée, le chemin du plugin, le chemin et le nom de la marketplace.

## Skills disponibles

Les skills stables et les ajouts expérimentaux sont identifiés dans
`skill-catalog.json`. Leurs chemins de configuration destinés aux projets,
leurs limites de sécurité et leurs interfaces de commande documentées suivent
la politique de compatibilité de [CONTRIBUTING.md](CONTRIBUTING.md).

Chaque entrée du catalogue déclare désormais son périmètre de configuration,
sa commande d’état JSON en lecture seule, ses capacités, ses prérequis et ses
intégrations facultatives. Les skills avec état déclarent aussi une commande
de configuration idempotente ; les configurations JSON/YAML versionnées
publient un schéma JSON et une commande de migration à côté du skill.

Le catalogue est regroupé selon son objectif principal pour l’utilisateur,
dans l’ordre de priorité ci-dessous. Chaque skill possède exactement une
catégorie principale. Des tags indépendants décrivent sa phase de cycle de
vie, son périmètre, son comportement et ses intégrations ; le statut de
maturité reste indépendant. Les affectations faisant autorité et lisibles par
machine ainsi que le vocabulaire contrôlé se trouvent dans
[`skill-catalog.json`](../../../skill-catalog.json), validé avec
[`schemas/skill-catalog.schema.json`](../../../schemas/skill-catalog.schema.json).

Les axes de tags contrôlés sont :

- phase du cycle de vie : `prepare`, `investigate`, `implement`, `verify`,
  `publish`, `operate`, `document` et `handoff` ;
- périmètre : `project`, `repository`, `multi-repository`, `workstation`,
  `external-service` et `skill-collection` ;
- comportement : `read-only-planning`, `mutation`, `evidence-producing`,
  `orchestration` et `notification` ;
- intégration : `git`, `github`, `telegram`, `google-drive` et `yandex-cloud`.

### Développement et qualité du code

#### `develop-with-test-first-evidence` (expérimental)

Implémentez le comportement par des cycles rouge-vert-refactorisation appuyés
sur des preuves.

**Ce qu’il fait :**

- consigne, avant l’implémentation, l’échec d’un test ciblé pour la raison
  comportementale attendue ;
- lie les résultats verts ciblés et élargis à l’état final de la modification ;
- valide les preuves durables avec le schéma et l’utilitaire fournis.

**Ce qu’il ne fait pas :**

- fabriquer un résultat rouge en cassant un comportement sans rapport ;
- qualifier de développement piloté d’abord par les tests des tests écrits après coup ;
- masquer les échecs préexistants, environnementaux ou de l’état final.

**Comment l’invoquer :**

```text
$develop-with-test-first-evidence Implement this behavior with a recorded red-green-refactor cycle.
```

#### `review-code-changes` (expérimental)

Examinez une modification délimitée pour détecter des défauts actionnables de
correction, de sécurité, de fiabilité et de compatibilité.

**Ce qu’il fait :**

- résout une référence de départ et un état modifié exacts ;
- rapporte des constats étayés, avec impact, déclencheur, priorité et
  emplacements précis ;
- explicite l’incertitude et les lacunes significatives de tests.

**Ce qu’il ne fait pas :**

- présenter des préférences de style ou des spéculations non étayées comme des défauts ;
- corriger les constats, publier des commentaires ou approuver une revue sans
  autorisation distincte ;
- remplacer une revue ciblée par une explication générale du code.

**Comment l’invoquer :**

```text
$review-code-changes Review this branch against its declared baseline and report actionable findings.
```

#### `diagnose-software-defects` (expérimental)

Enquêtez sur les échecs et les régressions pour produire une explication
causale étayée ou des hypothèses classées.

**Ce qu’il fait :**

- délimite et reproduit le symptôme sans risque lorsque c’est possible ;
- teste les hypothèses concurrentes à l’aide de preuves pertinentes ;
- rapporte la cause racine, les conditions contributives, l’étendue des
  conséquences, le degré de confiance et un plan de vérification du correctif.

**Ce qu’il ne fait pas :**

- déduire la causalité d’une corrélation ;
- modifier la production ou écarter les preuves d’échec ;
- implémenter un correctif spéculatif lorsqu’un diagnostic seul a été demandé.

**Comment l’invoquer :**

```text
$diagnose-software-defects Diagnose this regression and distinguish evidence from hypotheses.
```

#### `resolve-git-conflicts` (expérimental)

Résolvez les conflits autorisés de merge, rebase ou cherry-pick selon leur
sémantique, en préservant le travail sans rapport.

**Ce qu’il fait :**

- inspecte l’opération active, la base, les deux côtés et chaque chemin non fusionné ;
- ne réconcilie que les conflits dont le comportement combiné voulu est compris ;
- valide les chemins résolus et explicite l’étape restante de l’opération Git.

**Ce qu’il ne fait pas :**

- traiter une divergence ordinaire du dépôt comme une tâche de conflit de fichiers ;
- effectuer automatiquement un stash, reset, abort, continue ou force-push,
  ni ajouter à l’index des chemins sans rapport ;
- deviner les décisions ambiguës concernant des fichiers générés, binaires,
  des schémas ou le produit.

**Comment l’invoquer :**

```text
$resolve-git-conflicts Resolve the active merge conflicts path by path and validate the result.
```

### Dépôts et livraison des modifications

#### `synchronize-git-repositories`

Établissez l’état distant actuel sans écraser le travail local.

**Ce qu’il fait :**

- découvre uniquement les dépôts pertinents pour la tâche et récupère leurs
  remotes suivis ;
- avance en fast-forward les branches propres qui sont uniquement en retard ;
- signale les états avec modifications locales, en avance, divergents,
  détachés, sans suivi et avec une opération en cours ;
- publie une branche de fonctionnalité autorisée depuis un `main` actuel et
  vérifié avant la première modification lorsque la politique du projet l’exige.

**Ce qu’il ne fait pas :**

- effectuer automatiquement un stash, reset, rebase, merge, clean, switch ou force-push ;
- masquer une divergence ou considérer une récupération réussie comme la
  preuve que la branche locale a été mise à jour ;
- parcourir ou mettre à jour des dépôts sans rapport.

**Comment l’invoquer :**

```text
$synchronize-git-repositories Configure this project's repository synchronization policy.
```

#### `verify-before-push`

Liez les contrôles déclarés par le projet à l’état Git exact qui sera poussé.

**Ce qu’il fait :**

- configure une politique de vérification appartenant au dépôt, hors du
  dossier du skill installé ;
- exécute les contrôles déclarés et consigne les preuves pour les commits,
  copies de travail, état amont et configuration de vérification exacts ;
- bloque lorsque les preuves protégées sont absentes, en échec, mal formées ou périmées.

**Ce qu’il ne fait pas :**

- bloquer des dépôts sans rapport non couverts par la politique ;
- analyser des commandes shell arbitraires ou installer un hook propre à un IDE ou agent ;
- considérer un contrôle réussi sur un ancien état Git comme une preuve actuelle.

**Comment l’invoquer :**

```text
$verify-before-push Configure this project's verification policy and checks.
```

#### `coordinate-code-documentation-repositories` (expérimental)

Coordonnez une modification de projet auditable lorsque l’implémentation et la
documentation canonique résident dans des dépôts Git distincts.

**Ce qu’il fait :**

- résout les rôles des dépôts d’implémentation et de documentation déclarés par le projet ;
- crée un plan en lecture seule lié aux deux commits de départ et aux
  sources de documentation faisant autorité ;
- exige des preuves documentaires pour les sujets configurés tels que les
  exigences, le comportement, la validation, l’impact opérationnel et les limites ;
- vérifie l’identité des deux commits publiés, les preuves de validation et
  la traçabilité entre dépôts avant d’annoncer l’achèvement conjoint.

**Ce qu’il ne fait pas :**

- déduire les rôles des dépôts de leurs noms ou des noms de dossiers ;
- remplacer la documentation canonique par un récapitulatif quotidien ;
- modifier, committer, pousser, fusionner ou réparer lui-même des dépôts
  modifiés localement et divergents ;
- affirmer un accord sémantique simplement parce que les fichiers de documentation attendus existent.

**Comment l’invoquer :**

```text
$coordinate-code-documentation-repositories Implement this change across the declared code and canonical documentation repositories and verify both published outcomes.
```

#### `execute-configured-gitflow-releases` (expérimental)

Exécutez les parcours de publication standard et hotfix à partir d’un contrat
GitFlow déclaré par le projet.

**Ce qu’il fait :**

- résout le développement, la production, l’espace de noms hotfix, le remote,
  les points de contrôle et la politique du parcours par défaut depuis la
  configuration versionnée du projet ;
- fige un plan en lecture seule lié au commit source et à l’identité des branches distantes ;
- applique les mêmes contrôles communs déclarés aux parcours standard et hotfix ;
- vérifie la publication en production après revue, les preuves de déploiement
  et la réintégration obligatoire du hotfix dans la ligne de développement.

**Ce qu’il ne fait pas :**

- déduire des noms de branches conventionnels ou utiliser hotfix comme parcours par défaut ;
- prendre en charge la livraison trunk-based ou la chaîne de publication
  spécialisée de cette collection ;
- pousser directement vers une production protégée, contourner des contrôles,
  réécrire l’historique ou réparer silencieusement une divergence ;
- considérer un hotfix de production comme entièrement terminé avant la
  vérification de sa réintégration.

**Comment l’invoquer :**

```text
$execute-configured-gitflow-releases Run the standard release route declared by this project and verify the resulting production identity.
$execute-configured-gitflow-releases Run an explicit hotfix release and verify its reintegration into the declared development line.
```

#### `execute-verified-development-lifecycle` (expérimental)

Planifiez et vérifiez un parcours déclaré par le projet, depuis la préparation
d’une fonctionnalité jusqu’à l’intégration revue dans la ligne de
développement, l’observation de la livraison, la documentation et le nettoyage prouvé.

**Ce qu’il fait :**

- fige un plan lié à une empreinte avant modification et franchit des points
  de contrôle ordonnés à l’aide de preuves conservées ;
- crée une configuration de projet prudente lors d’une mise à jour gérée ou
  de la première utilisation lorsque les racines des dépôts, les branches
  amont suivies, les contrôles et la documentation sont observables, et
  signale chaque valeur par défaut appliquée ;
- vérifie les contrôles de branche de fonctionnalité avant modification,
  tests d’abord, preflight du périmètre modifié, revue, push de l’état exact,
  pipeline, documentation, intégration en développement, production déléguée,
  livraison, test de fumée, notification et nettoyage ;
- revient à un point de contrôle déclaré après un échec et invalide les
  preuves ultérieures devenues périmées.

**Ce qu’il ne fait pas :**

- deviner les adaptateurs propres à un fournisseur, les rôles des dépôts,
  la politique de livraison ou l’autorisation lorsque les preuves du projet sont ambiguës ;
- pousser, ouvrir ou fusionner des revues, déployer, notifier, modifier la
  documentation ou supprimer des ressources lui-même ;
- exécuter la livraison en production, qui reste déléguée au workflow de
  publication approuvé tel que `$execute-configured-gitflow-releases`.

Installez et configurez d’abord ses skills requis :
`$synchronize-git-repositories`, `$develop-with-test-first-evidence`,
`$verify-before-push` et `$review-code-changes`. Un contrat de cycle de vie
version 1 appartenant au projet, s’il manque, est initialisé à partir de faits
observables avant le premier plan ; examinez et affinez les valeurs par défaut
signalées lorsque le projet déclare une politique plus précise. N’installez
les skills facultatifs que lorsque le projet active les points de contrôle
correspondants : `$orchestrate-agent-work`, `$diagnose-software-defects`,
`$resolve-git-conflicts`, `$coordinate-code-documentation-repositories`,
`$maintain-work-log`, `$maintain-project-digest`, `$notify-via-telegram` et
`$execute-configured-gitflow-releases`.

**Comment l’invoquer :**

```text
$execute-verified-development-lifecycle Plan and verify this change through the project's configured development lifecycle.
```

### Connaissances du projet et continuité

#### `maintain-work-log`

Maintenez le journal de projet canonique daté dans `docs/reports/work-log.md`.

**Ce qu’il fait :**

- consigne les modifications importantes, opérations, diagnostics, décisions,
  vérifications, blocages et résultats de retour arrière ;
- préserve le format existant du journal du projet ;
- reconstitue l’historique manquant à partir des preuves Git et des tâches
  du projet disponibles.

**Ce qu’il ne fait pas :**

- s’activer pour un travail ordinaire sauf si la politique du projet ou
  l’utilisateur l’exige ;
- écrire des secrets, journaux applicatifs, suivis de temps ou notes personnelles ;
- affirmer des événements qui ne peuvent pas être étayés par les preuves disponibles.

**Comment l’invoquer :**

```text
$maintain-work-log Configure this project to maintain its dated work log.
```

#### `maintain-project-digest` (expérimental)

Maintenez dans la documentation du projet un récapitulatif quotidien des
modifications terminées, destiné aux utilisateurs.

**Ce qu’il fait :**

- regroupe les modifications terminées sous la date du jour en nouvelles
  capacités, améliorations, correctifs, sécurité, documentation ou changements
  de comportement importants ;
- rédige de courts résultats non techniques et omet les catégories vides ;
- place les dates les plus récentes en premier et laisse chaque date antérieure inchangée ;
- utilise un plan lié au contenu, un verrou coopératif, un remplacement atomique
  et la détection des doublons pour permettre à plusieurs développeurs de
  contribuer sans risque le même jour.

**Ce qu’il ne fait pas :**

- choisir ou créer un emplacement de documentation lorsque le projet n’en
  identifie pas un sans ambiguïté ;
- consigner des plans, des expériences échouées, des activités internes
  d’implémentation ou des bénéfices utilisateur non étayés ;
- remplacer le journal technique, les notes de version ou un journal des
  modifications conventionnel ;
- réécrire les périodes historiques du récapitulatif lors d’une mise à jour
  ordinaire du jour courant.

**Comment l’invoquer :**

```text
$maintain-project-digest Add today's completed user-visible changes to the project digest.
```

#### `sync-project-context`

Synchronisez entre ordinateurs l’état privé et expurgé du projet et de
continuation de chaque conversation. Le skill est stable après deux
exécutions Google Drive indépendantes sur de vrais appareils ayant réussi
son contrôle déterministe de promotion.

**Ce qu’il fait :**

- stocke des points de contrôle immuables dans un dossier synchronisé approuvé
  ou Google Drive connecté, avec une configuration locale à la machine hors du dépôt ;
- dirige par défaut les demandes de synchronisation non qualifiées vers
  Google Drive connecté, tout en préservant un backend existant et en exigeant
  une acceptation explicite avant d’utiliser un dossier synchronisé local ;
- découvre, sur un nouvel ordinateur, une association Google Drive existante
  vérifiée par empreinte du dépôt avant de créer un dossier distant, et bloque
  si les listes sont incomplètes, la visibilité non fiable ou les correspondances multiples ;
- conserve un flux opaque par tâche du projet : une base détaillée suivie de
  courts deltas, des titres visibles exacts, des décisions, vérifications,
  questions ouvertes, prochaines étapes et empreintes Git ;
- enregistre, restaure ou planifie dans les deux sens toutes les tâches
  récentes et épinglées du projet, en ignorant les tâches inchangées ou actives
  et en signalant explicitement les conflits ;
- valide les instantanés téléchargés, relit les téléversements, empêche la
  restauration entre projets et rejette les motifs de secrets à forte confiance ;
- consigne un manifeste d’environnement distinct pour les règles, skills,
  plugins et paramètres scalaires sûrs déclarés que Git ne fournit pas déjà.

**Ce qu’il ne fait pas :**

- copier des fichiers sources, diffs, transcriptions brutes, raisonnements
  cachés, identifiants, jetons OAuth ou installations de skills/plugins ;
- dupliquer les règles ou dépendances déjà transportées par Git ;
- écraser silencieusement des règles de destination suivies par Git :
  l’application ne peut que créer un `AGENTS.md` ou `CLAUDE.md` manquant et
  non suivi, sélectionné pour l’agent actif après un plan explicite ;
- inclure des noms de branches ou chemins de fichiers en mode métadonnées
  uniquement ; les titres visibles des tâches restent volontairement inclus.

Codex Desktop prend en charge les workflows documentés de découverte, création
et renommage de tâches par lots ainsi que du connecteur Google Drive. Claude
Code peut utiliser le cœur portable de points de contrôle, stockage en dossier
local et réconciliation de l’environnement, mais son stockage de sessions
n’est pas inspecté et les opérations de tâches par lots propres à Codex sont
bloquées comme non prises en charge.

**Comment l’invoquer :**

Configurez chaque ordinateur une fois :

```text
$sync-project-context Configure this clone in metadata-only mode. Use connected Google Drive by default unless I explicitly request another approved channel.
```

Utilisez ensuite des commandes par tâche ou par lot, par exemple :

```text
$sync-project-context Save the current task state.
$sync-project-context Restore all project tasks on this computer.
$sync-project-context Synchronize all project tasks bidirectionally and show conflicts before applying changes.
```

Dans Claude Code, remplacez le préfixe `$` de ces exemples par `/`.

### Coordination et communication

#### `orchestrate-agent-work` (expérimental)

Coordonnez des sous-agents explicitement autorisés tout en gardant la
responsabilité du résultat intégré.

**Ce qu’il fait :**

- répartit le travail parallèle en missions délimitées sans chevauchement ;
- surveille et réconcilie les résultats des agents selon les contraintes partagées ;
- vérifie le résultat combiné avant d’annoncer l’achèvement.

**Ce qu’il ne fait pas :**

- déléguer sauf si l’utilisateur ou les instructions du projet autorisent les sous-agents ;
- transférer à un autre agent le pouvoir d’approbation, des secrets, un
  nettoyage destructif ou des modifications externes non approuvées ;
- considérer des sous-tâches terminées indépendamment comme la preuve d’une intégration réussie.

**Comment l’invoquer :**

```text
$orchestrate-agent-work Delegate these independent subtasks to agents and verify the integrated result.
```

#### `synchronize-team-skills` (expérimental)

Maintenez les skills d’agent de projet de chaque membre de l’équipe alignés
sur un manifeste unique revu dans la documentation du projet.

**Ce qu’il fait :**

- crée ou lit `team-agent-skills.md` dans une racine de documentation approuvée ;
- compare les skills Codex et Claude Code déclarés aux copies de projet vérifiées ;
- signale les états manquant, obsolète, plus récent, non vérifié, surcharge de
  projet et supplément préservé sans modifier l’environnement ;
- construit un plan d’installation lié à l’empreinte du manifeste pour une
  seule version épinglée de la collection ;
- n’installe que l’ensemble revu après approbation, puis vérifie l’état observable.

**Ce qu’il ne fait pas :**

- transformer automatiquement l’état fortuit d’un poste en politique d’équipe ;
- stocker des secrets, une configuration utilisateur, des chemins de machine
  ou l’authentification des plugins ;
- supprimer les skills supplémentaires, rétrograder les copies plus récentes
  ou modifier les installations globales ;
- affirmer qu’une tâche d’agent en cours a rechargé les skills nouvellement installés.

**Comment l’invoquer :**

```text
$synchronize-team-skills Check this project's installed skills against the reviewed team manifest.
$synchronize-team-skills Align my project skills with the team documentation after showing the plan.
$synchronize-team-skills Add maintain-project-digest to the reviewed team skill set.
```

#### `notify-via-telegram`

Envoyez via Telegram des mises à jour de cycle de vie pour les tâches d’agent longues.

**Ce qu’il fait :**

- signale les démarrages, jalons, résultats intermédiaires, problèmes,
  blocages et achèvements ;
- valide le bot de manière interactive et aide à découvrir une conversation de destination ;
- fournit un formulaire de première utilisation masqué, adapté au collage,
  pour Codex Desktop sous Windows ;
- stocke les identifiants dans le répertoire de configuration utilisateur
  et envoie une notification de test pendant la configuration ;
- prend en charge une conversation ou un sujet de forum distinct par projet,
  avec un choix explicite entre envoi global plus projet et envoi au projet uniquement ;
- exporte des valeurs de routage de projet sans secrets pour réconciliation
  via `sync-project-context` ;
- fonctionne avec la bibliothèque standard Python 3 sous Windows, macOS et Linux.

**Ce qu’il ne fait pas :**

- placer le jeton du bot dans la conversation, l’historique shell ou le dépôt ;
- copier le jeton global du bot ou l’état d’authentification Telegram entre ordinateurs ;
- envoyer des notifications lorsque l’utilisateur demande de garder le suivi
  dans la tâche courante ;
- servir de framework général de développement de bots Telegram.

**Comment l’invoquer :**

```text
$notify-via-telegram Configure Telegram notifications for long tasks.
$notify-via-telegram Configure this project to notify its team chat only, instead of the global destination.
```

### Infrastructure et opérations

#### `operate-yandex-cloud`

Exploitez une infrastructure Yandex Cloud explicitement configurée et limitée au projet.

**Ce qu’il fait :**

- stocke les identifiants Cloud/Folder partagés dans la configuration du projet
  et le profil `yc` du poste dans une configuration locale ignorée ;
- détecte les outils requis, vérifie les versions minimales et exécute un
  preflight de contexte en lecture seule ;
- prend en charge des workflows délimités de CLI, SSH, Terraform, Ansible,
  Helm, Kubernetes, déploiement, base de données, stockage, DNS, surveillance,
  sauvegarde et gestion d’incidents ;
- fournit une sortie JSON et des utilitaires Python multiplateformes.

**Ce qu’il ne fait pas :**

- déduire Yandex Cloud de demandes génériques SSH, Kubernetes, Terraform ou
  de déploiement sans contexte de fournisseur ;
- stocker des identifiants dans la configuration partagée du projet ;
- appliquer une modification avant d’avoir établi la cible, le contexte et l’autorisation.

**Comment l’invoquer :**

```text
$operate-yandex-cloud Configure this project for Yandex Cloud operations.
```

### Évolution de la collection de skills

#### `discover-skill-candidates` (expérimental)

Trouvez des idées de skills réutilisables dans des preuves de projet et de
contexte délimitées, sans créer de skill.

**Ce qu’il fait :**

- inventorie des fichiers `AGENTS.md` délimités et relatifs au projet avec
  une provenance Git et au niveau des lignes ;
- inventorie facultativement la documentation du projet, des fichiers
  sélectionnés, un historique Git délimité, des métadonnées de structure et des
  résumés confirmés par l’utilisateur issus des conversations disponibles ou
  de transmissions `sync-project-context` ;
- classe les candidats comme recommandés, à examiner ou rejetés et les
  compare aux catalogues existants ;
- propose de manière proactive chaque candidat admissible pour une
  contribution sûre à `kolabse/skills`, une création locale ou un report ;
- exporte une idée sélectionnée sous forme de dossier de contribution expurgé
  et lié à une empreinte, que les responsables peuvent valider indépendamment.

**Ce qu’il ne fait pas :**

- modifier les règles du projet ni générer la structure, publier ou installer un skill ;
- énumérer les conversations, ingérer des transcriptions brutes ou parcourir
  largement le code source ;
- exporter des règles brutes, chemins locaux, secrets, URL ou adresses e-mail ;
- promouvoir sans revue des conventions portant uniquement sur des règles, volatiles,
  sensibles ou ponctuelles en workflows réutilisables.

**Comment l’invoquer :**

```text
$discover-skill-candidates Analyze this project's local rules and prepare an evidence-backed backlog of reusable skill ideas without creating anything.
```

#### `release-skill-collection`

Planifiez, vérifiez, auditez et nettoyez les publications déterministes d’une
collection de skills.

**Ce qu’il fait :**

- vérifie les versions, la préparation du journal des modifications, l’état
  du dépôt, les tests, la sécurité, les archives déterministes et les sommes de contrôle ;
- valide les preuves liées au commit concernant le jeu de contrôle réservé,
  les installations des agents cibles, les plateformes, la revue et les contrôles locaux ;
- audite les artefacts GitHub immuables, manifestes, sommes de contrôle et attestations ;
- prouve si les branches temporaires sont fusionnées, ont un arbre identique
  ou des patchs équivalents avant le nettoyage ;
- n’applique un nettoyage explicitement confirmé qu’à partir d’un plan sûr
  inchangé et d’un audit de la version publiée dont l’empreinte est valide.

**Ce qu’il ne fait pas :**

- déduire l’autorisation de committer, taguer, pousser, déclencher des
  workflows ou publier des artefacts ;
- déplacer un tag existant ou remplacer des artefacts publiés ;
- supprimer des branches d’après leur seul nom, un plan périmé ou une version non auditée.

**Comment l’invoquer :**

```text
$release-skill-collection Plan and verify release vX.Y.Z of this skill collection, but do not publish it yet.
```

## Compositions prises en charge

Le catalogue définit trois workflows ordonnés réutilisables :

- `protected-push` : synchroniser les dépôts, puis produire des preuves de
  vérification actuelles ; le journal de travail et la notification Telegram sont facultatifs.
- `yandex-cloud-operation` : synchroniser les dépôts, puis exécuter l’opération
  cloud délimitée ; la vérification, le journal de travail et la notification
  Telegram sont facultatifs lorsque la politique du projet les active.
- `skill-collection-release` : synchroniser le dépôt, planifier et vérifier
  localement la publication de la collection, puis lier les preuves avant
  push ; le journal de travail et la notification Telegram sont facultatifs.
Les étapes requises bloquent en cas d’échec ou d’incertitude. La
journalisation et la notification facultatives signalent leur propre échec
sans changer le résultat observé de l’opération principale. Résolvez un plan
exact avec `scripts/compose_skills.py` ; passez `--evidence` avec un document
lié à une empreinte conforme à `schemas/composition-evidence.schema.json`
pour vérifier l’ordre des étapes, les résultats requis et les échecs
facultatifs non bloquants. Le résultat vérifié suit
`schemas/composition-result.schema.json`.

## Ajouter un skill

Suivez [CONTRIBUTING.md](CONTRIBUTING.md) et partez de
[`templates/skill-template.md`](../../../templates/skill-template.md). Chaque
skill doit avoir une entrée correspondante dans `skill-catalog.json` indiquant
son responsable, ses plateformes, son statut, sa licence et sa provenance.
Conservez la configuration propre au projet hors du dossier du skill installé
afin que les mises à jour ne puissent pas l’écraser.

N’ajoutez pas d’installateur au niveau du dépôt pour un skill individuel.
Lorsque la collection nécessite une installation et des mises à jour gérées
dans ChatGPT et Codex, distribuez-la comme plugin OpenAI en complément de
cette structure multi-agent.

Exécutez les contrôles de la collection localement avec :

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py
```

Préparez une suite de déclenchement à l’aveugle pour un sélecteur d’agent ou de modèle avec :

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
```

La suite ne contient que les noms des skills, leurs descriptions publiques,
des identifiants de cas opaques et les prompts. Elle omet les étiquettes
attendues et les raisons de l’auteur. Un sélecteur renvoie un JSON strict
listant chaque skill sélectionné pour chaque cas ; notez les observations avec :

```shell
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

Utilisez `run` avec une commande après `--` pour invoquer un sélecteur qui lit
la suite sur l’entrée standard et écrit les prédictions sur la sortie
standard. Gardez les identifiants du fournisseur hors des arguments de
commande. Le répertoire ignoré `.trigger-evals/` exclut par défaut des commits
les suites, prédictions et rapports générés. Les grandes suites de
développement sont envoyées par défaut en lots de 64 cas liés à une empreinte,
afin que de longues réponses JSON strictes ne tronquent pas les identifiants
opaques des cas. Ajustez cette limite avec `--batch-size` sans exposer au
sélecteur les étiquettes attendues.

Avant une publication, exécutez le jeu de contrôle réservé, versionné
séparément et verrouillé par empreinte, sans l’utiliser pour ajuster les
descriptions pendant le développement :

```shell
python scripts/trigger_evals.py prepare \
  --corpus release-holdout \
  --output .trigger-evals/release-holdout.json
```

Comparez un rapport candidat à un rapport produit pour la même version du jeu de contrôle :

```shell
python scripts/trigger_evals.py compare \
  --candidate .trigger-evals/candidate-report.json \
  --markdown-output .trigger-evals/comparison.md
```

La comparaison bloque lorsque les empreintes des assertions diffèrent ou
lorsque l’exactitude globale, la précision, le rappel ou une métrique par
skill baisse au-delà des limites configurées. Elle utilise par défaut la
référence publiée nommée dans `skill-catalog.json` ; ne passez `--baseline`
que pour comparer délibérément avec un autre rapport compatible.

Pour les sélecteurs de modèle non déterministes, recueillez un nombre impair
d’au moins trois exécutions de prédiction à l’aveugle et notez leur décision majoritaire :

```shell
python scripts/trigger_evals.py aggregate \
  --corpus release-holdout \
  --predictions run-1.json run-2.json run-3.json \
  --predictions-output .trigger-evals/aggregate.json \
  --json-output .trigger-evals/candidate-report.json
```

## Vérifier une version publiée

Les versions publiées comprennent des archives ZIP et TAR.GZ déterministes,
`release-manifest.json` et `SHA256SUMS`. Téléchargez les quatre artefacts dans
un même répertoire et vérifiez-les avec :

```shell
python scripts/build_release.py --verify <download-directory>/SHA256SUMS
```

GitHub expose aussi un `digest` SHA-256 pour chaque artefact de publication
téléversé. Les workflows de publication publient en outre des attestations
d’artefacts GitHub. Vérifiez un artefact téléchargé par rapport à ce dépôt avec :

```shell
gh attestation verify <artifact> --repo kolabse/skills
```
