# AI_LOG — shop_integration_api (Ejercicio 1, tramo A)

Registro del trabajo asistido por IA para el tramo A en este módulo. Se declara todo: qué hizo la IA, qué se verificó contra el código real y qué quedó a medias.

## Herramientas

- **OpenCode** — agente de trabajo (planificación, edición, corrida de pruebas).
- **GLM-5.3-Flash** — implementación del módulo (contrato, controlador, pruebas, documentación).
- **Skill `odoo-development-skill`** — guía de patrones (objetivo 18.0), verificada contra el Odoo 18 real del contenedor.

La implementación fue revisada mediante pruebas automatizadas, inspección del diff y contraste con el código real de Odoo 18.

## Qué hizo la IA

1. Definición del contrato con 8 decisiones previas a codificar (modelo Odoo, contrato HTTP, formato de éxito, formato de error, interpretación de `available_quantity`, validaciones, dominio ORM, estrategia anti N+1).
2. Implementación del controlador `controllers/products.py` y del `__manifest__.py`.
3. Las 15 pruebas HTTP pedidas (`tests/test_products_api.py`).
4. Verificación de hechos contra el Odoo 18 real del contenedor **antes y durante** el desarrollo (ver siguiente sección).
5. Corrida de la suite y cálculo de cobertura sobre base nueva.

## Verificación de la guía contra el Odoo 18 real

La skill y su propia doc fueron contrastadas con el código real en `/usr/lib/python3/dist-packages/odoo`:

| Afirmación de la guía / memoria | Realidad en Odoo 18 (verificada) | Impacto |
|---|---|---|
| Patrón REST con `json.dumps` + `make_response` + headers manuales | Existe `request.make_json_response(data, status=...)` (`odoo/http.py`) | Se usó la API nativa del 18 |
| Odoo ≤ 16: `type='product'` marca storable | `product.template.type` = `('consu','Goods'),('service'),('combo')`; el inventario se marca con `is_storable=True` (`stock/models/product.py`) | Datos de prueba creados con `is_storable` |
| "Categoría" = `public_categ_ids` / `product.public_category` | Solo existen con `website_sale`; en core está `product.category` | `category_id` valida contra `product.category` |
| Categorías / tests HTTP del 17-18: sin patrón para "no autenticado" | `HttpCase.opener` (requests-like) con cookie jar por test y `allow_redirects=False` (`tests/common.py:2143-2361`) | Test 13 escrito sobre ese mecanismo |
| — | `free_qty` es buscable (`search='_search_free_qty'`, `stock/models/product.py`) | El filtro de stock vive en el dominio ORM (anti N+1) |
| — | `is_storable` es de `product.template`, `default_code` de `product.product`, `product.category` en `product/models/product_category.py` | Modelización correcta de variantes |

## Lo que la IA hizo mal o casi mal (y cómo se detectó)

1. **Primera versión del mensaje de error de `modified_since`:** concatenaba ejemplos con `datetime` como valor `%s` (salida ilegible y confusa). Corregido a ejemplos literales mientras revisaba el archivo antes de correr las pruebas (no llegó a ejecutarse mal).
2. **Rostro mentalmente al ciclo de vida de datos HTTP:** dudé entre `cr.commit()` en `setUpClass` o confiar en el test-cursor. Se verificó `tests/common.py` (opener con cookie `test_cursor` compartiendo la transacción) y la primera corrida verde lo confirmó: **no** se commitea en el setup.
3. **Estructura sugerida `controllers/main.py`:** se usó `controllers/products.py` por semántica; la convención de directorio sí se respeta (`controllers/__init__.py`).
4. **Desvío de la guía:** la skill sugiere `README.rst`; el ejercicio exige `README.md` (manda el enunciado).
5. **Supuestos planteados y no confirmados formalmente por el usuario al momento de codificar** (se documentaron en `README.md`): `free_qty` vs `qty_available`, sobre de error `{code, field, message}` desde A, `auth="user"` literal.
6. **Búsqueda OCA previa ("no reinventar")**: no se buscó módulo OCA equivalente; el ejercicio pide construir el endpoint exacto con contrato propio, y las alternativas existentes (p. ej. `shopinvader`) son plataformas completas, no catalog readers. Decisión consciente, no oversight.

## Validación manual (evidencia real)

- `py_compile` de los 6 `.py`: exit 0.
- `./odoo test prueba-tecnica shop_integration_api` (base nueva `test_shop_integration_api_20261019_084247_2c4a8b`):
  - **15 tests, 0 fallos, 0 errores, 0 omitidos**.
  - Cobertura **94%** (líneas no cubiertas: `100` branch de `in_stock=false`, `119` fecha con offset explícito).
  - Sin advertencias de obsolescencia en el log de la corrida.
  - Logs de werkzeug de la corrida: `200` para filtros válidos, `400` para los 4 casos inválidos, `303` para el no autenticado.
  - La BD de prueba se elimina al terminar la corrida.
- `grep -rn "sudo()"` en el módulo: **0 coincidencias** (no hay `sudo`; el acceso es con la sesión del usuario vía `auth="user"`).
- Sin modelos nuevos → no aplica `security/ir.model.access.csv` (regla del enunciado para modelos nuevos).
- Sin modificaciones a otros módulos de la prueba.

## Archivos tocados

```
shop_integration_api/
├── __manifest__.py
├── __init__.py
├── controllers/
│   ├── __init__.py
│   └── products.py
├── tests/
│   ├── __init__.py
│   └── test_products_api.py
├── README.md
└── AI_LOG.md
```

## Fuera del alcance (ejercicio)

API keys y bitácora (tramo B), pedidos/paginación/webhook/idempotencia (tramo C), OpenAPI, datos reales de clientes.
