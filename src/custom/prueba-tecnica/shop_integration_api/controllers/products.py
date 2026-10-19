from datetime import datetime, timezone

from odoo import _, http
from odoo.http import request
from odoo.tools import str2bool

PRODUCT_FIELDS = ("id", "default_code", "name", "list_price", "free_qty")


class APIParameterError(Exception):
    """Invalid value in an incoming HTTP parameter (mapped to HTTP 400)."""

    def __init__(self, field, message):
        super().__init__(message)
        self.field = field
        self.message = message


class ShopIntegrationAPI(http.Controller):

    @http.route("/api/v1/products", type="http", auth="user", methods=["GET"], csrf=False)
    def list_products(self, **params):
        """GET /api/v1/products (Exercise 1, tramo A).

        Returns the sellable products that match all the given filters,
        as ``{"products": [{"id", "default_code", "name", "price",
        "available_quantity"}]}``. Invalid parameters reply 400 with a
        ``{"error": {...}}`` envelope.
        """
        domain = [("active", "=", True), ("sale_ok", "=", True)]
        try:
            domain += self._filter_category(params.get("category_id"))
            domain += self._filter_in_stock(params.get("in_stock"))
            domain += self._filter_modified_since(params.get("modified_since"))
        except APIParameterError as error:
            return self._error_response(error.field, error.message)

        # One batched read for the whole result: the ORM computes
        # ``free_qty`` for the full recordset at once (no N+1).
        products = request.env["product.product"].search_read(
            domain, list(PRODUCT_FIELDS), order="id",
        )
        payload = {
            "products": [
                {
                    "id": item["id"],
                    "default_code": item["default_code"],
                    "name": item["name"],
                    "price": item["list_price"],
                    "available_quantity": item["free_qty"],
                }
                for item in products
            ],
        }
        return request.make_json_response(payload, status=200)

    def _error_response(self, field, message):
        return request.make_json_response(
            {
                "error": {
                    "code": "INVALID_PARAMETER",
                    "field": field,
                    "message": message,
                },
            },
            status=400,
        )

    def _filter_category(self, value):
        """Validate ``category_id`` and return its ORM domain leaves."""
        if value in (None, ""):
            return []
        try:
            category_id = int(str(value).strip())
        except ValueError:
            raise APIParameterError(
                "category_id",
                _("La categoría '%s' no es un identificador numérico.") % value,
            )
        category = request.env["product.category"].browse(category_id).exists()
        if not category:
            raise APIParameterError(
                "category_id",
                _("No existe una categoría de producto con id %s.") % category_id,
            )
        return [("categ_id", "=", category.id)]

    def _filter_in_stock(self, value):
        """Validate ``in_stock`` and return its ORM domain leaves."""
        if value in (None, ""):
            return []
        try:
            only_in_stock = str2bool(str(value))
        except ValueError:
            raise APIParameterError(
                "in_stock",
                _("'%s' no es un booleano válido (true/false, 1/0, yes/no).") % value,
            )
        if not only_in_stock:
            return []
        # ``free_qty`` is searchable (search='_search_free_qty'): the ORM
        # turns this leaf into SQL, so the stock filter never iterates
        # product by product.
        return [("free_qty", ">", 0)]

    def _filter_modified_since(self, value):
        """Validate ``modified_since`` (ISO 8601) and return its domain leaves."""
        if value in (None, ""):
            return []
        text = str(value).strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            raise APIParameterError(
                "modified_since",
                _("La fecha '%s' no es ISO 8601 válido. Ejemplos: 2025-01-31, 2025-01-31T12:30:00Z.") % value,
            )
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        # ``write_date`` is a naive UTC datetime in Odoo.
        return [("write_date", ">=", parsed.strftime("%Y-%m-%d %H:%M:%S"))]
