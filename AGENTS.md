# AGENTS.md — Prueba técnica Binaural (Desarrollador Odoo)

Prueba de 72h con 4 ejercicios (tramos A/B/C acumulativos). Se puede usar IA, pero lo que se evalúa
es el criterio: cada módulo lleva `README.md` (tramos completados, supuestos, limitaciones) y
`AI_LOG.md` (herramientas, prompts clave, **lo que la IA hizo mal** y cómo se detectó). Documenta
supuestos y sé honesto con lo que quede a medias. Prefiere un tramo bien hecho y probado a dos a medias.

## Versión declarada

- **Odoo 18.0** — declarada en este README y en `instances.json` (instancia `prueba-tecnica`).
- Solo sintaxis 17 o superior: `<list>` (nunca `<tree>`), atributos `invisible`/`readonly` directos
  (nunca `attrs` ni `states`), `ir.cron` sin `numbercall`. El evaluador lo verifica para la versión declarada.
- Antes de generar código de Odoo, usar la skill global `odoo-development-skill` con la versión 18.0
  como objetivo; **verificar sus afirmaciones contra esta versión real** y anotar en `AI_LOG.md`
  cualquier error que cometa la IA (eso puntúa).

## Estructura

Un módulo por ejercicio, todos en `src/custom/prueba-tecnica/`:

| Ejercicio | Módulo | Estado |
|---|---|---|
| 1 — Integración API tienda | `shop_integration_api` | Crear |
| 2 — Migración inspecciones | `fleet_inspection` | Existe en `src/custom/prueba-tecnica-odoo16/` (escrito para 16.0): primer paso de la migración es moverlo a `src/custom/prueba-tecnica/` |
| 3 — Ticket urgente T-200 | `sale_commission` | Existe; hotfix con cambio mínimo, sin reescribir |
| 4 — Solicitudes de pago | `payment_request` | Crear |

Código, nombres técnicos y modelos en inglés; textos visibles al usuario y documentación en español.

## Comandos (desde WSL, raíz del repo)

Ruta del repo en WSL: `/mnt/c/Users/Usuario/dev/docker-odoo`

```bash
./odoo build                      # construir imágenes
./odoo start                      # levantar instancia + DB + nginx
./odoo logs prueba-tecnica        # logs en vivo
./odoo test prueba-tecnica shop_integration_api,fleet_inspection,sale_commission,payment_request
                                  # pruebas sobre base nueva (también: -i / -m / -d prueba_limpia)
./odoo shell prueba-tecnica       # shell de Odoo
./odoo update prueba-tecnica -d prueba_limpia -m sale_commission   # actualizar módulos
```

- Odoo: http://localhost:8069 (admin/admin) · MailHog: http://localhost:8025
- Los módulos que no cierren la iteración se dejan fuera del comando de tests solo si no instalan;
  el objetivo final es que los 4 instalen y pasen juntos.

## Commits

- Pequeños, con prefijo en inglés: `[FEAT]`, `[FIX]`, `[MIG]`, `[TEST]`, `[DOC]`. Nada de un único commit final.
- Ejercicio 3: rama `hotfix/T-200`, commits tipo `[FIX] sale_commission: T-200 …`, y pull request en el fork.

## Seguridad y datos

- Todo modelo nuevo con `security/ir.model.access.csv` (y `ir.rule` si aplica); `sudo()` solo con justificación.
- Pruebas también de lo que un usuario **no** debe poder hacer (permisos, reglas de registro, estado).
- Ningún dato real de clientes, contraseñas ni claves. Las credenciales locales del workspace
  (admin/admin, odoo/odoo) son de desarrollo.
