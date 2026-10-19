from datetime import datetime, timedelta, timezone

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestProductsAPI(HttpCase):
    """HTTP tests for GET /api/v1/products (Exercise 1, tramo A)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shop_category = cls.env["product.category"].create({
            "name": "Accesorios de tienda",
        })
        cls.other_category = cls.env["product.category"].create({
            "name": "Librería interna",
        })

        cls.product_a = cls.env["product.product"].create({
            "name": "Producto A",
            "default_code": "TIENDA-A",
            "list_price": 10.0,
            "is_storable": True,
            "categ_id": cls.shop_category.id,
        })
        cls.product_b = cls.env["product.product"].create({
            "name": "Producto B",
            "default_code": "TIENDA-B",
            "list_price": 20.0,
            "is_storable": True,
            "categ_id": cls.shop_category.id,
        })
        cls.product_c = cls.env["product.product"].create({
            "name": "Producto C",
            "default_code": "OTRA-C",
            "list_price": 30.0,
            "is_storable": True,
            "categ_id": cls.other_category.id,
        })
        cls.product_service = cls.env["product.product"].create({
            "name": "Servicio de instalación",
            "default_code": "SERVICIO-S",
            "list_price": 99.0,
            "type": "service",
        })
        cls.product_not_saleable = cls.env["product.product"].create({
            "name": "Producto interno",
            "default_code": "NO-VENDIBLE",
            "list_price": 40.0,
            "is_storable": True,
            "sale_ok": False,
            "categ_id": cls.shop_category.id,
        })
        cls.product_archived = cls.env["product.product"].create({
            "name": "Producto retirado",
            "default_code": "ARCHIVADO",
            "list_price": 50.0,
            "is_storable": True,
            "categ_id": cls.shop_category.id,
        })
        cls.product_archived.write({"active": False})

        cls._apply_inventory(cls.product_a, 7.0)
        cls._apply_inventory(cls.product_c, 3.0)
        cls._apply_inventory(cls.product_not_saleable, 5.0)
        cls._apply_inventory(cls.product_archived, 5.0)

        # ``product_b`` was last modified one month ago; the rest were
        # modified during this setup.
        cls.env.flush_all()
        backdated = (datetime.now(timezone.utc) - timedelta(days=30)).strftime(
            "%Y-%m-%d %H:%M:%S",
        )
        cls.env.cr.execute(
            "UPDATE product_product SET write_date = %s WHERE id = %s",
            [backdated, cls.product_b.id],
        )
        cls.env["product.product"].invalidate_model()

    @classmethod
    def _apply_inventory(cls, product, quantity):
        quant = cls.env["stock.quant"].with_context(inventory_mode=True).create({
            "product_id": product.id,
            "location_id": cls.env.ref("stock.stock_location_stock").id,
            "inventory_quantity": quantity,
        })
        quant.action_apply_inventory()

    def _get(self, query_string=""):
        """GET the endpoint with an authenticated session."""
        self.authenticate("admin", "admin")
        return self.url_open("/api/v1/products" + query_string)

    def _codes(self, response):
        self.assertEqual(response.status_code, 200)
        return sorted(
            product["default_code"] for product in response.json()["products"]
        )

    def _error_of(self, response):
        self.assertEqual(response.status_code, 400)
        error = response.json()["error"]
        self.assertEqual(set(error.keys()), {"code", "field", "message"})
        return error

    # -- 1. No filters -----------------------------------------------------

    def test_01_products_without_filters(self):
        response = self._get("")
        self.assertEqual(
            self._codes(response),
            ["OTRA-C", "SERVICIO-S", "TIENDA-A", "TIENDA-B"],
        )
        by_code = {
            product["default_code"]: product
            for product in response.json()["products"]
        }
        self.assertEqual(by_code["TIENDA-A"]["id"], self.product_a.id)
        self.assertEqual(by_code["TIENDA-A"]["name"], "Producto A")
        self.assertEqual(by_code["TIENDA-A"]["price"], 10.0)
        self.assertEqual(by_code["TIENDA-A"]["available_quantity"], 7.0)
        self.assertEqual(by_code["OTRA-C"]["available_quantity"], 3.0)
        self.assertEqual(by_code["TIENDA-B"]["available_quantity"], 0.0)
        self.assertEqual(by_code["SERVICIO-S"]["available_quantity"], 0.0)

    # -- 2. Category filter ------------------------------------------------

    def test_02_filter_by_category(self):
        response = self._get(f"?category_id={self.shop_category.id}")
        self.assertEqual(self._codes(response), ["TIENDA-A", "TIENDA-B"])

    # -- 3. In stock only --------------------------------------------------

    def test_03_filter_in_stock(self):
        response = self._get("?in_stock=true")
        self.assertEqual(self._codes(response), ["OTRA-C", "TIENDA-A"])

    # -- 4. Modified since a date ------------------------------------------

    def test_04_filter_modified_since(self):
        since = (datetime.now(timezone.utc) - timedelta(days=10)).strftime(
            "%Y-%m-%dT%H:%M:%S",
        )
        response = self._get(f"?modified_since={since}")
        # ``product_b`` was backdated 30 days, so it is excluded.
        self.assertEqual(
            self._codes(response),
            ["OTRA-C", "SERVICIO-S", "TIENDA-A"],
        )

    # -- 5. Category + stock combined --------------------------------------

    def test_05_filters_category_and_in_stock(self):
        query = f"?category_id={self.shop_category.id}&in_stock=true"
        response = self._get(query)
        self.assertEqual(self._codes(response), ["TIENDA-A"])

    # -- 6. All filters at once --------------------------------------------

    def test_06_all_filters_combined(self):
        since = (datetime.now(timezone.utc) - timedelta(days=10)).strftime(
            "%Y-%m-%dT%H:%M:%S",
        )
        query = f"?category_id={self.shop_category.id}&in_stock=true&modified_since={since}"
        response = self._get(query)
        self.assertEqual(self._codes(response), ["TIENDA-A"])

    # -- 7. Invalid category ------------------------------------------------

    def test_07_invalid_category_id(self):
        response = self._get("?category_id=999999999")
        error = self._error_of(response)
        self.assertEqual(error["code"], "INVALID_PARAMETER")
        self.assertEqual(error["field"], "category_id")
        self.assertTrue(error["message"])

        response = self._get("?category_id=tienda")
        self.assertEqual(self._error_of(response)["field"], "category_id")

    # -- 8. Invalid boolean --------------------------------------------------

    def test_08_invalid_in_stock(self):
        response = self._get("?in_stock=perhaps")
        error = self._error_of(response)
        self.assertEqual(error["code"], "INVALID_PARAMETER")
        self.assertEqual(error["field"], "in_stock")
        self.assertTrue(error["message"])

    # -- 9. Invalid date ------------------------------------------------------

    def test_09_invalid_modified_since(self):
        response = self._get("?modified_since=31/12/2026")
        error = self._error_of(response)
        self.assertEqual(error["code"], "INVALID_PARAMETER")
        self.assertEqual(error["field"], "modified_since")
        self.assertTrue(error["message"])

    # -- 10. Inactive product excluded ----------------------------------------

    def test_10_inactive_product_excluded(self):
        response = self._get("")
        self.assertNotIn("ARCHIVADO", self._codes(response))

    # -- 11. Not saleable product excluded -------------------------------------

    def test_11_not_saleable_product_excluded(self):
        response = self._get("")
        self.assertNotIn("NO-VENDIBLE", self._codes(response))

    # -- 12. Out of stock product excluded when in_stock=true ------------------
    def test_12_out_of_stock_excluded_when_in_stock(self):
        # Without the filter, the out-of-stock product is listed...
        self.assertIn("TIENDA-B", self._codes(self._get("")))
        # ...but with ``in_stock=true`` it is not.
        self.assertNotIn("TIENDA-B", self._codes(self._get("?in_stock=true")))

    # -- 13. Unauthenticated user ----------------------------------------------

    def test_13_unauthenticated_request(self):
        # No ``authenticate()`` call: the opener has no session cookie.
        response = self.url_open("/api/v1/products", allow_redirects=False)
        self.assertIn(response.status_code, (301, 302, 303, 307, 308))

    # -- 14. Empty result -------------------------------------------------------

    def test_14_empty_result(self):
        # Every product was modified in the past: nothing matches a future date.
        since = (datetime.now(timezone.utc) + timedelta(days=2)).strftime(
            "%Y-%m-%dT%H:%M:%S",
        )
        response = self._get(f"?modified_since={since}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"products": []})

    # -- 15. Response with only the expected fields ------------------------------

    def test_15_response_has_exact_fields(self):
        response = self._get(f"?category_id={self.shop_category.id}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(list(payload.keys()), ["products"])
        expected = {"id", "default_code", "name", "price", "available_quantity"}
        for product in payload["products"]:
            self.assertEqual(set(product.keys()), expected)
