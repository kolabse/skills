# Política de privacidad

[English](../../../PRIVACY.md) | [Русский](../ru/PRIVACY.md) | Español

Fecha de entrada en vigor: 2026-08-24

`kolabse-skills` es una colección de código abierto de flujos de trabajo para
agentes. La colección no opera un servicio alojado, no crea cuentas de usuario,
no recopila datos analíticos ni transmite telemetría a kolabse.

## Información procesada

Las habilidades pueden indicar a un agente de programación compatible que
inspeccione o modifique archivos, repositorios Git, la configuración del
proyecto u otros recursos que el usuario haya incluido en el alcance. El
procesamiento se realiza en el entorno del agente del usuario y está sujeto a
las condiciones de privacidad de ese agente y de su proveedor de modelos.

Algunas habilidades pueden utilizar servicios de terceros, entre ellos Google
Drive, Telegram, proveedores de alojamiento Git y Yandex Cloud. Solo lo hacen
cuando el usuario ejecuta el flujo de trabajo correspondiente y proporciona o
aprueba la configuración necesaria. Esos servicios procesan la información de
acuerdo con sus propias políticas de privacidad.

## Credenciales y datos privados

La colección está diseñada para mantener las credenciales fuera del repositorio
y evitar que se incluyan secretos en registros, artefactos de versiones o
metadatos sincronizados del proyecto. Los usuarios siguen siendo responsables
de revisar los accesos solicitados y decidir qué información del proyecto puede
procesar un agente o enviar a un tercero configurado.

## Retención y eliminación

kolabse no recibe ni conserva los datos que las habilidades procesan localmente.
El usuario controla la configuración, las evidencias, los registros y los datos
de sincronización creados de forma local, y puede eliminarlos del proyecto, del
agente o del servicio de terceros correspondiente.

## Cambios y contacto

Los cambios sustanciales de esta política se registran en el historial del
repositorio. Para consultas sobre privacidad, abra un issue en
<https://github.com/kolabse/skills/issues> sin incluir credenciales ni datos
privados del proyecto.
