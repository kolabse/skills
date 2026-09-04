# Privacy Policy

English | [Русский](docs/i18n/ru/PRIVACY.md) | [Español](docs/i18n/es/PRIVACY.md) | [Français](docs/i18n/fr/PRIVACY.md) | [Deutsch](docs/i18n/de/PRIVACY.md) | [Português (Brasil)](docs/i18n/pt-BR/PRIVACY.md) | [日本語](docs/i18n/ja/PRIVACY.md) | [Italiano](docs/i18n/it/PRIVACY.md) | [한국어](docs/i18n/ko/PRIVACY.md) | [简体中文](docs/i18n/zh-CN/PRIVACY.md) | [Türkçe](docs/i18n/tr/PRIVACY.md) | [Polski](docs/i18n/pl/PRIVACY.md) | [Українська](docs/i18n/uk/PRIVACY.md)

Effective date: 2026-08-24

`kolabse-skills` is an open-source collection of agent workflows. The
collection itself does not operate a hosted service, create user accounts,
collect analytics, or transmit telemetry to kolabse.

## Information processed

The skills may instruct a supported coding agent to inspect or modify files,
Git repositories, project configuration, or other resources that the user has
placed in scope. Processing occurs in the user's agent environment and is
subject to the privacy terms of that agent and its configured model provider.

Some skills can use third-party services, including Google Drive, Telegram,
Git hosting providers, and Yandex Cloud. They do so only when the user invokes
the relevant workflow and supplies or approves the required configuration.
Those services process information under their own privacy policies.

## Credentials and private data

The collection is designed to keep credentials outside the repository and to
avoid including secrets in logs, release artifacts, or synchronized project
metadata. Users remain responsible for reviewing requested access and for
choosing what project information an agent may process or send to a configured
third party.

## Retention and deletion

kolabse does not receive or retain data processed locally by the skills.
Locally created configuration, evidence, logs, or synchronization records are
controlled by the user and can be removed from their corresponding project,
agent, or third-party service.

## Changes and contact

Material changes to this policy are recorded in the repository history. For
privacy questions, open an issue at
<https://github.com/kolabse/skills/issues> without including credentials or
private project data.
