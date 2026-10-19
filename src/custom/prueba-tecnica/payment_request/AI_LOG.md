# AI_LOG — payment_request (tramo A)

## Enfoque

Implementación directa del tramo A en el orden pedido: modelo y secuencia,
validación de monto, transiciones, permisos dentro de los métodos, bloqueo
tras el envío, ACL, record rules, vistas, menú/acción, pruebas y documentación.
Después se hizo una auditoría de seguridad y una corrección mínima (ver abajo).

## Verificación contra Odoo 18 real

Antes de escribir código se contrastaron los supuestos con el código fuente
del 18 (`/usr/lib/python3/dist-packages/odoo`):

- `res.users` sigue usando `groups_id` (no `group_ids`) y `company_ids`.
- Tokens de `ir.sequence`: `%(year)s` y `%(range_year)s` soportados;
  `ir.sequence` tiene ACL de lectura para `base.group_user`, suficiente
  para `next_by_code` desde un solicitante (la numeración se actualiza por
  SQL, sin requerir escritura ORM).
- `Command` se exporta desde `odoo`.

## Decisiones

- Permisos de transición dentro de los métodos (`has_group` → `AccessError`)
  y estado inválido → `UserError`; los `groups=`/`invisible=` de la vista son
  refuerzo, no la única defensa.
- Record rules: una global de compañía y una de grupo para el solicitante.
- `action_reject(reason=None)` acepta el motivo por argumento o leído del
  campo `rejection_reason` (flujo de interfaz), y exige que no esté vacío.
- `write()` bloquea los campos de negocio (solo el dueño puede editarlos en
  borrador) y los campos de flujo/auditoría; las transiciones usan
  `_write_flow()`.

## Auditoría de seguridad y corrección

La primera versión del tramo A solo bloqueaba los campos de negocio después
de `draft`; la auditoría posterior detectó que quedaban escrituras directas
peligrosas:

- `company_id` seguía siendo modificable después de enviar la solicitud.
- `state`, `approved_by_id`, `approved_at` y `rejection_reason` se podían
  escribir directamente por ORM/RPC, saltándose las transiciones (incluso un
  aprobador podía forzar `approved` desde `draft` y Tesorería `paid` sin
  aprobación).
- `create()` aceptaba `state`, auditoría y un `name` arbitrario.
- Los datos de negocio de un borrador ajeno podían editarse con permiso de
  escritura (Aprobador/Tesorería).

Verificación contra el ORM real de Odoo 18:

- `readonly=True` es solo interfaz: el ORM no lo valida en `write()`.
- `_check_company_auto` es `False` por defecto, así que la compañía no se
  valida automáticamente.
- Las record rules evalúan los valores existentes antes de un `write()`.
- En `create()`, la regla se reevalúa sobre el registro nuevo
  (`models.py:5311`), por eso la record rule de compañía sí rechaza una
  creación no autorizada; se verificó con `test_20`.
- Odoo bloquea por RPC los métodos que empiezan con `_` o están decorados
  con `@api.private`.

Corrección aplicada:

- `company_id` se incorporó a `_BUSINESS_FIELDS`.
- `_FLOW_FIELDS = {state, name, approved_by_id, approved_at}` se bloquea
  siempre en `write()` público.
- `rejection_reason` solo lo escribe el grupo Aprobador y solo en
  `submitted`.
- Las acciones usan `_write_flow()`, decorado con `@api.private`, que llama a
  `super().write()`: conserva ACL, record rules y tracking, sin `sudo()`. Se
  eligió `@api.private` porque el método debe ser interno y Odoo ya bloquea
  su invocación por RPC, sin depender de `sudo` ni de contexto.
- `create()` fuerza `draft`, elimina auditoría/motivo y regenera `name`,
  trabajando sobre copias (`dict(vals)`) para no mutar los diccionarios
  recibidos en `vals_list`.
- Se descartó usar banderas de contexto (`skip_validation`, `bypass_flow` o
  equivalentes): un cliente RPC podría proporcionarlas y anular la
  protección. La única excepción es `env.su`, que conserva el comportamiento
  administrativo y no es alcanzable por RPC.

Pruebas agregadas:

- `test_14`: compañía y propietario bloqueados tras el envío.
- `test_15`: `state` no se escribe directamente (solicitante, aprobador,
  tesorería; tampoco volver de aprobado a borrador).
- `test_16`: auditoría no se escribe directamente, ni siquiera por Tesorería
  después de aprobar.
- `test_17`: `rejection_reason` solo Aprobador y solo en `submitted`;
  inmutable tras rechazar.
- `test_18`: `create()` sanea estado, auditoría y nombre.
- `test_19`: solo el solicitante propietario edita datos de negocio en
  borrador; Aprobador y Tesorería reciben `AccessError`.
- `test_20`: la record rule rechaza crear en una compañía no autorizada
  (`AccessError`), sin `sudo()`.

## Pruebas

`./odoo test prueba-tecnica payment_request` sobre base nueva:

- 20 tests, 0 fallos, 0 errores, 0 omitidos; código de salida 0.
- Cobertura 99%: única línea sin cubrir, `write()` línea 124, el retorno para
  `env.su` (comportamiento administrativo intencional, no accesible por RPC).
- Los 13 tests previos siguen pasando; se añadieron `test_14`–`test_20` con
  los casos negativos de la auditoría.
- El log muestra denegaciones reales: record rules (lectura de solicitud
  ajena, de otra compañía y creación en compañía no autorizada) y ACL
  (usuario sin grupos).
- `sudo()`: 0 usos en el módulo; sin banderas `skip_`/`bypass` ni uso de
  `env.context`.
