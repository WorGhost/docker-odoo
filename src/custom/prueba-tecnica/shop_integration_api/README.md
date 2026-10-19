# shop_integration_api

Módulo del **Ejercicio 1 — Integración con tienda** (prueba técnica Binaural, Odoo 18.0).
Expone el catálogo de productos en JSON para que una tienda externa lo consulte.

## Estado

| Tramo | Contenido | Estado |
|---|---|---|
| A | `GET /api/v1/products` (lectura de catálogo con filtros) | ✅ Hecho y probado |
| B | API keys + bitácora de llamadas | Pendiente |
| C | Creación de pedidos, paginación medible, webhook, idempotencia | Pendiente |

## Tramo A — contrato

### Endpoint

`GET /api/v1/products` — `type="http"`, `auth="user"` (sesión de backend), solo `GET`.

### Filtros (query string; se combinan con AND)

| Parámetro | Formato | Ejemplo | Semántica |
|---|---|---|---|
| `category_id` | entero | `?category_id=4` | Solo productos de esa categoría (`product.category`). |
| `in_stock` | booleano | `?in_stock=true` | Acepta `true/false`, `1/0`, `yes/no`. Solo productos con stock disponible. |
| `modified_since` | ISO 8601 | `?modified_since=2026-01-31` o `2026-01-31T12:30:00Z` | Productos cuyo `write_date` es igual o posterior. Fecha sin zona horaria se interpreta en UTC. |

### Respuesta de éxito (HTTP 200)

```json
{
  "products": [
    {
      "id": 42,
      "default_code": "TIENDA-A",
      "name": "Producto A",
      "price": 10.0,
      "available_quantity": 7.0
    }
  ]
}
```

- Solo esos 5 claves por producto; el cuerpo solo contiene `products`.
- `price` = `list_price` del producto (precio de venta, sin impuestos ni tarifa).
- `available_quantity` = `free_qty` (a mano − reservado).
- Sin coincidencias → `{"products": []}` (HTTP 200).
- Se listan únicamente productos **activos** y **vendibles** (`active`, `sale_ok`).

### Errores (HTTP 400, formato uniforme)

```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "field": "modified_since",
    "message": "La fecha '31/12/2026' no es ISO 8601 válido. Ejemplos: 2025-01-31, 2025-01-31T12:30:00Z."
  }
}
```

- `category_id` no numérico o inexistente → 400.
- `in_stock` no booleano → 400.
- `modified_since` no ISO 8601 → 400.
- Parámetros desconocidos: se ignoran.
- Sin sesión: redirección estándar de Odoo al login (303). El reemplazo por API keys corresponde al tramo B.

## Supuestos

1. **`available_quantity` = `free_qty`** (disponible para vender ahora: a mano − reservado) y no `qty_available` (a mano sin descontar reservas). Es lo que una tienda necesita para no vender de más.
2. **`category_id` se interpreta como `product.category`** del núcleo (la de la ficha de producto). `product.public_category` solo existe con `website_sale`, que es una dependencia injustificable para este módulo.
3. El **sobre de error** `{code, field, message}` se adopta desde el tramo A (el mismo formato que usará el tramo B) para no romper el contrato en el futuro.
4. `price` = `list_price`; no aplica tarifa de precios ni impuestos en este tramo.
5. `modified_since` compara contra el `write_date` de la variante (`product_product`).
6. `in_stock=false` equivale a omitir el filtro (el filtro solo existe en dirección "solo con stock").
7. El cuerpo lleva envoltorio `{"products": [...]}` desde el tramo A; así la paginación del tramo C será un cambio aditivo y no romperá integraciones existentes.

## Rendimiento

- El filtro de stock forma parte del dominio ORM mediante el método de búsqueda de `free_qty` (`search='_search_free_qty'` en `stock`), evitando filtrar producto por producto en Python.
- La respuesta se arma con un solo `search_read` por lote (los 5 campos en una pasada); el cálculo de `free_qty` lo hace el ORM para el lote completo. Sin N+1 por diseño; la medición de consultas de tramo C lo verificará.

## Limitaciones

- Autenticación por sesión de backend; API keys: tramo B.
- Sin bitácora de llamadas: tramo B.
- Sin pedidos, paginación, webhook ni idempotencia: tramo C.
- Sin marcar importe con impuestos ni tarifa de precios: fuera de este tramo.

## Pruebas

15 pruebas HTTP (`tests/test_products_api.py`, `HttpCase`): sin filtros, cada filtro solo, combinados y todos a la vez, categoría inválida, booleano inválido, fecha inválida, exclusiones (inactivo, no vendible, sin stock), usuario no autenticado, resultado vacío y exactitud de claves de respuesta.

```bash
./odoo test prueba-tecnica shop_integration_api
```

Última corrida (base nueva): **15 tests, 0 fallos, 0 errores, 94% de cobertura** (ramas sin ejercitar: `in_stock=false` y fecha con offset de zona horaria explícito).

## Prueba manual

Con sesión de backend iniciada (admin/admin en `http://localhost:8069`) o cookie de sesión:

```
GET http://localhost:8069/api/v1/products
GET http://localhost:8069/api/v1/products?category_id=4&in_stock=true
```
