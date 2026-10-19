from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged("post_install", "-at_install")
class TestCommissionRuleSecurity(TransactionCase):
    """T-200: permisos efectivos del vendedor sobre sale.commission.rule.

    Contrato tras el hotfix (ACL 1,0,0,0 + record rule multi-compañía):
    el vendedor puede LEER las reglas globales (company_id=False) o de sus
    compañías permitidas, y NO puede crear, modificar ni borrar reglas.
    Un gerente conserva el CRUD completo. Sin sudo().
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Compañía B (T-200)"})
        cls.salesman = new_test_user(
            cls.env,
            login="t200_rule_salesman",
            groups="sales_team.group_sale_salesman",
            name="Vendedor reglas T-200",
            company_id=cls.company_a.id,
            company_ids=[(6, 0, [cls.company_a.id])],
        )
        cls.manager = new_test_user(
            cls.env,
            login="t200_rule_manager",
            groups="sales_team.group_sale_manager",
            name="Gerente reglas T-200",
            company_id=cls.company_a.id,
            company_ids=[(6, 0, [cls.company_a.id, cls.company_b.id])],
        )
        cls.category = cls.env["product.category"].create({"name": "Categoría seguridad T-200"})
        cls.rule_global = cls.env["sale.commission.rule"].create({
            "categ_id": cls.category.id,
            "percent": 7.0,
        })
        cls.rule_a = cls.env["sale.commission.rule"].create({
            "categ_id": cls.category.id,
            "percent": 8.0,
            "company_id": cls.company_a.id,
        })
        cls.rule_b = cls.env["sale.commission.rule"].create({
            "categ_id": cls.category.id,
            "percent": 9.0,
            "company_id": cls.company_b.id,
        })

    def _rules_as(self, user):
        return self.env["sale.commission.rule"].with_user(user)

    def test_salesman_can_read_applicable_rule(self):
        """El vendedor puede leer una regla aplicable (la de su compañía)."""
        rule = self._rules_as(self.salesman).search([("id", "=", self.rule_a.id)])
        self.assertEqual(rule, self.rule_a)
        self.assertEqual(rule.percent, 8.0)

    def test_salesman_can_read_global_rule(self):
        """El vendedor puede ver una regla global (company_id=False)."""
        rule = self._rules_as(self.salesman).search([("id", "=", self.rule_global.id)])
        self.assertEqual(rule, self.rule_global)

    def test_salesman_sees_only_his_companies_rules(self):
        """Aislamiento multi-compañía: ve exactamente global + su compañía."""
        visible = self._rules_as(self.salesman).search([])
        self.assertEqual(set(visible.ids), {self.rule_global.id, self.rule_a.id})

    def test_salesman_cannot_access_other_company_rule(self):
        """La regla de la compañía B no es accesible para el vendedor de la A."""
        rules = self._rules_as(self.salesman)
        self.assertFalse(rules.search([("id", "=", self.rule_b.id)]))
        self.assertNotIn(self.rule_b.id, rules.search([]).ids)
        with self.assertRaises(AccessError) as ctx:
            self.rule_b.with_user(self.salesman).read(["percent"])
        self.assertIn("sale.commission.rule", str(ctx.exception))

    def test_salesman_cannot_create_rule(self):
        """El vendedor no puede crear reglas (ACL create=0)."""
        with self.assertRaises(AccessError) as ctx:
            self._rules_as(self.salesman).create({
                "categ_id": self.category.id,
                "percent": 1.0,
            })
        self.assertIn("sale.commission.rule", str(ctx.exception))

    def test_salesman_cannot_write_rule(self):
        """El vendedor no puede modificar reglas (ACL write=0)."""
        with self.assertRaises(AccessError) as ctx:
            self.rule_a.with_user(self.salesman).write({"percent": 99.0})
        self.assertIn("sale.commission.rule", str(ctx.exception))

    def test_salesman_cannot_unlink_rule(self):
        """El vendedor no puede eliminar reglas (ACL unlink=0)."""
        with self.assertRaises(AccessError) as ctx:
            self.rule_a.with_user(self.salesman).unlink()
        self.assertIn("sale.commission.rule", str(ctx.exception))

    def test_manager_can_manage_rules(self):
        """El gerente conserva el CRUD completo tras el hotfix."""
        rules = self._rules_as(self.manager)
        rule = rules.create({"categ_id": self.category.id, "percent": 4.0})
        rule.write({"percent": 6.0})
        self.assertEqual(rule.percent, 6.0)
        rule.unlink()
        self.assertFalse(rule.exists())
