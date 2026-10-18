# AI_LOG.md — sale_commission / ticket T-200

Fecha: 2026-10-18 · Registro de uso de IA conforme a `AGENTS.md` (herramientas, prompts clave y lo que la IA hizo mal y cómo se detectó). Ninguna salida de IA se aplicó sin contrastarla contra el entorno real: código fuente del contenedor Odoo 18.0, `git log/show` y corridas de `./odoo test`.

## 1. Herramientas utilizadas

| Herramienta | Uso en T-200 |
|---|---|
| OpenCode | Agente de código en el workspace: inspección del módulo y del Odoo 18 real, edición de archivos, generación de diffs y verificaciones del entorno Docker. Los cambios se realizaron bajo instrucciones acotadas y cada diff fue revisado antes de las pruebas y de los commits manuales. |
| GLM-5.3-Flash | Modelo que impulsó OpenCode en esta sesión: apoyó la implementación, las pruebas iniciales y la documentación. |
| Gemini 4 Argon Contributor | Segunda revisión para las alternativas de seguridad y el principio de mínimo privilegio. |
| Odoo Development Skill / odoo-code-reviewer | Convenciones de desarrollo para Odoo 18 (sintaxis 17+, ACL/`ir.rule`) y revisión del cambio de seguridad antes del commit. |
| M365 Copilot | Apoyo en redacción y estructuración de la documentación (secciones del informe). |

## 2. Objetivos para los que se utilizó IA

- Inspeccionar el repositorio y formular la hipótesis inicial sobre la ACL. La causa se **confirmó** ejecutando una prueba real con `with_user(vendedor)`, no solo por análisis de la IA.
- Redactar la prueba de regresión en rojo (`tests/test_t200_regression.py`) y las 8 pruebas de seguridad (`tests/test_commission_rule_security.py`).
- Comparar alternativas de corrección y recomendar la de mínimo privilegio.
- Aplicar el hotfix (ACL de lectura + record rule multi-compañía) y su documentación (`INCIDENT.md`, este `AI_LOG.md`).
- Documentar, sin corregir, `action_recompute_commissions` como hallazgo fuera de alcance.
- La ejecución manual de Git, las corridas de pruebas y los commits correspondieron al candidato, con revisión de cada resultado.

## 3. Prompts relevantes resumidos

- «Analiza `sale_commission` y el ticket T-200; formula hipótesis sobre el `AccessError` del vendedor al confirmar (señalar causa, no síntoma).»
- «Escribe una prueba de regresión que reproduzca el fallo con `with_user(vendedor)`, sin `sudo()` y sin capturar el `AccessError`.»
- «Compara 3 alternativas de fix (ACL de lectura, reestructurar el cálculo, `sudo()`) contra mínimo privilegio, multi-compañía, complejidad y riesgo.»
- «Implementa únicamente: ACL `1,0,0,0` para el vendedor + record rule global `[('company_id','in',company_ids+[False])]` + pruebas de seguridad; muestra el diff antes de correr tests.»
- «Crea `INCIDENT.md` con 17 secciones usando exclusivamente evidencia real (commits, traceback, logs, corridas).»
- «Corrige `INCIDENT.md`: alcance de la operación afectada, afirmación acotada sobre corrupción, orden cronológico con `git log --reverse` y verificación de `bc03edd` con `git show --stat`.»
- «Crea `AI_LOG.md` breve y honesto con estas 8 secciones y estos hechos; no inventes errores adicionales.»

## 4. Trabajo realizado y validado manualmente

- La prueba en rojo (`TestT200Regression`) fue revisada y confirmada manualmente antes del hotfix.
- Los cambios (hotfix, pruebas, documentación) se revisaron con `git diff` antes de ejecutar y de commitear; `git diff --check` sin problemas de whitespace.
- Los commits fueron realizados manualmente: `a56b78f` `[TEST]` (prueba roja) y `bc03edd` `[FIX]` (hotfix).
- Se ejecutaron realmente corridas de 2, 8 y 14 tests sobre base limpia; la corrida final tuvo 0 fallos y 0 errores con cobertura del 83 %; reportes JSON y logs revisados.
- Verificación de referencias con `git log --reverse` y `git show --stat bc03edd`; `py_compile` del archivo nuevo y búsqueda de `sudo()` en el módulo (0 llamadas).

## 5. Alternativas propuestas y descartadas

| Alternativa | Veredicto | Motivo del descarte / adopción |
|---|---|---|
| `sudo()` en el camino de confirmación | Descartada | Omite ACL y record rules: exposición multi-compañía y oculta la brecha de permisos; no hay justificación extraordinaria. |
| Conceder el grupo de gerente al vendedor | Descartada | Exceso de privilegios: CRUD total sobre reglas y permisos heredados de Sales/Administrator. |
| Reestructurar el cálculo para no leer reglas | Descartada | Amplía el alcance (cambia lógica/semántica por compañía) o constituía un `sudo()` encubierto. |
| Duplicar porcentajes en `product.category` | Descartada | Inconsistencia multi-compañía: las reglas pueden ser globales (`company_id=False`) y la duplicación no preserva esa dimensión. |
| ACL de lectura + record rule multi-compañía | **Adoptada** | `read=1` para `group_sale_salesman` acotado por `[('company_id','in',company_ids+[False])]`: mínimo privilegio con aislamiento. |

## 6. Errores o ajustes reales de las respuestas de IA

1. Se describió la confirmación como la única operación expuesta; se corrigió al detectar que `action_recompute_commissions` también consulta las reglas (reflejado en `INCIDENT.md`, secciones 3 y 17). Detectado revisando el código y el diff.
2. Se utilizó una afirmación absoluta sobre ausencia de corrupción de datos; se cambió por una conclusión limitada a la reproducción automatizada. Detectado al revisar qué evidencia realmente respaldaba la frase.
3. La línea de tiempo situaba el README (`87ac54d`) antes del FEAT (`3f4d73f`); se corrigió el orden cronológico de los commits usando `git log --reverse`.
4. Referencia imprecisa de archivo en la sección del hallazgo fuera del alcance (mezclaba `models/sale_commission.py`); corregida a `models/sale_order.py` (líneas 13-20). Detectada en la revisión manual del documento.

## 7. Evidencia utilizada para validar la solución

- Traceback real pre-fix (reporte JSON/log de la corrida del 2026-10-18): `test_t200_regression.py:56` → `sale_order.py:10` → `sale_order_line.py:28` → `odoo/models.py:5825` `check_access('read')` → `AccessError` (solo Sales/Administrator); log `Access Denied by ACLs … uid: 6, model: sale.commission.rule`.
- Inspección del Odoo 18 real en el contenedor: `with_user` aplica ACL/record rules; `company_ids` existe en el contexto de evaluación de `ir.rule`; reglas sin grupos son globales.
- Corridas reales: 2 (TestT200Regression), 8 (TestCommissionRuleSecurity) y 14 (suite completa) → 0 fallos, 0 errores, exit 0, veredictos `passed: true`, cobertura 83 %.
- Logs multi-compañía: denegación por record rules (`ids: [3], uid: 6`) y CRUD del gerente (`User #7 … IDs: [4]`).
- Git: `git diff --check` limpio, `py_compile` OK, 0 llamadas a `sudo()`, `git log --reverse` y `git show --stat` para referencias exactas.

## 8. Alcance no implementado

- `action_recompute_commissions`: se documentó, pero no se corrigió para no ampliar el alcance de T-200 (a tratar en un ticket independiente).
- El manifest se mantiene en 1.1.0 para no mezclar metadatos con el hotfix.
- La normalización a Odoo 18 puede hacerse en un cambio separado.
- El pull request estaba pendiente al redactar el registro.
- Verificación clic a clic en la UI web (la validación fue ORM/RPC con pruebas automatizadas).
