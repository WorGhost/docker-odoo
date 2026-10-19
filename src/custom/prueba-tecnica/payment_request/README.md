# payment_request — Solicitudes de pago (Ejercicio 4, tramo A)

Módulo Odoo 18 para gestionar solicitudes de pago internas con flujo
borrador → enviada → aprobada → pagada (o rechazada).

## Modelo

`payment.request` hereda `mail.thread` y `mail.activity.mixin`.

Campos: `name`, `partner_id`, `requester_id`, `amount`, `currency_id`,
`request_date`, `concept`, `state`, `company_id`, `approved_by_id`,
`approved_at`, `rejection_reason`.

- Secuencia: `SP/AÑO/NNNN` (`ir.sequence` con código `payment.request`,
  prefijo `SP/%(range_year)s/`, padding 4, compartida entre compañías).
- `amount > 0` validado con `@api.constrains` (`ValidationError`).
- `approved_by_id` y `approved_at` se registran al aprobar.

## Estados y transiciones

| Desde | Acción | Hacia | Permiso |
|---|---|---|---|
| draft | `action_submit` | submitted | solicitante dueño |
| submitted | `action_approve` | approved | grupo Aprobador |
| submitted | `action_reject(reason)` | rejected | grupo Aprobador, motivo obligatorio |
| approved | `action_pay` | paid | grupo Tesorería |

- Transición inválida → `UserError`.
- Falta de permiso → `AccessError` (validado dentro de cada método con
  `has_group`, no solo con botones invisibles).

### Protección de escritura

- Campos de negocio (`partner_id`, `requester_id`, `amount`, `currency_id`,
  `request_date`, `concept`, `company_id`):
  - en `draft`, solo el solicitante propietario puede modificarlos;
  - fuera de `draft`, no se pueden modificar por `write()` → `UserError`;
  - Aprobador y Tesorería pueden ejecutar transiciones, pero no editar datos
    de negocio de borradores ajenos → `AccessError`.
- Campos de flujo y auditoría (`state`, `name`, `approved_by_id`,
  `approved_at`): bloqueados en `write()` para usuarios normales en cualquier
  estado → `UserError`. Solo cambian mediante `action_submit`,
  `action_approve`, `action_reject` y `action_pay`.
- Las acciones usan `_write_flow()`, un método `@api.private` que llama a
  `super().write()`: conserva ACL, record rules y tracking de `mail.thread`,
  no usa `sudo()` ni banderas de contexto. Odoo bloquea por RPC los métodos
  privados.
- `rejection_reason`: la escritura pública solo se permite al grupo Aprobador
  y solo en `submitted` (sin grupo → `AccessError`; estado incorrecto →
  `UserError`). `action_reject()` lo escribe internamente y, tras `rejected`,
  el motivo queda bloqueado.
- `create()` fuerza `state="draft"`, descarta `approved_by_id`, `approved_at`
  y `rejection_reason`, y genera `name` con la secuencia ignorando cualquier
  valor recibido. La record rule de compañía rechaza crear en una compañía no
  permitida → `AccessError`.
- `env.su` conserva la escritura administrativa para preparación de datos y
  tests; no es alcanzable desde RPC.

## Permisos

Grupos: Solicitante, Aprobador, Tesorería (categoría "Solicitudes de pago").

ACL (R/W/C/U):

| Grupo | R | W | C | U |
|---|---|---|---|---|
| Solicitante | 1 | 1 | 1 | 0 |
| Aprobador | 1 | 1 | 0 | 0 |
| Tesorería | 1 | 1 | 0 | 0 |

Record rules:

- Global `company_id in company_ids` (todas las operaciones): aislamiento
  multi-compañía para todos los usuarios.
- De grupo para Solicitante: `requester_id = user.id` (solo ve las suyas).
  Aprobador y Tesorería ven todas las solicitudes de sus compañías permitidas.

## Supuestos

- La secuencia es continua entre años: el año va en el prefijo y NNNN no se
  reinicia.
- `rejection_reason` se puede escribir mientras la solicitud está enviada
  para que el aprobador deje el motivo antes de pulsar "Rechazar"; solo ese
  grupo puede hacerlo, el método exige que no esté vacío y, tras el rechazo,
  el motivo ya no se puede cambiar.
- `currency_id` por defecto es la moneda de la compañía del usuario.
- No se registra qué usuario marcó como pagada (el alcance no define campo).
- En `draft`, el solicitante propietario puede cambiar `company_id` como
  cualquier otro campo de negocio; no se añadió una restricción adicional de
  compañías permitidas en `write()`. La creación en una compañía no permitida
  sí queda rechazada por la record rule.

## Fuera de alcance (tramo A)

`account.payment`, asientos contables, conversión USD/VES, aprobación por
montos, pagos parciales, concurrencia avanzada, tramos B y C.

## Pruebas

```bash
./odoo test prueba-tecnica payment_request
```

Resultado real (Odoo 18, base nueva): **20 tests, 0 fallos, 0 errores,
0 omitidos, 99% de cobertura**, código de salida 0. Cubren secuencia/valores
por defecto, monto cero/negativo, envío, permisos por rol, aprobación,
rechazo con y sin motivo, pago, bloqueo tras envío, visibilidad por
solicitante, aislamiento multi-compañía y ACL para usuarios sin grupos.

Las pruebas 14–20 añaden los casos negativos de la auditoría: bloqueo de
compañía y propietario tras el envío, escritura directa de estado, escritura
directa de auditoría, reglas de `rejection_reason`, saneamiento de `create()`,
edición de borradores solo por el propietario y rechazo de `create()` en una
compañía no autorizada.

Única línea sin cubrir: `write()` línea 124, retorno para `env.su`
(comportamiento administrativo intencional, no accesible por RPC).
