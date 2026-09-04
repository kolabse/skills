# 隐私政策

[English](../../../PRIVACY.md) | [Русский](../ru/PRIVACY.md) | [Español](../es/PRIVACY.md) | [Français](../fr/PRIVACY.md) | [Deutsch](../de/PRIVACY.md) | [Português (Brasil)](../pt-BR/PRIVACY.md) | [日本語](../ja/PRIVACY.md) | [Italiano](../it/PRIVACY.md) | [한국어](../ko/PRIVACY.md) | 简体中文 | [Türkçe](../tr/PRIVACY.md) | [Polski](../pl/PRIVACY.md) | [Українська](../uk/PRIVACY.md)

本文为简体中文译文。如有差异，以[英文原文](../../../PRIVACY.md)为准。

生效日期：2026-08-24

`kolabse-skills` 是一套开源代理工作流。该集合本身不运营托管服务、不创建用户账户、不收集分析数据，也不向 kolabse 传输遥测数据。

## 处理的信息

技能可能会指示受支持的编码代理检查或修改用户纳入任务范围的文件、Git 仓库、项目配置或其他资源。
处理发生在用户的代理环境中，并受该代理及其所配置模型提供商的隐私条款约束。

部分技能可以使用第三方服务，包括 Google Drive、Telegram、Git 托管提供商和 Yandex Cloud。
只有当用户调用相关工作流并提供或批准所需配置时，技能才会使用这些服务。
这些服务依据各自的隐私政策处理信息。

## 凭据和私有数据

该集合的设计旨在将凭据保留在仓库之外，并避免在日志、发布产物或同步的项目元数据中包含秘密信息。
用户仍有责任审查所请求的访问权限，并决定代理可以处理哪些项目信息，或将哪些信息发送给已配置的第三方。

## 保留和删除

kolabse 不接收或保留技能在本地处理的数据。
本地创建的配置、证据、日志或同步记录由用户控制，可以从相应项目、代理或第三方服务中删除。

## 变更和联系

本政策的重大变更会记录在仓库历史中。如有隐私相关问题，请在
<https://github.com/kolabse/skills/issues> 创建 issue，且不要包含凭据或私有项目数据。
