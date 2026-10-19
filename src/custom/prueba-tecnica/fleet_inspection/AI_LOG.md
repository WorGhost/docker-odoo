# AI_LOG — `fleet_inspection` (migración a Odoo 18)

Registro de asistencia de IA del **tramo A** (migración 16 → 18) del Ejercicio 2.

## Herramientas

- OpenCode.
- GLM-5.3-Flash.
- Gemini 4 Argon Contributor.
- Odoo Development Skill / odoo-code-reviewer.
- M365 Copilot.

## Uso de IA

- Inventario inicial de incompatibilidades Odoo 16 a Odoo 18.
- Propuesta de estrategia de copia y migración.
- Conversión de Python y XML.
- Adaptación inicial de pruebas.
- Revisión de compatibilidad y documentación.

## Validación manual

- Se conservó intacto el módulo original Odoo 16.
- Se revisó el diff.
- Se ejecutó py_compile sobre 8 archivos.
- Se validaron 8 archivos XML.
- Se instaló el módulo sobre una base limpia.
- Se ejecutaron 9 tests, con 0 fallos y 0 errores.
- Se obtuvo 94 % de cobertura.
- Se revisó el log final y no hubo advertencias de obsolescencia.
- El commit fue realizado manualmente.

## Ajustes o errores reales de la asistencia

- El import heredado de Form desde odoo.tests.common produjo una
  DeprecationWarning.
- Se corrigió para importar Form desde odoo.tests.
- Se comprobó que states en campos podía ser aceptado sin error
  visible, aunque no preservaba el comportamiento esperado, por lo
  que se eliminó y se trasladó el control a la vista.
- Recomendaciones generales como _check_company_auto, type hints y
  cambios de seguridad adicionales no se aplicaron por estar fuera
  del tramo A.
- La afirmación de que company_ids estaba obsoleto en record rules no
  se aceptó sin evidencia; su funcionamiento fue validado previamente
  en Odoo 18.

## Cambios realizados

- manifest a 18.0.1.0.0;
- @api.model_create_multi;
- _compute_display_name;
- eliminación de states en campos;
- tree a list;
- view_mode a list,form;
- attrs y states a expresiones directas;
- column_invisible;
- eliminación de numbercall y doall;
- actualización del import Form.

## Fuera del alcance

- Tramo B.
- Migración real de datos productivos.
- Pruebas con 10.000 registros.
- Optimización por lotes.
- Regla de registros de fleet.inspection.line.
- Cambios funcionales adicionales.
