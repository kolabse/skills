# Política de Privacidade

[English](../../../PRIVACY.md) | [Русский](../ru/PRIVACY.md) | [Español](../es/PRIVACY.md) | [Français](../fr/PRIVACY.md) | [Deutsch](../de/PRIVACY.md) | Português (Brasil) | [日本語](../ja/PRIVACY.md) | [Italiano](../it/PRIVACY.md) | [한국어](../ko/PRIVACY.md) | [简体中文](../zh-CN/PRIVACY.md) | [Türkçe](../tr/PRIVACY.md)

Esta é uma tradução para português do Brasil. Em caso de divergência, a [versão em inglês](../../../PRIVACY.md) é a referência oficial.

Data de vigência: 2026-08-24

`kolabse-skills` é uma coleção de código aberto de fluxos de trabalho para agentes.
A coleção em si não opera um serviço hospedado, não cria contas de usuário,
não coleta dados analíticos nem transmite telemetria para kolabse.

## Informações processadas

As skills podem instruir um agente de programação compatível a inspecionar ou
modificar arquivos, repositórios Git, configurações de projeto ou outros recursos
que o usuário tenha incluído no escopo. O processamento ocorre no ambiente de
agente do usuário e está sujeito aos termos de privacidade desse agente e de seu
provedor de modelo configurado.

Algumas skills podem usar serviços de terceiros, incluindo Google Drive, Telegram,
provedores de hospedagem Git e Yandex Cloud. Isso ocorre somente quando o usuário
invoca o fluxo de trabalho correspondente e fornece ou aprova a configuração
necessária. Esses serviços processam informações de acordo com suas próprias
políticas de privacidade.

## Credenciais e dados privados

A coleção foi projetada para manter credenciais fora do repositório e evitar a
inclusão de segredos em logs, artefatos de release ou metadados de projeto
sincronizados. Os usuários continuam responsáveis por revisar os acessos
solicitados e escolher quais informações do projeto um agente pode processar ou
enviar a um terceiro configurado.

## Retenção e exclusão

kolabse não recebe nem retém dados processados localmente pelas skills.
Configurações, evidências, logs ou registros de sincronização criados localmente
são controlados pelo usuário e podem ser removidos de seu respectivo projeto,
agente ou serviço de terceiros.

## Alterações e contato

Alterações relevantes nesta política são registradas no histórico do repositório.
Para dúvidas sobre privacidade, abra uma issue em
<https://github.com/kolabse/skills/issues> sem incluir credenciais ou dados
privados do projeto.
