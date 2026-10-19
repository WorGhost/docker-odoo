# Inspecciones de vehículos (`fleet_inspection`)

Checklist de inspección para la flota del vehículo. Migrado a **Odoo 18.0** (18.0.1.0.0) para el
**Ejercicio 2 — Migración** de la prueba técnica; el original para Odoo 16 permanece intacto en
`src/custom/prueba-tecnica-odoo16/fleet_inspection` (16.0.1.0.0).

## Qué hace

- Registra inspecciones de los vehículos de Flota con un checklist de puntos (frenos, luces, cauchos…) que se carga solo al crear la inspección.
- Estados: borrador → en curso → aprobada / rechazada. Un punto crítico con falla impide aprobar.
- Tipo de vehículo como campo de selección: moto, carro, camión u otro.
- Grupos: *Inspector* (ve solo sus inspecciones) y *Supervisor de inspecciones* (ve todas, aprueba y rechaza).
- Acción planificada diaria que marca las inspecciones con más de 7 días en curso y le crea una actividad al inspector.
- Reporte PDF de la inspección.

## Cómo probarlo (Odoo 18)

```bash
./odoo test prueba-tecnica fleet_inspection
```

Corrida del 2026-10-18 sobre base limpia: 9/9 tests, 0 fallos, 0 errores, cobertura 94 %;
instalación sin advertencias de obsolescencia.

## Cambios de migración (16 → 18)

| Área | Antes (16) | Después (18) |
|---|---|---|
| Manifest | `version: 16.0.1.0.0` | `18.0.1.0.0` (dependencias y data sin cambios) |
| Campos | `readonly=True, states={"draft": [("readonly", False)]}` en `vehicle_id`/`vehicle_type` | `states` eliminado (obsoleto en 18); `readonly="state != 'draft'"` en la vista de formulario |
| `create` | `@api.model def create(self, vals)` | `@api.model_create_multi def create(self, vals_list)`; misma lógica de secuencia y checklist |
| Display name | `name_get()` | `_compute_display_name` + `@api.depends("name", "vehicle_id.name", "vehicle_id.license_plate")`; etiqueta idéntica (`name - placa/nombre vehículo`) |
| Vistas | `<tree>`, `attrs=`, `states=` en botones, `invisible="1"` en columnas | `<list>`, expresiones directas (`invisible=`, `readonly=`, `required=`), `column_invisible="1"` |
| Acciones | `view_mode` `tree,form` / `tree` | `list,form` / `list` |
| Cron | `numbercall`, `doall` | eliminados (no existen en 18); intervalo, método y comportamiento intactos |
| Tests | `from odoo.tests.common import …`; `name_get()` en el caso de placa | `from odoo.tests import …`; el caso usa `display_name` (misma expectativa)

Sin cambios de lógica funcional; nombres técnicos, data, security, reporte y menús intactos.

## Limitaciones conocidas (tramo B pendiente)

- `fleet.inspection.line` no tiene regla de registro propia (se accede a las líneas a través de la inspección); se aborda en el tramo B del ejercicio.
