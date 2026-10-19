# Prueba técnica — Desarrollador Odoo

## 1. Descripción general

Entrega de los cuatro ejercicios de la prueba técnica, implementados en su
**tramo A** sobre **Odoo 18** y **PostgreSQL 16**. Los módulos viven en
`src/custom/prueba-tecnica/` y se cargan en la instancia local
`prueba-tecnica`.

| Dato | Valor |
|---|---|
| Autor | Gabriel Izaya |
| Odoo | 18 |
| PostgreSQL | 16 |
| Instancia | `prueba-tecnica` |
| Rama | `prueba-tecnica/gabriel-izaya` |
| URL de Odoo | http://localhost:8069 |
| MailHog | http://localhost:8025 |

## 2. Requisitos

- Docker y Docker Compose.
- WSL/Linux con bash para ejecutar el CLI `./odoo`.
- Git.
- Puertos locales `8069` (Odoo) y `8025` (MailHog) disponibles.
- No se requieren datos reales de clientes ni credenciales productivas.

## 3. Configuración inicial

Copiar `instances.example.jsonc` a `instances.json` y declarar la instancia
`prueba-tecnica` con esta carpeta como addons:

```jsonc
"prueba-tecnica": {
  "odoo_version": "18.0",
  "external_port": 8069,
  "database": "pg16",
  "odoo_config": "18.0_full",
  "overwrite_odoo_config": {
    "addons": ["src/custom/prueba-tecnica"],
    "dev_mode": true
  }
}
```

## 4. Construcción e inicio

```bash
./odoo build
./odoo start prueba-tecnica
./odoo logs prueba-tecnica
```

El correo saliente (MailHog) se inicia aparte:

```bash
docker compose -f docker-compose.generated.yml up -d mailhog
```

## 5. URLs locales

- Odoo: http://localhost:8069 — usuario `admin`, contraseña `admin` (entorno
  de desarrollo).
- MailHog: http://localhost:8025

## 6. Estructura de los cuatro módulos

```text
src/custom/prueba-tecnica/
├── shop_integration_api/   # Ejercicio 1: API de consulta de productos
├── fleet_inspection/       # Ejercicio 2: migración Odoo 16 → 18
├── sale_commission/        # Ejercicio 3: incidente T-200
└── payment_request/        # Ejercicio 4: solicitudes de pago
```

Cada módulo incluye `README.md` y `AI_LOG.md`; `sale_commission` incluye
además `INCIDENT.md`.

## 7. Módulos entregados

| Módulo | Ejercicio | Alcance | Tests | Cobertura individual | Estado |
|---|---|---|---:|---:|---|
| `shop_integration_api` | 1 | API de productos, tramo A | 15 | 94 % | Entregado |
| `fleet_inspection` | 2 | Migración de Odoo 16 a 18, tramo A | 9 | 94 % | Entregado |
| `sale_commission` | 3 | Resolución del incidente T-200, tramo A | 14 | 83 % | Entregado |
| `payment_request` | 4 | Solicitudes de pago, tramo A | 20 | 99 % | Entregado |

## 8. Comandos individuales de prueba

Cada comando ejecuta las pruebas del módulo sobre una base nueva:

```bash
./odoo test prueba-tecnica shop_integration_api
./odoo test prueba-tecnica fleet_inspection
./odoo test prueba-tecnica sale_commission
./odoo test prueba-tecnica payment_request
```

## 9. Comando conjunto exacto

```bash
./odoo test prueba-tecnica \
  shop_integration_api,fleet_inspection,sale_commission,payment_request \
  --out-verbose
```

## 10. Resultado conjunto

Resultado real verificado sobre base limpia:

| Métrica | Resultado |
|---|---|
| Tests ejecutados | 58 |
| Success | 58 |
| Fallos | 0 |
| Errores | 0 |
| Omitidos | 0 |
| Módulos instalados | 4/4 |
| Exit code | 0 |
| Cobertura conjunta | 92 % |
| Traceback | 0 |
| DeprecationWarning | 0 |

El log sí contiene advertencias; se revisaron y clasificaron:

- advertencia de `pip` ejecutándose como root dentro del contenedor;
- advertencias de `docutils` al interpretar documentación de los módulos;
- falsos positivos por nombres de archivo y por la línea `0 error(s)` del
  resumen.

No se detectaron advertencias funcionales ni de obsolescencia que afectaran
la instalación o los tests.

## 11. Decisiones principales de seguridad

- **T-200**: resuelto con ACL mínima y record rule multi-compañía, sin `sudo()`.
- **payment_request**: protegido a nivel ORM/RPC, no solamente en vistas.
- **payment_request**: los cambios de estado solo se realizan mediante las
  acciones del flujo (`action_submit`, `action_approve`, `action_reject`,
  `action_pay`).
- **shop_integration_api**: la API utiliza `auth="user"` y no usa `sudo()`.
- Las pruebas de permisos se ejecutan con usuarios no administradores.
- Las transiciones internas de `payment_request` usan un método privado no
  invocable por RPC y no se usan banderas de contexto controlables por el
  cliente.

## 12. Documentación por módulo

| Módulo | Documentación |
|---|---|
| `shop_integration_api` | `README.md`, `AI_LOG.md` |
| `fleet_inspection` | `README.md`, `AI_LOG.md` |
| `sale_commission` | `README.md`, `AI_LOG.md`, `INCIDENT.md` |
| `payment_request` | `README.md`, `AI_LOG.md` |

## 13. Uso de IA

La IA se utilizó como apoyo para implementación, revisión y documentación.
Las decisiones y resultados se contrastaron contra Odoo 18 y se validaron con
las suites de pruebas. Los detalles, errores detectados y correcciones están
registrados en el `AI_LOG.md` de cada módulo.

## 14. Limitaciones

- Solamente se implementó el tramo A de los cuatro ejercicios.
- No se implementaron API keys, pedidos, webhooks ni idempotencia.
- No se implementó una migración productiva de datos.
- No se corrigió el hallazgo fuera de alcance sobre `fleet.inspection.line`.
- No se corrigió `action_recompute_commissions`.
- No se implementaron pagos contables, conversiones monetarias ni concurrencia
  avanzada.

## 15. Tramos no implementados

Los tramos B y C de los cuatro ejercicios no forman parte de esta entrega.
Las limitaciones concretas del tramo A se detallan en la sección anterior y en
el `README.md` de cada módulo.

## 16. Instrucciones de entrega y rama relevante

La entrega se encuentra en la rama `prueba-tecnica/gabriel-izaya`, con los
cuatro módulos en `src/custom/prueba-tecnica/`. La instancia `prueba-tecnica`
carga ese directorio como addons; no se requieren rutas adicionales para
ejecutar los comandos de prueba de este documento.
