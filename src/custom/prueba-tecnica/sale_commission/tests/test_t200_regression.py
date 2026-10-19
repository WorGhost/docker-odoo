from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged("post_install", "-at_install")
class TestT200Regression(TransactionCase):
    """T-200: el vendedor no puede confirmar pedidos de venta.

    Prueba de regresión (debe fallar en rojo ANTES del hotfix y pasar
    después): confirmar con un vendedor sin grupo de gerente lanza
    AccessError al consultar `sale.commission.rule` desde
    `sale.order.line._get_commission_percent` con los permisos del usuario
    que confirma, mientras que un gerente de ventas sí puede confirmar.
    La acción evaluada no usa sudo(): se prueba el permiso real del usuario.
    Los dos tests son independientes entre sí: cada uno crea su propio pedido
    y no dependen del orden de ejecución.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.salesman = new_test_user(
            cls.env,
            login="t200_salesman",
            groups="sales_team.group_sale_salesman",
            name="Vendedor T-200",
        )
        cls.manager = new_test_user(
            cls.env,
            login="t200_manager",
            groups="sales_team.group_sale_manager",
            name="Gerente T-200",
        )
        cls.partner = cls.env["res.partner"].create({"name": "Cliente T-200"})
        cls.category = cls.env["product.category"].create({"name": "Repuestos T-200"})
        cls.product = cls.env["product.product"].create({
            "name": "Producto T-200",
            "categ_id": cls.category.id,
            "list_price": 100.0,
            "taxes_id": [(5, 0, 0)],
        })

    def _create_order(self, user):
        return self.env["sale.order"].with_user(user).create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1})],
        })

    def test_salesman_can_confirm_order(self):
        """El vendedor confirma su propio pedido (flujo real del T-200).

        Hoy debe reproducir el AccessError de `sale.commission.rule`; cuando
        se corrija la causa, este mismo test debe pasar sin cambios.
        """
        order = self._create_order(self.salesman)
        order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.state, "sale")

    def test_manager_can_confirm_order(self):
        """Control por separado: un gerente de ventas sí puede confirmar."""
        order = self._create_order(self.manager)
        order.with_user(self.manager).action_confirm()
        self.assertEqual(order.state, "sale")
