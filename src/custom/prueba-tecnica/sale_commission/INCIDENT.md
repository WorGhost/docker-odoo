# INCIDENT.md — T-200: los vendedores no podían confirmar pedidos de venta

Módulo: `sale_commission` (Odoo 18.0, manifest 1.1.0) · Rama: `hotfix/T-200` · Fecha: 2026-10-18 · Autor del hotfix: Gabriel Izaya

Documento elaborado exclusivamente con evidencia real: historial de git, logs y reportes JSON de las corridas de `./odoo test` del 2026-10-18 (ver sección 12).

## 1. Identificador

| Campo | Valor |
|---|---|
| Ticket | T-200 |
| Módulo | `sale_commission` (Odoo 18.0) |
| Rama | `hotfix/T-200` |
| Commit que introdujo la regresión | `3f4d73f` |
| Commit de la prueba de regresión | `a56b78f` |
| Commit del hotfix | `bc03edd` |
| Severidad | Alta — bloqueo del flujo de confirmación de pedidos para vendedores |
| Estado | Resuelto en `hotfix/T-200`; pull request pendiente |

## 2. Resumen

Desde el commit `3f4d73f` (v1.1.0), la confirmación de un pedido calcula la comisión de cada línea consultando el modelo `sale.commission.rule`. Ese modelo solo tenía ACL de lectura para el grupo Sales/Administrator (gerente), por lo que cualquier vendedor (`sales_team.group_sale_salesman`) recibía un `AccessError` al confirmar un pedido. El gerente podía confirmar sin problemas, lo que explica por qué el defecto pasó inadvertido en la suite original. El hotfix `bc03edd` concede al vendedor únicamente lectura del modelo, lo acota multi-compañía con una record rule global y añade 8 pruebas de seguridad, sin usar `sudo()` y sin tocar modelos, vistas ni el manifest.

## 3. Impacto

- **Afectados:** usuarios del grupo Vendedor de ventas (`sales_team.group_sale_salesman`) al confirmar pedidos, desde la publicación de v1.1.0 (2026-10-16).
- **Síntoma:** `AccessError` al confirmar; el pedido no se confirma. No se observó corrupción de datos en la reproducción automatizada; el AccessError abortó la transacción de confirmación.
- **No afectados:** gerentes (Sales/Administrator) y el superusuario.
- **Alcance técnico:** la confirmación era el síntoma observado, pero no la única operación expuesta: `action_recompute_commissions` también consulta `sale.commission.rule` y podía verse afectada por la misma ACL; su inconsistencia funcional quedó fuera del alcance del hotfix (sección 17).

## 4. Línea de tiempo

| Fecha | Commit / evento | Detalle |
|---|---|---|
| 2026-10-16 | `ad51040` | `[ADD]` sale_commission v1.0.0: comisión del vendedor por línea y análisis mensual. |
| 2026-10-16 | `3f4d73f` | `[FEAT]` v1.1.0 «porcentaje de comisión por categoría de producto»: **introduce la regresión** (nuevo modelo `sale.commission.rule` con ACL solo para gerente y lectura de reglas dentro de `action_confirm`). 10 archivos, +128/−12. |
| 2026-10-16 | `87ac54d` | `[DOC]` README del módulo. |
| 2026-10-18 | `1d9f995` | `[DOC]` entorno de prueba (Odoo 18.0 + PostgreSQL 16); etiqueta `prueba-tecnica-inicio`. |
| 2026-10-18 | `94975c5` | `[DOC]` comandos útiles del entorno en el README. |
| 2026-10-18 | `a56b78f` | `[TEST]` prueba de regresión `tests/test_t200_regression.py` en rojo: reproduce el `AccessError` del vendedor. |
| 2026-10-18 | `bc03edd` | `[FIX]` hotfix: ACL de solo lectura para el vendedor + record rule multi-compañía + 8 pruebas de seguridad. Suite completa: 14/14 en verde. |

Por qué pasó inadvertida desde el 2026-10-16: los 4 tests originales confirman pedidos con el entorno por defecto de `TransactionCase` (superusuario), que no ejecuta ACLs ni record rules; solo `with_user(...)` las aplica.

## 5. Pasos para reproducir

En estado anterior al hotfix (commit `3f4d73f`, sin `bc03edd`):

1. Base de datos limpia con `sale_commission` instalado (v1.1.0).
2. Crear un vendedor con el grupo «Vendedor» (`sales_team.group_sale_salesman`) en la compañía principal.
3. Crear un pedido de venta asignado (`user_id`) a ese vendedor.
4. Confirmar el pedido como ese vendedor (UI, o por ORM: `order.with_user(salesman).action_confirm()`).

Equivalente automatizado (evidencia capturada el 2026-10-18): `./odoo test prueba-tecnica sale_commission --tags /sale_commission:TestT200Regression` con `test_salesman_can_confirm_order` fallando por `AccessError`.

## 6. Resultado esperado

El vendedor confirma su propio pedido sin errores; la comisión por línea se fija con la regla de la categoría (o con el porcentaje del vendedor si no hay regla aplicable); el gerente confirma igual que antes; ninguna de las dos operaciones requiere permisos de administración de reglas.

## 7. Resultado observado

Al confirmar como vendedor (uid 6) se lanzaba:

```
odoo.exceptions.AccessError: You are not allowed to access 'Comisión por categoría de producto' (sale.commission.rule) records.

This operation is allowed for the following groups:
	- Sales/Administrator

Contact your administrator to request access if necessary.
```

Con la cadena real del traceback (reporte JSON de la corrida del 2026-10-18):

- `tests/test_t200_regression.py:56` → `order.with_user(self.salesman).action_confirm()`
- `models/sale_order.py:10` → `line.commission_percent = line._get_commission_percent()`
- `models/sale_order_line.py:28` → `self.env["sale.commission.rule"].search([...])`
- `odoo/models.py:5825` → `self.browse().check_access('read')` → `AccessError`

Y en el log: `Access Denied by ACLs for operation: read, uid: 6, model: sale.commission.rule`.

El gerente confirmaba sin error (test `test_manager_can_confirm_order` en verde en la misma corrida).

## 8. Causa raíz

El camino de confirmación introducido en v1.1.0 lee `sale.commission.rule` actuando como el usuario que confirma. El modelo se creó con una única ACL de lectura para `sales_team.group_sale_manager` (Sales/Administrator); el grupo `group_sale_salesman` no tenía permiso de lectura, de modo que `check_access('read')` abortaba la confirmación del vendedor. No es un problema de datos ni de reglas dinámicas: es una brecha entre un nuevo punto de lectura y la matriz de permisos del modelo consultado. Nótese la inconsistencia previa: el porcentaje resultante ya era visible para el vendedor en sus propias líneas (`commission_percent`), pero el acceso a la fuente (las reglas) estaba vetado.

## 9. Cambio que introdujo la regresión

Commit `3f4d73f` — 2026-10-16, Roque Lopez, «[FEAT] sale_commission: porcentaje de comisión por categoría de producto» (10 archivos, +128/−12):

- Nuevo modelo `sale.commission.rule` (`models/sale_commission_rule.py`) y campo `commission_percent` en `product.category` (`models/product_category.py`), con su vista.
- `models/sale_order.py`: override de `action_confirm` que fija `commission_percent` por línea llamando a `_get_commission_percent()`; además `action_recompute_commissions` (ver sección 17).
- `models/sale_order_line.py`: `_get_commission_percent()`, que busca reglas con `("categ_id", "parent_of", ...)` y `("company_id", "in", [False, self.company_id.id])`.
- `security/ir.model.access.csv`: única ACL nueva para `sale.commission.rule`, solo para el gerente (`1,1,1,1`).
- Manifest a v1.1.0 y 4 tests nuevos (que confirman como superusuario, por lo que no ejercitan la ACL del vendedor).

## 10. Corrección aplicada

Commit `bc03edd` — 2026-10-18, «[FIX] sale_commission: T-200 restaura la confirmación del vendedor» (4 archivos, +118; sin cambios en modelos, vistas ni manifest):

- `security/ir.model.access.csv` (+1): `access_sale_commission_rule_salesman,sale.commission.rule.salesman,model_sale_commission_rule,sales_team.group_sale_salesman,1,0,0,0` — lectura únicamente.
- `security/sale_commission_security.xml` (+1 record rule global, sin grupos): `sale_commission_rule_company` con dominio `[('company_id', 'in', company_ids + [False])]` — solo reglas globales (`company_id=False`) o de las compañías permitidas del usuario.
- `tests/test_commission_rule_security.py` (nuevo, 8 pruebas de la clase `TestCommissionRuleSecurity`) y su registro en `tests/__init__.py`.
- La prueba de regresión `tests/test_t200_regression.py` (commit `a56b78f`) pasa sin ninguna modificación. Sin `sudo()`. `action_recompute_commissions` no se tocó.

## 11. Justificación de mínimo privilegio

- **Necesidad real:** el vendedor necesita leer reglas para calcular y ver la comisión de sus líneas; con `read` basta.
- **`write`/`create`/`unlink` en 0:** la administración de reglas sigue siendo exclusiva del gerente (ACL `1,1,1,1` intacta).
- **No se agregó al vendedor al grupo gerente:** habría concedido CRUD total sobre reglas y todos los permisos heredados de Sales/Administrator (sobre-privilegio).
- **No se usó `sudo()`:** habría eludido a la vez la ACL y la record rule (exposición a reglas de todas las compañías) y habría ocultado la brecha de diseño de permisos. El valor derivado ya es visible para el vendedor en sus líneas, así que no existe justificación extraordinaria para elevar privilegios.
- **Record rule multi-compañía:** la nueva lectura se acota a `company_id=False` o a las compañías permitidas del usuario, evitando exponer por ORM/RPC reglas de otras compañías.
- **Trade-off aceptado:** el vendedor puede enumerar reglas (categoría → porcentaje) de sus propias compañías, lo cual es consistente con que el porcentaje ya se muestra en sus pedidos.

## 12. Validación automatizada

Corridas del 2026-10-18, cada una sobre base de datos nueva, con `./odoo test` desde la raíz del repo (WSL). Los tres veredictos del reporte JSON: `{"passed": true, "fail_reasons": []}`.

| Corrida | Comando | Tests | Fallos | Errores | Exit |
|---|---|---|---|---|---|
| 1 | `./odoo test prueba-tecnica sale_commission --tags /sale_commission:TestT200Regression` | 2 | 0 | 0 | 0 |
| 2 | `./odoo test prueba-tecnica sale_commission --tags /sale_commission:TestCommissionRuleSecurity` | 8 | 0 | 0 | 0 |
| 3 | `./odoo test prueba-tecnica sale_commission` | 14 | 0 | 0 | 0 |

- Corrida 1: `TestT200Regression.test_salesman_can_confirm_order` y `test_manager_can_confirm_order` en verde **sin modificaciones** (el test rojo de `a56b78f` quedó resuelto solo por el fix).
- Corrida 3 (suite completa): 14 tests = 4 de `TestSaleCommission` (originales, intactos) + 2 de `TestT200Regression` + 8 de `TestCommissionRuleSecurity`. Cobertura reportada del módulo: **83 %**.
- Sin llamadas a `sudo()` en el módulo (búsqueda sobre el código: 0 ocurrencias; solo 2 menciones textuales en docstrings que declaran su ausencia).

## 13. Validación multi-compañía

Escenario de `TestCommissionRuleSecurity`: compañía A (principal), compañía B nueva; vendedor con compañías permitidas `[A]`; gerente con `[A, B]`; tres reglas: global (`company_id=False`, 7 %), de A (8 %) y de B (9 %).

- **Vendedor (solo A):** `search([])` devuelve exactamente la regla global y la de A; la regla de B no aparece en búsquedas y su lectura directa lanza `AccessError` de record rules. Log real de la corrida: `Access Denied by record rules for operation: read on record ids: [3], uid: 6, model: sale.commission.rule`.
- **Vendedor puede leer** la regla de su compañía y la global (tests `test_salesman_can_read_applicable_rule`, `test_salesman_can_read_global_rule`).
- **Vendedor no puede crear/modificar/eliminar:** `Access Denied by ACLs for operation: create|write|unlink, uid: 6` (log real de la corrida).
- **Gerente (A+B) conserva CRUD:** creó, modificó y eliminó una regla (log real: `User #7 deleted sale.commission.rule records with IDs: [4]`).
- La record rule es global (sin grupos): aplica a todo usuario no-superusuario; el dominio incluye `company_id=False` para no ocultar las reglas globales.

## 14. Riesgos

- **Exposición de lectura (aceptada):** el vendedor puede enumerar reglas categoría → porcentaje de sus compañías vía ORM/RPC. Consistente con que el porcentaje ya figura en sus líneas; no accede a reglas de otras compañías.
- **La record rule filtra a todo usuario no-superusuario** que consulte el modelo: futuros consumidores (reportes, integraciones) deben contemplar el filtro de compañías y `company_id=False`.
- **Permisos como datos:** en bases existentes hay que actualizar el módulo para aplicar ACL/record rule (no requiere scripts de migración; no hay cambios de esquema).
- **Versión del manifest sin incrementar** (sigue 1.1.0 en este hotfix): la trazabilidad de despliegue queda pendiente de decisión para el cierre del PR.
- `action_recompute_commissions` mantiene semántica inconsistente (sección 17).

## 15. Limitaciones

- La validación es a nivel ORM/RPC mediante tests automatizados; no se hizo verificación clic a clic en la UI web (la UI ejecuta las mismas comprobaciones ORM que dispararon y resolvieron el incidente).
- En `TransactionCase` el arrange corre como superusuario: la cobertura efectiva de permisos depende de los `with_user(...)` explícitos de los tests.
- `action_recompute_commissions` sigue sin corrección y sin cobertura de tests (líneas 15-20 de `models/sale_order.py` sin cubrir en la corrida completa).
- El hotfix no incrementa la versión del manifest ni toca modelos/vistas: deliberado para mantener el cambio mínimo exigido.
- Cobertura del módulo tras el hotfix: 83 % de líneas; las ramas restantes sin cubrir pertenecen a métodos no relacionados con el fix.

## 16. Acciones preventivas

- **Probar los flujos como el usuario que los ejecuta:** todo camino que corra como usuario no-superusuario debe cubrirse con `with_user(...)`; los tests que no cambian de usuario no ejercitan ACLs ni record rules (lección central de T-200).
- **Modelo nuevo ⇒ permisos explícitos:** cada modelo nuevo con su ACL por grupo y, si tiene `company_id`, su record rule multi-compañía; revisar además las rutas ya existentes que pasen a leer el modelo (p. ej. la confirmación de pedidos).
- **Revisar la matriz de permisos con el grupo menos privilegiado** que ejecuta el flujo antes de añadir lecturas en operaciones críticas.
- Mantener la suite completa en verde sobre base limpia antes de cada merge, incluyendo pruebas negativas de permisos (patrón de `tests/test_commission_rule_security.py`).
- Documentar en el README del módulo el contrato de permisos por grupo (quién lee y quién administra las reglas).

## 17. Hallazgo fuera del alcance: `action_recompute_commissions`

Ubicación: `models/sale_order.py` (líneas 13-20), acción expuesta junto a la confirmación de pedidos. Se documenta y **no se corrige en este hotfix**:

- **Utiliza `search` sin dominio de compañía explícito:** `self.env["sale.commission.rule"].search([])` no filtra por `company_id`, a diferencia de `_get_commission_percent`, que usa `("company_id", "in", [False, self.company_id.id])`.
- **No replica el comportamiento jerárquico de categoría:** empareja con igualdad exacta (`r.categ_id == line.product_id.categ_id`), mientras `_get_commission_percent` usa `("categ_id", "parent_of", ...)` y elige la regla más específica; los dos caminos pueden devolver porcentajes distintos.
- **Queda protegida por la nueva record rule:** para usuarios no-superusuario la búsqueda queda limitada a reglas globales y de sus compañías permitidas, de modo que la acción ya no puede alcanzar reglas de otras compañías (y el acceso de lectura del vendedor ya no revienta, como en T-200).
- **Debe tratarse en un ticket independiente:** alinear su dominio de compañía, su semántica jerárquica y añadirle pruebas ampliaría el hotfix más allá del cambio mínimo requerido para T-200; hoy además carece de cobertura de tests.
