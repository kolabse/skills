# Contribuer des skills

[English](../../../CONTRIBUTING.md) | [Русский](../ru/CONTRIBUTING.md) | [Español](../es/CONTRIBUTING.md) | Français | [Deutsch](../de/CONTRIBUTING.md) | [Português (Brasil)](../pt-BR/CONTRIBUTING.md) | [日本語](../ja/CONTRIBUTING.md) | [Italiano](../it/CONTRIBUTING.md) | [한국어](../ko/CONTRIBUTING.md) | [简体中文](../zh-CN/CONTRIBUTING.md) | [Türkçe](../tr/CONTRIBUTING.md)

Cette traduction est fournie à titre informatif ; la [version anglaise canonique](../../../CONTRIBUTING.md) fait foi en cas de divergence.

Ce dépôt est la source canonique des skills réutilisables de kolabse. Chaque
skill doit rester ciblé, portable, attribuable et installable indépendamment.

## Avant d’ajouter un skill

1. Identifiez la source canonique. Décidez si ce dépôt sera responsable du
   skill ou s’il sera le miroir d’une autre source.
2. Établissez le droit de redistribuer chaque instruction, script, référence
   et ressource copiés. Les contributions originales sont acceptées sous la
   licence Apache-2.0 du dépôt, sauf indication contraire explicite. Conservez
   les fichiers de licence tiers, les mentions de droits d’auteur, les
   attributions et les avis de modification ; consignez leur expression SPDX
   dans le catalogue. Ne publiez aucun contenu tiers dont la licence reste indéterminée.
3. Recherchez dans les descriptions existantes les déclencheurs qui se
   recoupent. Étendez un skill existant lorsque le workflow poursuit le même
   objectif ; ajoutez-en un nouveau lorsqu’il possède un déclencheur et un
   critère d’achèvement utiles indépendamment.
4. Choisissez un nom en minuscules, commençant par un verbe, séparé par des
   traits d’union et ne dépassant pas 63 caractères.

Critère d’achèvement : le responsable, la provenance, la licence, le périmètre
et le nom du skill sont connus avant toute copie de fichiers.

## Suivre un candidat jusqu’à son implémentation

Lorsqu’un skill nouveau ou étendu provient d’une issue GitHub, conservez cette
issue comme élément de travail canonique jusqu’à ce que l’implémentation soit
présente dans la branche principale.

1. Consignez l’issue d’origine dans la pull request d’implémentation.
2. Insérez `Closes #<issue-number>` dans le corps de la pull request. Si la
   modification ne doit pas fermer l’issue, indiquez explicitement la raison
   et le traitement prévu.
3. Après la fusion, inspectez l’issue au lieu de supposer que le mot-clé de
   fermeture a été appliqué. Si elle reste ouverte de manière inattendue,
   fermez-la comme terminée avec des liens vers la pull request
   d’implémentation et, si disponible, la version publiée.
4. Si l’implémentation est rejetée, remplacée ou seulement partiellement
   livrée, laissez un commentaire explicatif et appliquez le traitement
   correspondant à l’issue ; ne déclarez jamais un candidat terminé au seul
   motif qu’une branche ou une pull request a existé.

Critère d’achèvement : chaque candidat implémenté est traçable depuis son issue
d’origine jusqu’à la pull request fusionnée, et l’état final de l’issue a été
vérifié, avec une explication de l’implémentation ou de la non-réalisation.

## Ajouter ou migrer le skill

1. Synchronisez les dépôts source et destination sans écraser le travail local.
2. Créez `skills/<skill-name>/SKILL.md`. Ne conservez que `name` et
   `description` dans son en-tête YAML et faites correspondre le nom du dossier à `name`.
3. Placez les utilitaires déterministes dans `scripts/`, les détails destinés
   à l’agent dans `references/`, les ressources de sortie dans `assets/` et les
   métadonnées d’interface facultatives dans `agents/openai.yaml`. Conservez
   la configuration du projet hors du dossier du skill.
4. Rédigez des étapes à l’impératif, assorties de critères d’achèvement
   vérifiables. Gardez le corps sous 500 lignes ; fournissez les détails
   propres aux différents cas au moyen de références directes.
5. Ajoutez une entrée dans `skill-catalog.json` :
   - `name` et `path` relatif au dépôt ;
   - exactement une `category` principale, selon l’ordre de priorité documenté ;
   - un ou plusieurs `tags` contrôlés pour la phase du cycle de vie, le
     périmètre, le comportement et les intégrations ;
   - `status` : `experimental`, `stable` ou `deprecated` ;
   - les identifiants GitHub dans `maintainers` ;
   - les `platforms` prises en charge ;
   - l’expression SPDX dans `license` ;
   - le type de provenance, la source, les anciens noms et le dépôt canonique.
   Validez les catégories et les tags avec `schemas/skill-catalog.schema.json` ;
   le statut de maturité est indépendant des deux.
6. Ajoutez le skill au catalogue du README avec son objectif, ses notes
   d’installation et l’action requise à la première utilisation.
7. Ajoutez des tests pour les scripts déterministes et des prompts réalistes
   qui doivent ou ne doivent pas déclencher le skill. Stockez au moins trois
   cas positifs et trois cas négatifs proches dans `evals/<skill-name>.json`,
   puis référencez ce fichier dans `skill-catalog.json` sous `trigger_evals`.

Pour un skill migré, conservez son historique dans le catalogue même après que
ce dépôt est devenu canonique. Pour un skill tiers intégré, consignez une
révision source immuable, conservez sa licence et ses mentions dans le dossier
du skill, et séparez les modifications amont des correctifs locaux. Confirmez
la compatibilité des licences avant de combiner du contenu tiers avec du
contenu Apache-2.0.

Critère d’achèvement : un lecteur peut déterminer l’origine du skill, son
responsable, sa licence, les environnements où il s’exécute et sa méthode de validation.

## Contrat de configuration

Chaque skill configurable déclare un objet `configuration` dans
`skill-catalog.json` et respecte les règles suivantes :

- `configure` est un tableau argv, peut être répété sans risque, préserve le
  contenu sans rapport du projet et ne signale aucun changement lors d’un
  deuxième passage identique ;
- `status` est en lecture seule, prend en charge le JSON lisible par machine,
  ne renvoie zéro que si la configuration déclarée est présente et valide,
  et n’affiche jamais de secrets ;
- les périmètres projet et utilisateur sont explicites ; la configuration
  reste hors du répertoire du skill installé ;
- une configuration JSON ou YAML comporte une version entière strictement
  positive, un schéma JSON fourni décrivant son document décodé et une commande
  de migration qui bloque en cas d’incertitude ou d’erreur ;
- le texte géré utilise des marqueurs appariés propres au skill, rejette les
  marqueurs mal formés ou dupliqués et ne réécrit pas le texte hors de son bloc ;
- les skills sans état utilisent le format `none`, n’exposent qu’une commande
  d’état en lecture seule et ne doivent pas inventer d’artefacts de configuration factices.

Les commandes sont stockées sous forme de tableaux, et non de chaînes shell.
Utilisez des paramètres substituables tels que `<project-root>` pour les
valeurs fournies par l’appelant et ne placez jamais d’identifiants dans une
commande du catalogue. Les étapes de migration doivent rester incrémentales
et idempotentes ; rejetez une version plus récente inconnue au lieu de deviner
comment la rétrograder.

Critère d’achèvement : répéter configure produit une sortie identique octet
pour octet là où la configuration existe, status n’écrit rien, les migrations
préservent les entrées prises en charge, et les tests couvrent les
configurations absentes, mal formées, actuelles et anciennes.

## Préserver le parcours de mise à jour des utilisateurs

- Dans une version publiée, gardez identiques les versions de
  `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`,
  `skill-catalog.json.collection_version` et de chaque
  `skills/*/collection-metadata.json`.
- Testez l’installation par copie et la mise à jour depuis la plus ancienne
  version antérieure prise en charge via la CLI `skills` à version épinglée,
  pour `codex` et `claude-code`.
- Installez globalement la collection pour chaque agent. Conservez la configuration,
  les règles gérées et les réglages intentionnels du projet hors des dossiers
  des skills installés. Une mise à jour ne doit jamais créer silencieusement
  une configuration pour un skill inutilisé.
- Après une mise à jour, détectez les anciennes copies propres au projet et affichez
  un avis de centralisation. La migration doit planifier sans écrire, vérifier les
  copies globales avant suppression, préserver les skills sans rapport et la
  configuration, garder une sauvegarde récupérable et exiger une approbation liée au plan.
- Documentez les migrations requises et les limites du retour arrière dans
  le README et le journal des modifications. Considérez la rétrogradation
  d’une configuration comme non prise en charge tant qu’elle n’a pas été testée.
- Préservez les entrées sans rapport lorsque vous modifiez la marketplace
  personnelle. Appliquez un seul suffixe d’invalidation du cache à la copie
  installée du plugin et exigez une nouvelle tâche Codex après activation.

Critère d’achèvement : un utilisateur peut identifier les versions installées,
effectuer une mise à jour, migrer la configuration existante, diagnostiquer des
versions mélangées et réinstaller un tag antérieur sans connaissances privées du dépôt.

## Préserver le comportement entre agents

Gardez les instructions `SKILL.md` et les utilitaires partagés portables.
Codex reste la valeur par défaut des interfaces en ligne de commande
existantes ; une cible Claude Code explicite utilise `.claude/skills`,
`CLAUDE.md` et `/skill-name`. Ne remplacez pas les API de configuration
`.agents` existantes uniquement pour les renommer pour un autre agent cible.

Traitez `agents/openai.yaml` comme des métadonnées d’interface OpenAI et
`.codex-plugin` comme le packaging Codex. Le packaging Claude appartient à
`.claude-plugin` ; aucun manifeste ne doit implicitement tenir lieu de
validation de l’autre. Lorsqu’un agent ne dispose pas d’une capacité telle que
l’énumération des tâches Codex Desktop, signalez cette opération délimitée
comme non prise en charge tout en préservant le sous-ensemble portable.

Critère d’achèvement : les deux installations globales contiennent des contenus de
skills identiques, leurs structures natives de règles de projet et de skills
sont respectées, les valeurs par défaut Codex sont inchangées et les preuves
de tests de fumée des installations nomment explicitement les deux agents.

## Composer les skills par capacité

Déclarez des noms de capacités restreintes dans `provides`, les prérequis
obligatoires dans `requires` et les intégrations non bloquantes dans
`optional_integrations`. N’ajoutez une composition nommée à la collection que
pour un workflow récurrent comportant au moins deux skills. Ses
`required_steps` sont ordonnées ; les `optional_steps` ne s’exécutent que si le
projet ou l’utilisateur a activé leur capacité.

Ne copiez pas le workflow d’un skill dans un autre. Invoquez le skill prérequis,
exploitez son résultat d’achèvement observable et arrêtez-vous lorsqu’une
capacité requise est indisponible. La notification ou la journalisation
facultative ne doit jamais transformer le succès de l’opération principale
en faux succès, ni masquer son échec.

Critère d’achèvement : chaque capacité requise a un fournisseur, les étapes
de composition référencent des skills existants une seule fois, et l’ordre
dispose d’un test d’intégration ou d’un critère d’achèvement exécutable.

## Gérer le statut du cycle de vie

- Gardez un skill nouveau ou sensiblement remanié au statut `experimental`
  jusqu’à la validation de ses métadonnées, de ses utilitaires déterministes,
  de ses tests multiplateformes, de son corpus de déclenchement de
  développement, de son test prospectif indépendant, de son test de fumée
  d’installation par copie et de son jeu de contrôle réservé à la publication.
  Les exigences non pertinentes, comme les scripts fournis pour un workflow
  composé uniquement de prose, peuvent être marquées comme non applicables.
- Ne marquez un skill `stable` que dans une publication versionnée de la
  collection. Ajoutez `stable_since` avec cette version. Stable signifie que
  les entrées documentées, les emplacements de configuration, les limites de
  sécurité et le comportement de la CLI resteront compatibles au sein de la
  version majeure actuelle de la collection ou feront l’objet de conseils de migration.
- Marquez un skill `deprecated` avant son retrait. Nommez son remplacement
  pris en charge ou son parcours de migration dans le skill et le journal des
  modifications, et conservez-le pendant au moins une version mineure, sauf
  si un problème de sécurité urgent exige un retrait plus précoce.

Critère d’achèvement : le statut du cycle de vie s’appuie sur une validation
observable et communique clairement les attentes de compatibilité.

## Préserver la provenance des installations

Considérez un nom de skill connu uniquement comme un candidat, jamais comme
une preuve d’identité de collection. Corrélez la source du fichier de
verrouillage externe avec le `collection-metadata.json` installé. Normalisez
les formes GitHub prises en charge vers `https://github.com/kolabse/skills` ;
vérifiez les sources de développement locales à partir de leur manifeste de
plugin, de leur catalogue et du contenu du skill demandé, sans dépendre du
nom du répertoire de la copie de travail.

Bloquez en présence d’un skill homonyme provenant d’une autre source ou de
métadonnées contradictoires. L’adoption d’installations anciennes doit rester
explicite et n’être autorisée que si la source du verrouillage elle-même a été
vérifiée ; une adoption réussie doit aboutir à des métadonnées actuelles et à
un diagnostic sain après mise à jour.

Critère d’achèvement : status expose la classification de provenance, update
ne sélectionne que des skills vérifiés (ou des skills anciens explicitement
adoptés), et les tests couvrent les collisions de sources, les références de
versions, les copies de travail locales renommées et les installations anciennes.

## Garder l’automatisation utilisateur inspectable

Gardez `plan` en lecture seule : il ne doit invoquer ni installateurs,
ni migrations, ni opérations réseau. Publiez des schémas JSON versionnés
pour les données des plans et des résultats, et distinguez les états inchangé,
mis à jour, migré, ignoré, bloqué et en échec sans analyser la sortie de CLI
destinée aux humains.

Limitez la découverte globale aux emplacements documentés des fichiers de
verrouillage et des installations. Ne parcourez pas le répertoire personnel
pour rechercher d’éventuelles installations. Appliquez les mêmes règles de
provenance, de sélection explicite et de diagnostic après mise à jour au périmètre global.

Le bootstrap autonome doit vérifier la somme de contrôle de l’archive avant
extraction, vérifier la provenance de build GitHub avant exécution, rejeter
les entrées d’archive permettant de sortir du répertoire ou contenant des
liens symboliques, utiliser un répertoire temporaire et propager le code de
sortie du gestionnaire. Réservez l’exécution hors ligne non attestée à une
option explicite de mode dégradé.

Critère d’achèvement : les schémas sont analysables, la simulation laisse les
jeux de données de test identiques octet pour octet, les jeux de test globaux
couvrent les structures prises en charge et ambiguës, et le test de fumée du
bootstrap réussit sur chaque système d’exploitation pris en charge par la CI.

## Valider la modification

Exécutez :

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py --agent codex
python scripts/smoke_install.py --agent claude-code
```

Exercez le corpus de déclenchement avec un véritable agent, y compris le
parcours de première utilisation du skill. Les contrôles structurels de CI
garantissent l’exhaustivité du corpus, mais ne remplacent pas l’observation
de l’invocation du modèle. Incluez les prompts et le résultat observé dans la pull request.

Pour évaluer les déclencheurs de toute la collection, préparez une suite à
l’aveugle et notez les observations du sélecteur :

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

Les sélecteurs peuvent choisir plusieurs skills ou aucun. N’exposez pas au
sélecteur les fichiers d’évaluation sources, les étiquettes attendues, les
raisons de l’auteur, les échecs suspectés ni les rapports précédents. Consignez
l’identité du fournisseur et du modèle dans les métadonnées des prédictions,
conservez les prédictions brutes avec les preuves de revue et inspectez chaque
faux positif et faux négatif avant de modifier une description. Un meilleur
score ne suffit pas à justifier l’élargissement d’un déclencheur si cela rend
ambigus des workflows voisins.

Traitez `evals/release-holdout-vN.json` comme une preuve de publication à ajout
uniquement. Ne lisez ni n’exécutez le jeu de contrôle actif pendant l’ajustement
des descriptions. Les versions existantes de ce jeu sont immuables : créez
`vN+1`, mettez à jour le nom, le chemin et l’empreinte canonique dans le
catalogue, et conservez chaque version publiée. N’exécutez le jeu actif
qu’après avoir figé les descriptions candidates, puis comparez son rapport à
une référence générée avec la même version du jeu et la même configuration de
sélecteur. Ne comparez jamais des rapports dont les empreintes des assertions
diffèrent. Après publication, conservez le rapport accepté sous
`evals/baselines/` et mettez à jour le pointeur de référence du catalogue ; les
fichiers de référence sont des preuves de publication et ne doivent pas être
réécrits. Lorsque le sélecteur n’est pas déterministe, utilisez un nombre
impair d’au moins trois exécutions indépendantes à l’aveugle et comparez
l’agrégat par vote majoritaire. Ne relancez pas une observation unique jusqu’à
ce qu’elle réussisse et n’écartez pas les observations d’échec valides.

Critère d’achèvement : chaque commande réussit sur chaque système
d’exploitation pris en charge, et la liste de contrôle de la pull request
contient les preuves relatives au skill concerné.

## Protéger la chaîne de publication

- Épinglez chaque GitHub Action externe à un SHA de commit complet et
  conservez sa version publiée dans un commentaire. Laissez Dependabot
  proposer des mises à jour de SHA soumises à revue.
- N’accordez à chaque workflow que les permissions `GITHUB_TOKEN` nécessaires.
- Construisez les archives de publication avec `scripts/build_release.py` ;
  vérifiez `SHA256SUMS` avant de téléverser les artefacts.
- Publiez des attestations d’artefacts GitHub pour chaque artefact de
  publication et vérifiez-les avec
  `gh attestation verify <artifact> --repo kolabse/skills`.
- Ne remplacez jamais un artefact de publication existant. Une nouvelle
  exécution du workflow doit vérifier que les octets publiés sont identiques,
  ou échouer.
- Gardez les tags de version immuables. Publiez une correction sous une
  nouvelle version au lieu de déplacer un tag existant ou de remplacer son commit source.

Critère d’achèvement : le tag pointe vers le commit revu, les artefacts
téléversés correspondent à `SHA256SUMS` et les dépendances du workflow sont
des références immuables.
