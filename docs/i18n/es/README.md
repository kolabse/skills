# kolabse/skills

[English](../../../README.md) | [Русский](../ru/README.md) | Español | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Português (Brasil)](../pt-BR/README.md) | [日本語](../ja/README.md) | [Italiano](../it/README.md) | [한국어](../ko/README.md) | [简体中文](../zh-CN/README.md) | [Türkçe](../tr/README.md) | [Polski](../pl/README.md) | [Українська](../uk/README.md)

Habilidades reutilizables para agentes, mantenidas por kolabse.

Distribuido bajo la [Licencia Apache 2.0](../../../LICENSE). Copyright 2026 kolabse.

## Tabla de contenidos

- [Instalar habilidades](#instalar-habilidades)
  - [Instalar desde los marketplaces de Git](#instalar-desde-los-marketplaces-de-git)
- [Actualizar las habilidades instaladas](#actualizar-las-habilidades-instaladas)
  - [Ejecutar sin clonar el repositorio](#ejecutar-sin-clonar-el-repositorio)
  - [Inspeccionar instalaciones globales](#inspeccionar-instalaciones-globales)
- [Instalar o actualizar un plugin local de Codex para desarrollo](#instalar-o-actualizar-un-plugin-local-de-codex-para-desarrollo)
- [Habilidades disponibles](#habilidades-disponibles)
  - [Desarrollo y calidad del código](#desarrollo-y-calidad-del-código)
    - [`develop-with-test-first-evidence`](#develop-with-test-first-evidence-experimental)
    - [`review-code-changes`](#review-code-changes-experimental)
    - [`diagnose-software-defects`](#diagnose-software-defects-experimental)
    - [`resolve-git-conflicts`](#resolve-git-conflicts-experimental)
  - [Repositorios y entrega de cambios](#repositorios-y-entrega-de-cambios)
    - [`synchronize-git-repositories`](#synchronize-git-repositories)
    - [`verify-before-push`](#verify-before-push)
    - [`coordinate-code-documentation-repositories`](#coordinate-code-documentation-repositories-experimental)
    - [`execute-configured-gitflow-releases`](#execute-configured-gitflow-releases-experimental)
    - [`execute-verified-development-lifecycle`](#execute-verified-development-lifecycle-experimental)
  - [Conocimiento y continuidad del proyecto](#conocimiento-y-continuidad-del-proyecto)
    - [`maintain-work-log`](#maintain-work-log)
    - [`maintain-project-digest`](#maintain-project-digest-experimental)
    - [`sync-project-context`](#sync-project-context)
  - [Coordinación y comunicación](#coordinación-y-comunicación)
    - [`orchestrate-agent-work`](#orchestrate-agent-work-experimental)
    - [`synchronize-team-skills`](#synchronize-team-skills-experimental)
    - [`report-skill-feedback`](#report-skill-feedback-experimental)
    - [`notify-via-telegram`](#notify-via-telegram)
  - [Infraestructura y operaciones](#infraestructura-y-operaciones)
    - [`operate-yandex-cloud`](#operate-yandex-cloud)
  - [Evolución de la colección de habilidades](#evolución-de-la-colección-de-habilidades)
    - [`discover-skill-candidates`](#discover-skill-candidates-experimental)
    - [`release-skill-collection`](#release-skill-collection)
- [Composiciones compatibles](#composiciones-compatibles)
- [Añadir una habilidad](#añadir-una-habilidad)
- [Verificar una versión](#verificar-una-versión)

## Instalar habilidades

Instale una o más habilidades globalmente para el usuario actual con la CLI
multiagente [`skills`](https://skills.sh):

```shell
npx skills@latest add kolabse/skills --global
```

El CLI descubre las carpetas bajo `skills/`, le permite seleccionar qué habilidades a
instalar, y copiarlos a los agentes de codificación seleccionados. Es un exterior
instalador; este repositorio no publica ni ejecuta su propio paquete npm.

Los usuarios de Codex pueden pedir alternativamente `$skill-installer` para instalar una habilidad desde
este repositorio, por ejemplo de:

```text
https://github.com/kolabse/skills/tree/main/skills/operate-yandex-cloud
```

Elija un consumidor explícito para la instalación no interactiva:

```shell
npx skills@1.5.22 add kolabse/skills --agent codex --copy --global -y
npx skills@1.5.22 add kolabse/skills --agent claude-code --copy --global -y
```

Pida al agente: «Instala globalmente las habilidades seleccionadas e inicializa
solo la configuración ausente de este proyecto sin sustituir nuestras reglas».
Después use la ruta global de la habilidad:

```shell
python ~/.agents/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent codex --apply --yes --json
python ~/.claude/skills/synchronize-git-repositories/scripts/configure_project.py bootstrap --project-path . --agent claude-code --apply --yes --json
```

Las convenciones no declaradas usan `feature/`, `bugfix/`, `release/`, `hotfix/`
y los tipos de commit `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
Los prefijos, roles de ramas y formatos explícitos del proyecto tienen prioridad.
No se crean ramas persistentes ni hooks de Git. Las actualizaciones globales
gestionadas ejecutan el mismo bootstrap para el proyecto activo seleccionado;
sin confirmación, solo lo planifican.

Inicialice inmediatamente el contrato del ciclo de vida del proyecto cuando
los valores observables sean suficientes (use la ruta
de su agente):

```shell
python ~/.agents/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent codex --apply --yes --json
python ~/.claude/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py bootstrap --project-root . --agent claude-code --apply --yes --json
```

Una instalación global de marketplace/plugin no conoce el proyecto activo, por
lo que la habilidad ejecuta el mismo bootstrap en el primer uso del proyecto.

Las rutas globales compatibles son `~/.agents/skills/` para Codex y
`~/.claude/skills/` para Claude Code. Los proyectos conservan únicamente la
configuración, las reglas gestionadas y los ajustes intencionales fuera de esas
carpetas de payload.

El repositorio también está empaquetado como sólo las habilidades `kolabse-skills` plugin para
ChatGPT/Codex y Claude Code. Cada carpeta debajo `skills/` está incluido.
Cross-agent `npx skills` la instalación sigue disponible independientemente de
formato plugin.

### Instalar desde los marketplaces de Git

Los usuarios de Codex pueden registrar el mercado del repositorio e instalar el completo
colección con:

```shell
codex plugin marketplace add kolabse/skills --ref main
codex plugin add kolabse-skills@kolabse
```

Refrescar la instantánea Git y reinstalar la versión actual del plugin con:

```shell
codex plugin marketplace upgrade kolabse
codex plugin add kolabse-skills@kolabse
```

Los usuarios de Claude Code pueden registrar el mismo repositorio e instalar el plugin con:

```shell
claude plugin marketplace add kolabse/skills
claude plugin install kolabse-skills@kolabse
```

Refrésalo explícitamente con `claude plugin marketplace update kolabse`o
habilitar el mercado auto-actualizado en el Código Claude. Iniciar una nueva sesión de agente después
instalar o actualizar para que descubra el conjunto de habilidades actual.

Los catálogos de mercado son
[`.agents/plugins/marketplace.json`](../../../.agents/plugins/marketplace.json) y
[`.claude-plugin/marketplace.json`](../../../.claude-plugin/marketplace.json). Sus
Las cargas de pago plugin se describen por
[`.codex-plugin/plugin.json`](../../../.codex-plugin/plugin.json) y
[`.claude-plugin/plugin.json`](../../../.claude-plugin/plugin.json). Ambos catálogos buscar
la canónica `kolabse/skills` repositorio de `main`; versión de lanzamiento
permanece autorizado en los manifiestos del plugin.

Los materiales de lista pública se mantienen con la fuente: [Apoyo](../../../SUPPORT.md),
[Política de privacidad](../../../PRIVACY.md), [términos de uso](../../../TERMS.md), y el reproducible
[paquete de presentación del mercado](../../../docs/marketplace-submissions/). Publicación a
un directorio oficial sigue siendo una acción de mantenimiento revisada;
el mercado Git no requiere la aprobación del directorio.

Claude Code puede cargar una liberación extraída o un checkout de confianza directamente mientras
pruebas con `claude --plugin-dir <collection-root>`. Para personal ordinario o
uso del proyecto, prefiere el mercado Git o el explícito
`npx skills ... --agent claude-code` comando arriba. El Código de Claude dice:
`CLAUDE.md`, no `AGENTS.md`; cuando un proyecto ya
ha compartido `AGENTS.md` reglas, un mínimo `CLAUDE.md` que contiene `@AGENTS.md`
conserva un documento de reglas canónicas.

## Actualizar las habilidades instaladas

La CLI `skills` registra fuentes globales y hashes de contenido en
`~/.agents/.skill-lock.json`. Actualice las instalaciones globales desde sus
fuentes registradas:

```shell
npx skills@1.5.22 update -g -y
```

Actualizar una habilidad o instalaciones globales con:

```shell
npx skills@1.5.22 update verify-before-push -g -y
npx skills@1.5.22 update -g -y
```

Las copias antiguas instaladas en el proyecto deben centralizarse después de
revisar el plan. La migración instala y verifica primero la copia global, crea
una copia de seguridad y conserva la configuración del proyecto y habilidades ajenas:

```shell
python scripts/centralize_skill_installations.py plan --project-path . --json
python scripts/centralize_skill_installations.py apply --project-path . --expected-plan-sha256 <plan-value> --yes --json
```

Un no calificado `kolabse/skills` cerradura sigue la rama predeterminada del repositorio;
no fija una versión de la colección. No edite los payloads globales copiados,
porque una actualización puede sustituirlos. La configuración del proyecto y
del usuario permanece fuera de las carpetas instaladas.

Desde un archivo de registro o liberación clonado, actualización y migrar proyecto compatible
configuración en una operación explícita:

```shell
python scripts/manage_installed_skills.py update --scope global --project-path . --yes --migrate
python scripts/manage_installed_skills.py doctor --scope global --project-path . --json
```

Previsualizar la selección exacta sin invocar el instalador externo o cambiar
configuración:

```shell
python scripts/manage_installed_skills.py plan --scope global --project-path . --json
```

El plan reporta identidad fuente, versiones actuales y específicas, procedencia,
candidatos a la migración y `update`, `unchanged`, `adopt-and-update`o
`blocked` acciones. Su esquema es `schemas/manager-plan.schema.json`. Add
`--json` a `update`; actualización y seguimiento de los resultados migratorios
`schemas/manager-result.schema.json`.

Sin nombres, el manager resuelve únicamente las habilidades kolabse del lock
global; las habilidades globales ajenas nunca se incluyen. La actualización de
proyecto antigua se conserva solo como transición para el aviso y la migración.
Cuando se actualiza globalmente `execute-verified-development-lifecycle`, el manager también
crea la configuración ausente cuando los hechos del proyecto son suficientes y
devuelve `created`, `configured` o `blocked` como resultado de configuración.

Añadir `--include-user-config` sólo cuando la configuración del usuario de Telegram debe ser
Migraron también. `status` y `doctor` son sólo lectura. `migrate` cambios
archivos de configuración que ya existen; no configura habilidades no utilizadas.
Cada habilidad instalada lleva `collection-metadata.json`Así que `status` informes
versión de colección a pesar de que el formato de bloqueo externo no tiene campo de versión.
It also reports `provenance_status`: `verified` requiere ambas colecciones
metadatos y una fuente de bloqueo local verificada por contenido canónico GitHub;
`legacy-unverified` Identifica una instalación de premetadatos; `mismatch` Nunca
actualizado. Un checkout puede ser renombrado porque la identidad local viene de su plugin
manifiesto, catálogo y contenidos de habilidad en lugar del nombre del directorio.

Adoptar una instalación sin metadatos pre-v1.2 sólo después de revisar su informe
fuente:

```shell
python scripts/manage_installed_skills.py status --scope global --project-path . --json
python scripts/manage_installed_skills.py update --scope global --project-path . --yes --adopt-legacy
```

La bandera de adopción no bendice archivos arbitrarios: la fuente ya debe
normalizar `kolabse/skills` o pasar la validación local de checkout, y la normalidad
el diagnóstico posterior a la fecha debe verificar los metadatos instalados.
El CLI externo no actualiza `sourceType: local` bloqueos de desarrollo en
lugar. El gerente trata que CLI no-op como un fracaso; re-add esas habilidades de
su fuente local con el original `--skill` y `--agent` selecciones.

### Ejecutar sin clonar el repositorio

Descargar `scripts/bootstrap_update.py` de una liberación de confianza o esto
repositorio, entonces déjalo resolver el último lanzamiento estable, verifique la liberación
ZIP contra `SHA256SUMS` GitHub construye la procedencia, y dirige el gerente de
una extracción temporal aislada:

```shell
python bootstrap_update.py doctor --json
python bootstrap_update.py plan --json
python bootstrap_update.py update --yes --migrate --json
```

Uso `--release v1.15.0` para marcar una versión. El bootstrap requiere `gh` para
Attestation verification and removes its temporary directory on completion.
Para un caché fuera de línea, proporcionar ambos `--offline-archive` y
`--offline-checksums`. Queda necesaria la verificación de los progresos `gh` puede
llegar a GitHub. `--allow-unattested-offline` es un modo explícito degradado:
verifica sólo la suma de verificación caché y debe ser utilizado sólo para los artefactos movidos
a través de un canal de confianza independiente. Regresar seleccionando a un mayor
liberación y utilización del procedimiento de devolución en marcha; migraciones de configuración
Sigue adelante solo.

### Inspeccionar instalaciones globales

El Estado global apoyado está deliberadamente ligado a lo compartido
`~/.agents/.skill-lock.json` Cerradura v3. Cargas de pago instaladas en vivo
`~/.agents/skills` para Codex y `~/.claude/skills` para Claude Code. El gerente
no escanea otros directorios de usuarios. Codex sigue siendo el predeterminado; pase
`--agent claude-code` para el diseño de carga de Claude:

```shell
python scripts/manage_installed_skills.py status --scope global --json
python scripts/manage_installed_skills.py doctor --scope global --json
python scripts/manage_installed_skills.py plan verify-before-push --scope global --json
python scripts/manage_installed_skills.py update verify-before-push --scope global --yes --json
python scripts/manage_installed_skills.py status --scope global --agent claude-code --json
```

Uso `--global-root` para la inspección sólo lectura de una prueba o traslado explícitamente
diseño compatible. Las raíces relocadas no pueden ser actualizadas porque el CLI externo
no pueden apuntarlos. Los formatos de bloqueo desconocidos se reportan sin mutación.

Para reenrollar archivos de habilidad, primero retroceda configuración de proyecto/usuario, luego
reinstalar la etiqueta de liberación requerida con las mismas habilidades y objetivos de agente utilizados
para la instalación original, por ejemplo:

```shell
npx skills@1.5.22 add kolabse/skills@v1.1.0 --skill verify-before-push --agent codex --copy --global -y
```

Las migraciones de configuración son sólo de antemano a menos que una liberación explícitamente
los documentos se reducen. Restaurar archivos de habilidad antiguos no reduce el config;
restaurar el respaldo de configuración coincidente cuando la versión anterior no puede leer
el nuevo formato.

## Instalar o actualizar un plugin local de Codex para desarrollo

Para el desarrollo del plugin local, crear/actualizar el personal predeterminado
entrada de mercado, copiar el plugin al directorio de plugin local, añadir un Codex
cachebuster, y activarlo:

```shell
python scripts/install_personal_plugin.py --activate
```

El instalador conserva otras entradas de mercado personales y no edita
el manifiesto del repositorio. Es un camino de desarrollo alternativo, no el normal
Git marketplace installation. Ejecutar de nuevo después de actualizar el checkout, entonces
iniciar una nueva tarea de Codex para que las habilidades actualizadas estén cargadas. Uso `--json` para grabar
la versión instalada, la ruta del plugin, la ruta del mercado y el nombre del mercado.

## Habilidades disponibles

Se identifican habilidades estables y adiciones experimentales `skill-catalog.json`.
Sus trayectorias de configuración orientadas a proyectos, límites de seguridad y documentados
interfaces de comando siguen la política de compatibilidad en
[CONTRIBUCIÓN.md](../../../CONTRIBUTING.md).

Cada entrada de catálogo ahora declara su alcance de configuración, sólo lectura JSON status
mando, capacidades, requisitos y integraciones opcionales. Estado
habilidades también declaran un comando de configuración idempotent; versión JSON/YAML
configuraciones publican un esquema JSON y un comando de migración junto a la habilidad.

El catálogo se agrupa por su finalidad principal para el usuario, en el orden de
prioridad mostrado a continuación. Cada habilidad tiene exactamente una categoría
principal. Las etiquetas independientes describen la fase del ciclo de vida, el
alcance, el comportamiento y las integraciones; el estado de madurez sigue siendo
independiente. Las asignaciones legibles por máquina y el vocabulario controlado
oficiales están en [`skill-catalog.json`](../../../skill-catalog.json), validados
con
[`schemas/skill-catalog.schema.json`](../../../schemas/skill-catalog.schema.json).

Los ejes de etiquetas controladas son:

- fase del ciclo de vida: `prepare`, `investigate`, `implement`, `verify`,
  `publish`, `operate`, `document` y `handoff`;
- alcance: `project`, `repository`, `multi-repository`, `workstation`,
  `external-service` y `skill-collection`;
- comportamiento: `read-only-planning`, `mutation`, `evidence-producing`,
  `orchestration` y `notification`;
- integración: `git`, `github`, `telegram`, `google-drive` y `yandex-cloud`.

### Desarrollo y calidad del código

#### `develop-with-test-first-evidence` (experimental)

Implementar el comportamiento a través de ciclos de refactor rojo respaldados por evidencia.

*Lo que hace*

- registra una prueba enfocada fallando por la razón conductual prevista antes
  aplicación;
- vincula los resultados verdes centrados y más amplios al estado del cambio final;
- valida pruebas duraderas con su esquema y ayudante.

**Lo que no hace:**

- fabricar un resultado rojo rompiendo el comportamiento no relacionado;
- llamar el primer desarrollo de las pruebas después del hecho;
- ocultar fallos preexistentes, ambientales o del estado final.

**Cómo invocarlo:**

```text
$develop-with-test-first-evidence Implement this behavior with a recorded red-green-refactor cycle.
```

#### `review-code-changes` (experimental)

Revise un cambio definido para la corrección, seguridad, fiabilidad y
defectos de compatibilidad.

*Lo que hace*

- resuelve un estado de referencia exacto y cambiado;
- reporta hallazgos respaldados por pruebas con impacto, disparador, prioridad y apretado
  emplazamientos;
- hace explícita la incertidumbre y las lagunas significativas de los ensayos.

**Lo que no hace:**

- reportar preferencias de estilo o especulación sin soporte como defectos;
- implementar conclusiones, publicar comentarios o aprobar un examen sin separado
  autorización;
- sustituir una explicación de código general para un examen abarcado.

**Cómo invocarlo:**

```text
$review-code-changes Review this branch against its declared baseline and report actionable findings.
```

#### `diagnose-software-defects` (experimental)

Investigar fallos y regresiones para producir una explicación causal respaldada
o hipótesis clasificadas.

*Lo que hace*

- límites y reproduce con seguridad el síntoma cuando sea posible;
- pruebas de hipótesis concurrentes con pruebas pertinentes;
- reporte causa raíz, condiciones de contribución, radio de explosión, confianza y
  un plan de verificación de soluciones.

**Lo que no hace:**

- infer causation from correlation;
- mutar la producción o descartar pruebas fallidas;
- implementar una solución especulativa cuando sólo se solicitó el diagnóstico.

**Cómo invocarlo:**

```text
$diagnose-software-defects Diagnose this regression and distinguish evidence from hypotheses.
```

#### `resolve-git-conflicts` (experimental)

Resuelva los conflictos autorizados de fusión, rebase o cereza semánticamente mientras
preservar el trabajo no relacionado.

*Lo que hace*

- inspecciona el funcionamiento activo, la base, ambos lados, y cada camino inmerso;
- reconcilia únicamente los conflictos cuyo comportamiento combinado previsto se entiende;
- valida los caminos resueltos y hace explícita la operación Git restante.

**Lo que no hace:**

- tratar la divergencia de repositorios ordinarios como una tarea de conflictos;
- automáticamente, reajuste, abortar, continuar, fuerza-push, o etapa no relacionada
  caminos;
- adivinar a través de decisiones ambiguas generadas, binarias, esquemas o de productos.

**Cómo invocarlo:**

```text
$resolve-git-conflicts Resolve the active merge conflicts path by path and validate the result.
```


### Repositorios y entrega de cambios

#### `synchronize-git-repositories`

Establecer el estado remoto actual sin sobreescribir el trabajo local.

*Lo que hace*

- descubre sólo los repositorios pertinentes para tareas y corta sus distancias rastreadas;
- rápido hacia adelante limpias ramas detrás de sólo;
- reportes sucios, por delante, divergidos, desprendidos, sin rastrear y en estados de progreso;
- publica una sucursal autorizada de la corriente verificada `main` antes
  la primera edición cuando la política del proyecto lo requiere.

**Lo que no hace:**

- automáticamente apuñalar, restablecer, rebajar, fusionar, limpiar, cambiar o fuerza-push;
- ocultar la divergencia o tratar una embrague exitosa como prueba de que la rama local
  se actualizó;
- escanear o actualizar repositorios no relacionados.

**Cómo invocarlo:**

```text
$synchronize-git-repositories Configure this project's repository synchronization policy.
```

#### `verify-before-push`

Controles declarados por el proyecto Bind al estado Git exacto siendo empujado.

*Lo que hace*

- configura una política de verificación de repositorio fuera de la instalación
  carpeta de habilidad;
- corren cheques declarados y registran evidencia de compromisos exactos, árboles de trabajo,
  estado corriente y configuración de verificación;
- no cierra cuando falta evidencia protegida, falla, malformada o estancada.

**Lo que no hace:**

- bloquear los depósitos no relacionados que no estén cubiertos por la política;
- parse arbitrary shell commands or install an IDE- or agent-specific hook;
- tratar un cheque exitoso de un estado mayor de Git como evidencia actual.

**Cómo invocarlo:**

```text
$verify-before-push Configure this project's verification policy and checks.
```

#### `coordinate-code-documentation-repositories` (experimental)

Coordinar un cambio de proyecto auditable cuando se implemente y canónico
documentación vive en depósitos Git separados.

*Lo que hace*

- resuelve las funciones de ejecución y depósito de documentación declaradas por los proyectos;
- crea un plan de sólo lectura destinado a comenzar los compromisos y al autoritativo
  fuentes de documentación;
- requiere evidencia de documentación para temas configurados como requisitos,
  comportamiento, validación, impacto operativo y limitaciones;
- verifica ambas identidades publicadas, evidencia de validación y
  trazabilidad cruzada del repositorio antes de informar de la terminación conjunta.

**Lo que no hace:**

- inferir funciones de repositorio de nombres de directorios o repositorios;
- sustituir la documentación canónica por un digestión diaria;
- editar, comprometer, empujar, fusionar o reparar depósitos sucios y divergentes por
  en sí mismo;
- reclamar un acuerdo semántico simplemente porque existen archivos de documentación esperados.

**Cómo invocarlo:**

```text
$coordinate-code-documentation-repositories Implement this change across the declared code and canonical documentation repositories and verify both published outcomes.
```

#### `execute-configured-gitflow-releases` (experimental)

Ejecutar rutas de liberación estándar y hotfix de un proyecto declarado GitFlow
contrato.

*Lo que hace*

- resuelve desarrollo, producción, espacio de nombres de hotfix, remoto, puertas y
  política de ruta predeterminada de la configuración de proyecto versionada;
- Congela un plan de sólo lectura destinado al commit fuente y sucursal remota
  identidades;
- aplica las mismas puertas comunes declaradas a las rutas estándar y de hotfix;
- verifica la publicación revisada de la producción, pruebas de despliegue y obligatorios
  hotfix reintegration into the development line.

**Lo que no hace:**

- inferir nombres de rama convencionales o utilizar hotfix como ruta predeterminada;
- apoyar la entrega basada en troncos o la cadena de liberación especializada de esta colección;
- empujar directamente a la producción protegida, pasar por las puertas, reescribir historia, o
  reparar silenciosamente divergencia;
- tratar un hotfix de producción como completo antes de verificar la reintegración.

**Cómo invocarlo:**

```text
$execute-configured-gitflow-releases Run the standard release route declared by this project and verify the resulting production identity.
$execute-configured-gitflow-releases Run an explicit hotfix release and verify its reintegration into the declared development line.
```

#### `execute-verified-development-lifecycle` (experimental)

Planifique y verifique un camino declarado por proyecto desde la preparación de características a través de
examen de la integración del desarrollo, la observación de la ejecución, la documentación y
probada limpieza.

*Lo que hace*

- Congela un plan con digestión antes de la edición y avanza los puestos de control ordenados
  utilizar pruebas retenidas;
- crea una configuración conservadora del proyecto durante una actualización
  gestionada o el primer uso cuando los repositorios, upstream refs, checks y
  documentación son observables, e informa cada valor predeterminado aplicado;
- verifica características antes de editar, prueba-primero, cambio-scopio preflight, revisión,
  presión de estado exacto, tubería, documentación, integración de desarrollo,
  Delegadas de producción, entrega, humo, notificación y puertas de limpieza;
- rebobinado a un puesto de control declarado después del fracaso e invalida el estancamiento
  evidencia abajo.

**Lo que no hace:**

- adivinar adaptadores específicos del proveedor, roles de repositorio,
  política de entrega o autorización cuando la evidencia es ambigua;
- push, open or merge reviews, deployment, notify, edit documentation, or delete
  los propios recursos;
- ejecutar la producción, que sigue delegada en la versión aprobada
  flujo de trabajo, como `$execute-configured-gitflow-releases`.

Instalar y configurar sus habilidades requeridas primero: `$synchronize-git-repositories`,
`$develop-with-test-first-evidence`, `$verify-before-push`, y
`$review-code-changes`. Un contrato de ciclo de vida v1 ausente se crea a partir
de hechos observables antes del primer plan; revise y refine sus valores
predeterminados cuando el proyecto declare una política más específica.
Instalar habilidades opcionales sólo cuando el proyecto
permite sus puestos de control correspondientes: `$orchestrate-agent-work`,
`$diagnose-software-defects`, `$resolve-git-conflicts`,
`$coordinate-code-documentation-repositories`, `$maintain-work-log`,
`$maintain-project-digest`, `$notify-via-telegram`, y
`$execute-configured-gitflow-releases`.

**Cómo invocarlo:**

```text
$execute-verified-development-lifecycle Plan and verify this change through the project's configured development lifecycle.
```


### Conocimiento y continuidad del proyecto

#### `maintain-work-log`

Mantener la revista canónica de fecha del proyecto en `docs/reports/work-log.md`.

*Lo que hace*

- registros de cambios materiales, operaciones, diagnósticos, decisiones, verificación,
  bloqueos y resultados de retroceso;
- preserva el formato de revista existente del proyecto;
- reconstruye la historia perdida de las pruebas disponibles de Git y proyecto-tarea.

**Lo que no hace:**

- activar para el trabajo ordinario a menos que la política de proyecto o el usuario lo requiera;
- escribir secretos, registros de aplicaciones, seguimiento de tiempo o notas personales;
- alegar hechos que no pueden ser respaldados por pruebas disponibles.

**Cómo invocarlo:**

```text
$maintain-work-log Configure this project to maintain its dated work log.
```

#### `maintain-project-digest` (experimental)

Mantener un digest diario y orientado al usuario de los cambios de proyecto completados en el
documentación del proyecto.

*Lo que hace*

- grupos completaron los cambios en la fecha de hoy como nuevas capacidades,
  mejoras, correcciones, seguridad, documentación o cambios importantes de comportamiento;
- escribe breves resultados no técnicos y omite categorías vacías;
- mantiene las fechas más nuevas primero y deja cada fecha anterior sin cambios;
- utiliza un plan con contenido, candado cooperativo, reemplazo atómico y
  la detección duplicada para que varios desarrolladores puedan contribuir de forma segura en un día.

**Lo que no hace:**

- elegir o crear un lugar de documentación cuando el proyecto no identifica
  uno sin ambigüedades;
- planes de registro, experimentos fallidos, actividad de aplicación interna o
  beneficios no compatibles del usuario;
- reemplazar el registro de trabajo técnico, las notas de versión o un registro convencional
  cambio;
- reescribir los períodos históricos de la digestión durante una actualización ordinaria del mismo día.

**Cómo invocarlo:**

```text
$maintain-project-digest Add today's completed user-visible changes to the project digest.
```

#### `sync-project-context`

Synchronize private, sanitized project and per-chat continuing state between
ordenadores. La habilidad es estable después de dos dispositivos reales independientes Google Drive
las carreras pasaron su puerta de promoción determinista.

*Lo que hace*

- almacena puestos de control inmutables en una carpeta sincronizada aprobada o conectada
  Google Drive, con configuración local fuera del repositorio;
- solicitudes de sincronización sin reservas para conectar Google Drive,
  preservando un backend existente y exigiendo una opción explícita antes
  usando una carpeta sincronizada local;
- mantiene una corriente opaca por tarea de proyecto: una línea de referencia detallada seguida
  deltas cortos, títulos visibles, decisiones, verificación, preguntas abiertas,
  los siguientes pasos, y las huellas dactilares Git;
- guarda, restaura o planea bidireccionalmente todas las tareas de proyecto recientes y enmarcadas,
  a la vez que se saltan tareas inalteradas/activas y conflictos de navegación de forma explícita;
- valida las instantáneas descargadas, lee cargas atrás, previene los proyectos cruzados
  restaurar y rechazar patrones secretos de alta confianza;
- registra un entorno separado para reglas declaradas, habilidades, plugins,
  y ajustes de escalar seguros que Git ya no proporciona.

**Lo que no hace:**

- copia de archivos fuente, diffs, transcripciones crudas, razonamiento oculto, credenciales,
  OAuth tokens, o instalaciones de habilidad/plugin;
- duplicar las reglas o dependencias ya realizadas por Git;
- sobreescribir silenciosamente reglas de destino propiedad de Git: aplicar sólo puede crear un
  desaparecidos sin rastreo `AGENTS.md` o `CLAUDE.md` seleccionado para el agente activo
  después de un plan explícito;
- incluir nombres de rama o caminos de archivo en el modo metadatos solamente; títulos de tarea visibles
  permanecer intencionadamente incluido.

Codex Desktop es compatible con el descubrimiento de la tarea por lotes documentado, creación, renombre,
y Google Drive conector flujos de trabajo. Claude Code puede utilizar el portátil
punto de control, almacenamiento de vehículos locales y núcleo de conciliación ambiental, pero su
el almacén de sesión no es inspeccionado y las operaciones de tarea de lote de Codex sólo fallan cerrado
como sin apoyo.

**Cómo invocarlo:**

Configure cada ordenador una vez:

```text
$sync-project-context Configure this clone in metadata-only mode. Use connected Google Drive by default unless I explicitly request another approved channel.
```

A continuación, utilice comandos de nivel de tareas o lotes, por ejemplo:

```text
$sync-project-context Save the current task state.
$sync-project-context Restore all project tasks on this computer.
$sync-project-context Synchronize all project tasks bidirectionally and show conflicts before applying changes.
```

En el Código de Claude, sustitúyase `$` prefijo en estos ejemplos con `/`.


### Coordinación y comunicación

#### `orchestrate-agent-work` (experimental)

Coordinate explicitly authorized subagents while retaining responsibility for
el resultado integrado.

*Lo que hace*

- divide el trabajo paralelo en asignaciones limitadas y no superpuestas;
- Supervisa y reconcilia los resultados de los agentes contra las limitaciones comunes;
- verifica el resultado combinado antes de presentar informes.

**Lo que no hace:**

- Delegar a menos que el usuario o las instrucciones del proyecto autoricen a los subagentes;
- autoridad de aprobación de transferencia, secretos, limpieza destructiva, o no aprobado
  mutaciones externas a otro agente;
- tratar subtascos completados independientemente como prueba de que la integración tuvo éxito.

**Cómo invocarlo:**

```text
$orchestrate-agent-work Delegate these independent subtasks to agents and verify the integrated result.
```

#### `synchronize-team-skills` (experimental)

Mantiene las habilidades globales de cada integrante alineadas con un único
manifest revisado; la configuración del proyecto permanece local.

**Qué hace:**

- crea o lee `team-agent-skills.md` en una ubicación de documentación aprobada;
- compara las habilidades declaradas para Codex y Claude Code con copias
  globales verificadas;
- informa sin cambios sobre habilidades ausentes, antiguas, más nuevas, no
  verificadas, copias de proyecto que prevalecen sobre ámbitos más amplios y
  adicionales conservadas;
- crea un plan ligado al digest del manifest para una versión fijada;
- instala solo el conjunto revisado tras la aprobación y verifica el resultado.

**Qué no hace:**

- no convierte automáticamente el estado accidental de un equipo en política;
- no guarda secretos, configuración personal, rutas locales ni autenticación;
- no elimina habilidades adicionales, baja versiones ni quita silenciosamente
  copias antiguas del proyecto;
- no afirma que una tarea abierta ya haya cargado las habilidades nuevas.

**Cómo invocarlo:**

```text
$synchronize-team-skills Comprueba las habilidades del proyecto con el manifest del equipo.
$synchronize-team-skills Muestra el plan y alinea mis habilidades con la documentación del equipo.
$synchronize-team-skills Añade maintain-project-digest al conjunto de habilidades del equipo.
```

#### `report-skill-feedback` (experimental)

Prepara, tras un consentimiento explícito, un informe limitado y desidentificado sobre un uso observado de una habilidad. El borrador no incluye código, conversaciones, secretos, nombres, rutas ni URL. Se muestra completo y solo se envía a `kolabse/skills` después de una segunda aprobación; el issue seguirá vinculado a la cuenta de GitHub.

**Aufruf / Invocation:**

```text
$report-skill-feedback Prepare a de-identified preview about this observed skill use; do not submit it yet.
```

#### `notify-via-telegram`

Envía actualizaciones de ciclo de vida para tareas de agente de larga duración a través de Telegram.

*Lo que hace*

- informes comienzan, hitos, resultados intermedios, problemas, bloqueadores y
  terminación;
- valida interactivamente el bot y ayuda a descubrir un chat de destino;
- proporciona un formulario de primer uso enmascarado y fácil de pegar para Codex Desktop en Windows;
- almacena credenciales en el directorio de configuración del usuario y envía una prueba
  notificación durante la configuración;
- apoya un tema de chat o foro por proyecto, con una opción explícita
  entre la ejecución de proyectos a nivel mundial y la ejecución de proyectos únicamente;
- Exportaciones de valores libres de secretos para la reconciliación mediante
  `sync-project-context`;
- funciona con la biblioteca estándar Python 3 en Windows, macOS y Linux.

**Lo que no hace:**

- colocar el bot token en la conversación, la historia de la concha o el repositorio;
- copiar el estado global de autenticación de bots o Telegram entre ordenadores;
- enviar notificaciones cuando el usuario pida mantener el progreso en la tarea actual;
- actuar como un marco general de desarrollo de bots Telegram.

**Cómo invocarlo:**

```text
$notify-via-telegram Configure Telegram notifications for long tasks.
$notify-via-telegram Configure this project to notify its team chat only, instead of the global destination.
```


### Infraestructura y operaciones

#### `operate-yandex-cloud`

Operar infraestructura de Yandex Cloud configurada explícitamente.

*Lo que hace*

- almacena los IDs compartidos de Cloud/Folder en la configuración de proyectos y la estación de trabajo
  `yc` perfil en configuración local ignorada;
- detecta las herramientas necesarias, comprueba las versiones mínimas y ejecuta solo lectura
  context preflight;
- soporta el alcance de CLI, SSH, Terraform, Ansible, Helm, Kubernetes, despliegue,
  bases de datos, almacenamiento, DNS, vigilancia, respaldo y flujos de trabajo de incidentes;
- proporciona salida JSON y ayudantes Python multiplataforma.

**Lo que no hace:**

- infer Yandex Cloud de SSH genérico, Kubernetes, Terraform o despliegue
  solicitudes sin contexto de proveedores;
- almacenar credenciales en configuración de proyectos compartidos;
- aplicar una mutación antes de establecer el objetivo, el contexto y la autorización.

**Cómo invocarlo:**

```text
$operate-yandex-cloud Configure this project for Yandex Cloud operations.
```


### Evolución de la colección de habilidades

#### `discover-skill-candidates` (experimental)

Encontrar ideas de habilidad reutilizables en proyecto consolidado y evidencia contextual sin
creando una habilidad.

*Lo que hace*

- inventarios vinculados a proyectos relacionados `AGENTS.md` archivos con Git y
  - Probabilidad de nivel de línea;
- opcionalmente inventories documentación del proyecto, archivos seleccionados, Git atado
  historia, metadatos de estructura y resúmenes confirmados por el usuario desde disponibles
  chats o `sync-project-context` oficios;
- clasifica a los candidatos como recomendados, investigados o rechazados y los compara
  con catálogos existentes;
- Ofrece proactivamente a cada candidato elegible para una contribución segura
  `kolabse/skills`, creación local o aplazamiento;
- exporta una idea seleccionada como un paquete de contribución sanitario y dilatado
  que los usuarios pueden validar independientemente.

**Lo que no hace:**

- modificar las reglas del proyecto, publicar o instalar una habilidad;
- enumerar chats, ingerir transcripciones crudas, o escanear ampliamente código fuente;
- exportar reglas crudas, caminos locales, secretos, URLs o direcciones de correo electrónico;
- promover convenciones sobre políticas únicas, volátiles, sensibles o unilaterales como reutilizables
  flujos de trabajo sin revisión.

**Cómo invocarlo:**

```text
$discover-skill-candidates Analyze this project's local rules and prepare an evidence-backed backlog of reusable skill ideas without creating anything.
```

#### `release-skill-collection`

Planifique, verifique, audite y limpie las liberaciones de recolección de habilidades deterministas.

*Lo que hace*

- versiones de cheques, preparación de cambios, estado de repositorio, pruebas, seguridad,
  archivos determinísticos y sumas de comprobación;
- valida la retención de compromiso, consumidor, plataforma, revisión y cheque local
  pruebas;
- auditorías inmutables de GitHub, manifiestos, sumas de comprobación y certificados;
- prueba si las ramas temporales son fusionadas, idénticas o
  parche-equivalente antes de la limpieza;
- aplica una limpieza confirmada explícitamente sólo de un plan seguro sin cambios y
  una auditoría de la versión publicada.

**Lo que no hace:**

- inferir permiso para cometer, etiquetar, empujar, enviar flujos de trabajo, o publicar activos;
- mover una etiqueta existente o sustituir los activos publicados;
- eliminar ramas de nombres solos, un plan fijo o una liberación no auditada.

**Cómo invocarlo:**

```text
$release-skill-collection Plan and verify release vX.Y.Z of this skill collection, but do not publish it yet.
```

## Composiciones compatibles

El catálogo define tres flujos de trabajo reutilizables:

- `protected-push`: sincronizar los repositorios, luego producir corriente
  evidencia de verificación; registro de trabajo y notificación de Telegram son opcionales.
- `yandex-cloud-operation`: sincronizar los repositorios, luego ejecutar la nube de alcance
  operación; verificación, registro de trabajo y notificación de Telegram
  opcional cuando la política de proyecto les permite.
- `skill-collection-release`: sincronizar el repositorio, plan y localmente
  verificar la liberación de la colección, y luego unir evidencia pre-push; registro de trabajo y
  La notificación de telegramas es opcional.
Los pasos requeridos no cierran. Registros opcionales y notificación reportan su propio
fracaso sin cambiar el resultado observado de la operación primaria. Resolver
un plan exacto con `scripts/compose_skills.py`; paso `--evidence` con una
documento con límite de digestión que coincide `schemas/composition-evidence.schema.json` a
verificar el orden de paso, los resultados requeridos y los fallos opcionales no bloqueantes. El
resultado verificado `schemas/composition-result.schema.json`.

## Añadir una habilidad

Seguir [CONTRIBUCIÓN.md](../../../CONTRIBUTING.md) y empezar desde
[`templates/skill-template.md`](../../../templates/skill-template.md). Cada habilidad debe
tener una coincidencia `skill-catalog.json` entrada que registra a su propietario, plataformas,
estado, licencia y procedencia. Mantenga la configuración específica del proyecto fuera
la carpeta de habilidad instalada por lo que las actualizaciones no pueden sobreescribirla.

No añadir un instalador de nivel de repositorio para una habilidad individual. Cuando el
necesidades de recogida gestionan la instalación y actualizaciones en ChatGPT y Codex,
paquete la colección como un plugin OpenAI además de este cross-agent
diseño.

Ejecute los cheques de la colección localmente con:

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py
```

Prepare una suite de gatillo ciego para un agente o selector de modelo con:

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
```

La suite sólo contiene nombres de habilidad, descripciones públicas, identificaciones de casos opacos y
a los avisos. Omite etiquetas esperadas y razones de autor. Un selector vuelve estricto
JSON enumera cada habilidad seleccionada para cada caso; marque las observaciones con:

```shell
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

Uso `run` con un comando después `--` para invocar un selector que lea la suite
de entrada estándar y escribe predicciones a la salida estándar. Proveedor
credenciales fuera de los argumentos del comando. El ignorado `.trigger-evals/` directorio
mantiene suites, predicciones e informes generados por defecto.
Grandes suites de desarrollo se envían en lotes de 64 casos por
por defecto tan largas respuestas estrictas-JSON no trunquen opaque case IDs. Ajuste
el límite con `--batch-size` sin exponer las etiquetas esperadas al selector.

Antes de una liberación, ejecute el sujetador con versión separada y con bloqueo digestivo sin
utilizarlo para sintonizar descripciones durante el desarrollo:

```shell
python scripts/trigger_evals.py prepare \
  --corpus release-holdout \
  --output .trigger-evals/release-holdout.json
```

Compare un informe de candidato con un informe elaborado para la misma versión de retención:

```shell
python scripts/trigger_evals.py compare \
  --candidate .trigger-evals/candidate-report.json \
  --markdown-output .trigger-evals/comparison.md
```

La comparación falla cerrada cuando la aserción digiere diferencia o precisión general,
precisión, memoria o gotas métricas per-skill más allá de los límites configurados.
Por defecto utiliza la línea de referencia publicada `skill-catalog.json`; paso
`--baseline` sólo cuando se compara intencionalmente con otro informe compatible.

Para los selectores de modelos que no son deterministas, recoger un número extraño de a
menos tres carreras de predicción ciega y marcar su decisión mayoritaria:

```shell
python scripts/trigger_evals.py aggregate \
  --corpus release-holdout \
  --predictions run-1.json run-2.json run-3.json \
  --predictions-output .trigger-evals/aggregate.json \
  --json-output .trigger-evals/candidate-report.json
```

## Verificar una versión

Las versiones revisadas incluyen archivos deterministas ZIP y TAR.GZ,
`release-manifest.json`, y `SHA256SUMS`. Descargar los cuatro activos en uno
directorio y verifique con:

```shell
python scripts/build_release.py --verify <download-directory>/SHA256SUMS
```

GitHub también expone un SHA-256 `digest` para cada activo de lanzamiento subido.
Los flujos de trabajo de lanzamiento publican también las certificaciones de artefactos GitHub. Verificar un
artefacto descargado contra este repositorio con:

```shell
gh attestation verify <artifact> --repo kolabse/skills
```
