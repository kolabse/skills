# Politique de confidentialité

[English](../../../PRIVACY.md) | [Русский](../ru/PRIVACY.md) | [Español](../es/PRIVACY.md) | Français | [Deutsch](../de/PRIVACY.md) | [Português (Brasil)](../pt-BR/PRIVACY.md) | [日本語](../ja/PRIVACY.md) | [Italiano](../it/PRIVACY.md) | [한국어](../ko/PRIVACY.md) | [简体中文](../zh-CN/PRIVACY.md) | [Türkçe](../tr/PRIVACY.md) | [Polski](../pl/PRIVACY.md) | [Українська](../uk/PRIVACY.md)

Cette traduction est fournie à titre informatif ; la [version anglaise canonique](../../../PRIVACY.md) fait foi en cas de divergence.

Date d’entrée en vigueur : 2026-08-24

`kolabse-skills` est une collection open source de workflows pour agents. La
collection elle-même n’exploite aucun service hébergé, ne crée aucun compte
utilisateur, ne collecte aucune donnée analytique et ne transmet aucune
télémétrie à kolabse.

## Informations traitées

Les skills peuvent demander à un agent de programmation compatible d’inspecter
ou de modifier des fichiers, des dépôts Git, la configuration d’un projet ou
d’autres ressources que l’utilisateur a incluses dans le périmètre de la tâche.
Le traitement a lieu dans l’environnement d’agent de l’utilisateur et est soumis
aux conditions de confidentialité de cet agent et de son fournisseur de modèle configuré.

Certains skills peuvent utiliser des services tiers, notamment Google Drive,
Telegram, des fournisseurs d’hébergement Git et Yandex Cloud. Ils ne le font
que lorsque l’utilisateur invoque le workflow concerné et fournit ou approuve
la configuration requise. Ces services traitent les informations selon leurs
propres politiques de confidentialité.

## Identifiants et données privées

La collection est conçue pour conserver les identifiants en dehors du dépôt et
éviter d’inclure des secrets dans les journaux, les artefacts de publication ou
les métadonnées de projet synchronisées. Il incombe aux utilisateurs d’examiner
les accès demandés et de choisir quelles informations du projet un agent peut
traiter ou envoyer à un tiers configuré.

## Conservation et suppression

kolabse ne reçoit ni ne conserve les données traitées localement par les skills.
Les configurations, preuves, journaux ou enregistrements de synchronisation
créés localement sont sous le contrôle de l’utilisateur et peuvent être supprimés
du projet, de l’agent ou du service tiers correspondant.

## Modifications et contact

Les modifications importantes de cette politique sont consignées dans
l’historique du dépôt. Pour toute question relative à la confidentialité,
ouvrez une issue sur <https://github.com/kolabse/skills/issues> sans y inclure
d’identifiants ni de données privées du projet.
