# Contribuir con habilidades

[English](../../../CONTRIBUTING.md) | [Русский](../ru/CONTRIBUTING.md) | Español | [Français](../fr/CONTRIBUTING.md) | [Deutsch](../de/CONTRIBUTING.md)

Este repositorio es la fuente canónica de las habilidades reutilizables de kolabse.
Cada habilidad debe ser específica, portable, atribuible e instalable de forma independiente.

## Antes de añadir una habilidad

1. Identificar la fuente canónica. Decide si este repositorio será el dueño del
   habilidad o espejo otra fuente.
2. Establecer el derecho a redistribuir todas las instrucciones copiadas, script,
   referencia, y activo. Las contribuciones originales se aceptan en virtud de
   la licencia Apache-2.0 del repositorio a menos que se señale explícitamente otra cosa. Preserve
   archivos de licencia de terceros, avisos de copyright, atribución y modificación
   avisos; grabar su expresión SPDX en el catálogo. No publicar
   material de terceros con licencia sin resolver.
3. Buscar descripciones existentes para los desencadenantes superpuestos. Ampliar una existente
   habilidad cuando el flujo de trabajo tiene el mismo propósito; añadir una nueva habilidad cuando tiene un
   criterio de activación y terminación de manera independiente útil.
4. Elija una minúscula, con verbo, nombre hipnotizado de la mayoría de 63 caracteres.

Criterio de terminación: propiedad, procedencia, licencia, alcance y nombre de habilidad son
conocidos antes de que los archivos sean copiados.

## Seguir un candidato durante la implementación

Cuando una habilidad nueva o extendida se origina de un asunto GitHub, mantenga ese problema
como tema de trabajo canónico hasta que la aplicación esté representada en la primaria
rama.

1. Grabar el asunto fuente en la solicitud de eliminación de la aplicación.
2. Put `Closes #<issue-number>` en el cuerpo de solicitud de tirada. Si el cambio debe
   no cerrar el asunto, indicar la razón y disposición prevista explícitamente.
3. Después de fusionarse, inspeccionar el asunto en lugar de asumir la palabra clave de cierre
   aplicada. Si permanece abierto de forma inesperada, cierre como completado con enlaces
   a la solicitud de implementación y, cuando esté disponible, la liberación.
4. Si se rechaza la aplicación, se superpone o sólo se entrega parcialmente,
   dejar un comentario explicativo y utilizar la disposición correspondiente Edición;
   nunca reportar a un candidato como completado meramente porque una rama o tira
   existía la solicitud.

Criterio de conclusión: cada candidato implementado es rastreable de su fuente
Número a la solicitud de tirada fusionada, y el asunto tiene un estado final verificado con
una explicación de aplicación o no completa.

## Añadir o migrar la habilidad

1. Sincronizar los repositorios de origen y destino sin sobrescribir
   trabajo local.
2. Crear `skills/<skill-name>/SKILL.md`Manténgase `name` y `description` dentro
   y hacer que el nombre de la carpeta coincida `name`.
3. Poner ayudantes deterministas en `scripts/`, detalle de cara a agente
   `references/`, material de salida en `assets/`, y metadatos UI opcionales en
   `agents/openai.yaml`Mantenga la configuración del proyecto fuera de la carpeta de habilidad.
4. Escribir pasos imperativos con criterios de terminación verificables. Mantener el cuerpo
   debajo de 500 líneas; divulgar detalles de ramas específicas mediante referencias directas.
5. Añádase una entrada `skill-catalog.json`:
   - `name` y repositorio relativo `path`;
   - exactamente una `category` principal, respetando el orden de prioridad
     documentado;
   - una o más `tags` controladas para la fase del ciclo de vida, el alcance,
     el comportamiento y las integraciones;
   - `status`: `experimental`, `stable`o `deprecated`;
   - GitHub maneja dentro `maintainers`;
   - apoyo `platforms`;
   - Expresión SPDX en `license`;
   - Tipo de procedencia, fuente, nombres anteriores y repositorio canónico.
   Valide las categorías y etiquetas con
   `schemas/skill-catalog.schema.json`; el estado de madurez es independiente.
6. Añadir la habilidad al catálogo README con su propósito, notas de instalación,
   y requiere acción de primera.
7. Agregue pruebas para scripts deterministas y indicaciones realistas que deben y
   no debe desencadenar la habilidad. Almacene al menos tres positivos y tres cercanos
   casos negativos `evals/<skill-name>.json`, y referencia ese archivo de
   `skill-catalog.json` como `trigger_evals`.

Para una habilidad migrada, preservar su historia en el catálogo incluso después de esto
el repositorio se vuelve canónico. Para una habilidad comercializada, registre una fuente inmutable
revisión, mantener su licencia y avisos en la carpeta de habilidad, y mantener al corriente
cambios separados de parches locales. Confirmar compatibilidad de la licencia antes
combinando contenido de terceros con contenido Apache-2.0.

criterio de terminación: un lector puede determinar de dónde proviene la habilidad, quién
lo posee, cómo está licenciado, dónde funciona y cómo validarlo.

## Contrato de configuración

Cada habilidad configurable declara `configuration` objeto en
`skill-catalog.json` y sigue estas reglas:

- `configure` es un array argv, es seguro de repetir, preserva proyecto no relacionado
  contenido, y no reporta ningún cambio en un segundo paso idéntico;
- `status` sólo lectura, soporta JSON legible por máquina, sale cero sólo cuando
  la configuración declarada está presente y válida, y nunca imprime secretos;
- el proyecto y el alcance del usuario son explícitos; la configuración permanece fuera del ámbito
  directorio de habilidad instalado;
- configuración JSON y YAML tiene una versión de entero positivo, un JSON
  Schema describiendo su documento decodificado, y un comando de migración no cerrado;
- el texto gestionado utiliza marcadores pareados, específicos para habilidades, rechaza malformado o
  duplicar marcadores, y no reescribir texto fuera de su bloque.
- las habilidades apátridas utilizan el formato `none`, exponer sólo un comando de estado de sólo lectura,
  y no debe inventar artefactos de configuración de propietarios de lugares.

Los comandos se almacenan como arrays en lugar de cadenas de shell. Use propietarios de lugares tales
como `<project-root>` para los valores multiplicados por el callador y nunca poner credenciales en
comando de catálogo. Mantener los pasos de migración incremental e idempotente; rechazar un
nueva versión desconocida en lugar de adivinar cómo reducirla.

Criterio de terminación: configuración repetida produce salida byte-identical donde
configuración existe, status performs no writes, migrations preserve supported
entradas y pruebas cubren la configuración desaparecida, malformada, actual y heredada.

## Conservar la ruta de actualización del consumidor

- Quédate. `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`,
  `skill-catalog.json.collection_version`, y todos
  `skills/*/collection-metadata.json` versión idéntica en una versión.
- Prueba de instalación copiada y una actualización de la más antigua
  la liberación a través del pinned `skills` CLI para ambos `codex` y `claude-code`.
- Mantenga la configuración del proyecto/usuario fuera de carpetas de habilidad instaladas. Nunca hagas
  un actualizador silenciosamente crear configuración para una habilidad no usada.
- El documento requiere migraciones y limitaciones de reversión en el README y
  cambio. Trate a la configuración baja como no compatible a menos que se pruebe.
- Preserve entradas no relacionadas al cambiar el mercado personal. Aplicar uno
  cachebuster suffix a la copia de plugin instalada y requieren una nueva tarea Codex
  después de la activación.

criterio de terminación: un consumidor puede identificar versiones instaladas, actualizar,
migrar la configuración existente, diagnosticar versiones mixtas, y reinstalar antes
tag sin confiar en el repositorio-conocimiento privado.

## Conservar el comportamiento entre agentes

Mantener compartido `SKILL.md` instrucciones y ayudantes portátiles. Codex sigue siendo el
default for existing command-line interfaces; an explicit Claude Code target
usos `.claude/skills`, `CLAUDE.md`, y `/skill-name`. No sustituir las existentes
`.agents` configuración APIs simplemente para renombrarlos para otro consumidor.

Treat `agents/openai.yaml` como metadatos de OpenAI UI y `.codex-plugin` como Codex
Embalaje. Claude packaging pertenece al `.claude-plugin`; ninguna manifestación puede
silenciosamente para la validación de la otra. Cuando un agente carece de capacidad
tales como la enumeración de tareas de Codex Desktop, informe que el funcionamiento consolidado como
sin soporte mientras preserva el subconjunto portátil.

Criterio de terminación: ambas instalaciones del consumidor contienen cargas de habilidad idénticas,
sus reglas de proyecto nativo y diseños de habilidades son respetados, Codex defaults son
Las pruebas sin cambios, y el consumo de humo nombres de ambos agentes explícitamente.

## Componer habilidades por capacidad

Declare nombres de capacidades pequeñas en `provides`, requisitos obligatorios en
`requires`, y las integraciones no bloqueantes en `optional_integrations`. Añadir un
nombrada composición de colección sólo para un flujo de trabajo recurrente con al menos dos
habilidades. Es... `required_steps` se ordenan; `optional_steps` correr sólo cuando
proyecto o usuario ha habilitado su capacidad.

No copie el flujo de trabajo de una habilidad en otra. Invocar la habilidad previa,
consumir su resultado de terminación observable, y detener cuando una capacidad necesaria
no está disponible. La notificación o registro opcional nunca debe dar un resultado exitoso
operación primaria en un falso éxito, ni ocultar su fracaso.

Criterio de terminación: cada capacidad necesaria tiene un proveedor, composición
pasos referencia las habilidades existentes una vez, y el orden tiene una prueba de integración o
un criterio de terminación ejecutable.

## Gestionar el estado del ciclo de vida

- Mantener una habilidad nueva o modificada materialmente `experimental` hasta sus metadatos,
  ayudantes deterministas, pruebas multiplataforma, desencadenador de desarrollo corpus,
  prueba de humo independiente, copiado-instalación, y la retención de liberación tienen
  todo aprobado. Requisitos que no se aplican, como scripts agrupados para un
  El flujo de trabajo sólo prose, puede ser registrado como no aplicable.
- Marcar una habilidad `stable` sólo en una versión de la colección. Añadir
  `stable_since` con esa versión de lanzamiento. Stable significa aportaciones documentadas,
  ubicaciones de configuración, límites de seguridad y comportamiento CLI permanecerán
  compatible con la versión principal de la colección actual o recibir migración
  orientación.
- Marcar una habilidad `deprecated` antes de retirarse. Nombrar su reemplazo o
  ruta de migración en la habilidad y el cambio, y mantenerlo por al menos una
  liberación menor a menos que una cuestión de seguridad urgente requiera una eliminación anterior.

criterio de terminación: el estado del ciclo de vida está respaldado por validación observable y
comunica una expectativa de compatibilidad clara.

## Conservar la procedencia de la instalación

Tratar un nombre de habilidad conocido sólo como candidato, nunca como identidad de colección.
Correlar la fuente de bloqueo externa con instalado `collection-metadata.json`.
Normalizar ortografías GitHub compatibles a `https://github.com/kolabse/skills`;
verificar las fuentes locales de desarrollo de su manifiesto de plugin, catálogo y
Contenido de habilidad solicitado sin depender del nombre del directorio de checkout.

El fracaso cerró una habilidad del mismo nombre de otra fuente o metadatos contradictorios.
Mantener la adopción heredada explícita y permitirla sólo cuando la fuente de bloqueo en sí es
verificada; la adopción exitosa debe terminar con los metadatos actuales y una adopción saludable
diagnóstico post-actual.

Criterio de terminación: estado expone la clasificación de procedencia, actualización
selecciona sólo habilidades verificadas (o habilidades heredadas explícitamente adoptadas), y pruebas
tapar las colisiones fuente, refres de liberación, chequeos locales renombrados, y legado
instalaciones.

## Mantener inspeccionable la automatización del consumidor

Sigue. `plan` sólo lectura: no debe invocar instaladores, migraciones o red
operaciones. Publish versioned JSON Schemas for plan and result payloads and
distinguir estados sin cambios, actualizados, migrados, saltados, bloqueados y fallidos
sin analizar la producción de CLI orientada al ser humano.

Bound global discovery to documented lock and installation roots. No escaneos
el directorio principal para posibles instalaciones. Aplicar la misma procedencia,
selección explícita y reglas de diagnóstico posteriores a la actualización a nivel mundial.

El bootstrap independiente debe verificar el archivo checksum antes de la extracción,
verificar la procedencia de GitHub antes de la ejecución, rechazar traversal y simlink
entradas de archivos, utilizar un directorio temporal y propagar la salida del administrador
código. Mantenga la ejecución sin restricciones fuera de línea detrás de una bandera degradada explícita.

Criterio de compleción: parse de esquemas, hojas de funcionamiento seco porte-identical fijaciones,
fijaciones globales cubren diseños soportados y ambiguos, y el humo de arranque
pasa por todos los sistemas operativos de CI soportados.

## Validar el cambio

Corre:

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py --agent codex
python scripts/smoke_install.py --agent claude-code
```

Ejercicio del cuerpo de gatillo contra un agente real, incluyendo la habilidad
Primera ruta. Controles de la CI estructural mantienen el cuerpo completo, pero no
sustituir por observar la invocación modelo. Incluya los avisos y observados
result in the pull request.

Para la evaluación del gatillo en toda la colección, prepare una suite ciega y marque la
observaciones selectoras:

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

Los selectores pueden elegir múltiples habilidades o ninguna. No exponga la eval fuente
archivos, etiquetas esperadas, razones de autor, fallos sospechosos o informes anteriores a
el selector. Registrador/identidad modelo en los metadatos de predicción, mantenga
predicciones crudas con la evidencia de revisión, e inspeccionar cada falso positivo y
falso negativo antes de cambiar una descripción. Una puntuación más alta no es suficiente
razón para ampliar un gatillo cuando eso haría que los flujos de trabajo cercanos sean ambiguos.

Treat `evals/release-holdout-vN.json` como sólo un apéndice libera evidencia. No
leer o ejecutar el mantenimiento activo mientras sintoniza descripciones. Existing holdout
versiones son inmutables: crear `vN+1`, actualizar el nombre del catálogo, camino, y
digerir canónico y retener cada versión publicada. Ejecute el control activo
sólo después de que se congelen las descripciones de los candidatos, compare su informe con
una línea de referencia generada a partir de la misma versión de retención y configuración selectora.
Nunca compare informes con diferentes digestión de aserción. Después de la liberación, retenga
el informe aceptado `evals/baselines/` y actualizar el catálogo de referencia
pointer; baseline files are release evidence and must not be rewritten.
Cuando el selector no es determinado, utilice un número impar de al menos tres
corredores ciegos independientes y comparar el agregado de voto mayoritario. No vuelvas a correr
observación única hasta que pase o descarte las observaciones fallidas válidas.

criterio de terminación: cada comando pasa en cada sistema operativo compatible,
y la lista de verificación de la solicitud de tiraje contiene evidencia para la habilidad afectada.

## Proteger la cadena de publicación

- Pin cada GitHub externo Acción a un total commit SHA y conservar su liberación
  versión en un comentario. Deja que Dependabot proponga actualizaciones revisadas de SHA.
- Conceder cada flujo de trabajo sólo sus necesidades `GITHUB_TOKEN` permisos.
- Construir archivos de liberación a través de `scripts/build_release.py`; verificar
  `SHA256SUMS` antes de subir activos.
- Publish GitHub artifact attestations for every release asset and verify them
  con `gh attestation verify <artifact> --repo kolabse/skills`.
- Nunca sustituya un activo de liberación existente. Una repetición de flujo de trabajo debe verificar
  que los bytes publicados son idénticos o fracasan.
- Mantenga las etiquetas de la versión inmutables. Publicar una corrección como nueva versión en su lugar
  de mover una etiqueta existente o reemplazar su confirmación fuente.

Criterio de terminación: la etiqueta se resuelve al commit revisado, el cargado
bienes correspondientes `SHA256SUMS`, y las dependencias de flujo de trabajo son referencias inmutables.
