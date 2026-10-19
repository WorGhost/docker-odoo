from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPaymentRequest(TransactionCase):
    """Pruebas críticas del tramo A de payment_request."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "Proveedor de prueba"})
        cls.group_user = cls.env.ref("base.group_user")

        def make_user(name, login, extra_group_xmlid, company=None):
            company = company or cls.company_a
            groups = [cls.group_user.id]
            if extra_group_xmlid:
                groups.append(cls.env.ref(extra_group_xmlid).id)
            return cls.env["res.users"].create({
                "name": name,
                "login": login,
                "company_id": company.id,
                "company_ids": [Command.set([company.id])],
                "groups_id": [Command.set(groups)],
            })

        cls.user_requester = make_user(
            "Solicitante Uno", "requester_one", "payment_request.group_payment_requester",
        )
        cls.user_requester_2 = make_user(
            "Solicitante Dos", "requester_two", "payment_request.group_payment_requester",
        )
        cls.user_approver = make_user(
            "Aprobador", "approver", "payment_request.group_payment_approver",
        )
        cls.user_treasury = make_user(
            "Tesorería", "treasury", "payment_request.group_payment_treasury",
        )

    def _create_request(self, user=None, **vals):
        user = user or self.user_requester
        base = {
            "partner_id": self.partner.id,
            "amount": 100.0,
            "concept": "Compra de materiales",
        }
        base.update(vals)
        return self.env["payment.request"].with_user(user).create(base)

    # -- 1. Secuencia y valores predeterminados -------------------------------

    def test_01_sequence_and_defaults(self):
        request = self._create_request()
        year = fields.Date.today().year
        self.assertRegex(request.name, rf"^SP/{year}/\d{{4}}$")
        self.assertEqual(request.state, "draft")
        self.assertEqual(request.requester_id, self.user_requester)
        self.assertEqual(request.request_date, fields.Date.today())
        self.assertEqual(request.currency_id, self.company_a.currency_id)
        self.assertEqual(request.company_id, self.company_a)
        second = self._create_request()
        self.assertNotEqual(second.name, request.name)

    # -- 2. Monto cero y negativo ----------------------------------------------

    def test_02_amount_zero_and_negative(self):
        with self.assertRaises(ValidationError):
            self._create_request(amount=0.0)
        with self.assertRaises(ValidationError):
            self._create_request(amount=-5.0)

    # -- 3. Solicitante envía ----------------------------------------------------

    def test_03_requester_submits(self):
        request = self._create_request()
        request.action_submit()
        self.assertEqual(request.state, "submitted")
        self.assertFalse(request.approved_by_id)
        self.assertFalse(request.approved_at)
        # Enviar dos veces no es una transición válida.
        with self.assertRaises(UserError):
            request.action_submit()

    # -- 4. Solicitante no puede aprobar ------------------------------------------

    def test_04_requester_cannot_approve(self):
        request = self._create_request()
        request.action_submit()
        with self.assertRaises(AccessError):
            request.action_approve()
        with self.assertRaises(AccessError):
            request.action_reject(reason="No corresponde")
        with self.assertRaises(AccessError):
            request.action_pay()
        self.assertEqual(request.state, "submitted")
        # Ni el aprobador puede enviar en nombre del solicitante.
        draft = self._create_request()
        with self.assertRaises(AccessError):
            draft.with_user(self.user_approver).action_submit()

    # -- 5. Aprobador puede aprobar ------------------------------------------------

    def test_05_approver_approves(self):
        request = self._create_request()
        request.action_submit()
        request.with_user(self.user_approver).action_approve()
        self.assertEqual(request.state, "approved")
        self.assertEqual(request.approved_by_id, self.user_approver)
        self.assertTrue(request.approved_at)
        # Aprobar un borrador no es una transición válida.
        draft = self._create_request()
        with self.assertRaises(UserError):
            draft.with_user(self.user_approver).action_approve()

    # -- 6. Rechazo sin motivo falla ------------------------------------------------

    def test_06_reject_without_reason_fails(self):
        request = self._create_request()
        request.action_submit()
        with self.assertRaises(UserError):
            request.with_user(self.user_approver).action_reject()
        self.assertEqual(request.state, "submitted")
        self.assertFalse(request.rejection_reason)
        # Rechazar un borrador tampoco es una transición válida.
        draft = self._create_request()
        with self.assertRaises(UserError):
            draft.with_user(self.user_approver).action_reject(reason="Motivo de prueba")

    # -- 7. Aprobador rechaza con motivo ---------------------------------------------

    def test_07_approver_rejects_with_reason(self):
        request = self._create_request()
        request.action_submit()
        request.with_user(self.user_approver).action_reject(reason="Documentación incompleta")
        self.assertEqual(request.state, "rejected")
        self.assertEqual(request.rejection_reason, "Documentación incompleta")

        # Flujo de interfaz: escribir el motivo en el campo y pulsar el botón.
        other = self._create_request()
        other.action_submit()
        interface_request = other.with_user(self.user_approver)
        interface_request.rejection_reason = "Fuera de presupuesto"
        interface_request.action_reject()
        self.assertEqual(other.state, "rejected")
        self.assertEqual(other.rejection_reason, "Fuera de presupuesto")

    # -- 8. Tesorería paga una aprobada -----------------------------------------------

    def test_08_treasury_pays_approved(self):
        request = self._create_request()
        request.action_submit()
        request.with_user(self.user_approver).action_approve()
        request.with_user(self.user_treasury).action_pay()
        self.assertEqual(request.state, "paid")

    # -- 9. Tesorería no paga una no aprobada -------------------------------------------

    def test_09_treasury_cannot_pay_not_approved(self):
        draft = self._create_request()
        with self.assertRaises(UserError):
            draft.with_user(self.user_treasury).action_pay()

        submitted = self._create_request()
        submitted.action_submit()
        with self.assertRaises(UserError):
            submitted.with_user(self.user_treasury).action_pay()

        self.assertEqual(draft.state, "draft")
        self.assertEqual(submitted.state, "submitted")

    # -- 10. Bloqueo de modificación después del envío -----------------------------------

    def test_10_business_fields_locked_after_submit(self):
        request = self._create_request()
        request.write({"amount": 200.0})
        self.assertEqual(request.amount, 200.0)

        request.action_submit()
        with self.assertRaises(UserError):
            request.write({"amount": 300.0})
        with self.assertRaises(UserError):
            request.write({"concept": "Otro concepto"})
        self.assertEqual(request.amount, 200.0)
        self.assertEqual(request.concept, "Compra de materiales")

    # -- 11. Solicitante solo ve solicitudes propias ---------------------------------------

    def test_11_requester_sees_only_own_requests(self):
        own = self._create_request(concept="Propia")
        other = self._create_request(user=self.user_requester_2, concept="Ajena")

        visible = self.env["payment.request"].with_user(self.user_requester).search([])
        self.assertIn(own, visible)
        self.assertNotIn(other, visible)

        with self.assertRaises(AccessError):
            other.with_user(self.user_requester).read(["name"])

    # -- 12. Aislamiento multi-compañía ---------------------------------------------------------

    def test_12_multi_company_isolation(self):
        company_b = self.env["res.company"].create({"name": "Compañía B"})
        user_b = self.env["res.users"].create({
            "name": "Solicitante Compañía B",
            "login": "requester_company_b",
            "company_id": company_b.id,
            "company_ids": [Command.set([company_b.id])],
            "groups_id": [Command.set([
                self.group_user.id,
                self.env.ref("payment_request.group_payment_requester").id,
            ])],
        })
        request_a = self._create_request(concept="De la compañía A")
        request_b = self._create_request(user=user_b, concept="De la compañía B")

        visible_b = self.env["payment.request"].with_user(user_b).search([])
        self.assertIn(request_b, visible_b)
        self.assertNotIn(request_a, visible_b)

        with self.assertRaises(AccessError):
            request_a.with_user(user_b).read(["name"])

    # -- Extra: usuario sin grupos no accede al modelo (ACL) --------------------------------

    def test_13_user_without_groups_denied(self):
        plain_user = self.env["res.users"].create({
            "name": "Usuario sin grupos",
            "login": "plain_user",
            "company_id": self.company_a.id,
            "company_ids": [Command.set([self.company_a.id])],
            "groups_id": [Command.set([self.group_user.id])],
        })
        with self.assertRaises(AccessError):
            self.env["payment.request"].with_user(plain_user).create({
                "partner_id": self.partner.id,
                "amount": 10.0,
                "concept": "Sin permiso",
            })
        with self.assertRaises(AccessError):
            self.env["payment.request"].with_user(plain_user).search([])

    # -- 14. company_id y requester_id bloqueados tras el envío ----------------------------

    def test_14_company_and_owner_locked_after_submit(self):
        company_b = self.env["res.company"].create({"name": "Compañía B"})
        request = self._create_request()
        request.action_submit()
        with self.assertRaises(UserError):
            request.write({"company_id": company_b.id})
        with self.assertRaises(UserError):
            request.write({"requester_id": self.user_requester_2.id})
        self.assertEqual(request.company_id, self.company_a)
        self.assertEqual(request.requester_id, self.user_requester)

    # -- 15. state no se escribe directamente ------------------------------------------------

    def test_15_state_cannot_be_written_directly(self):
        request = self._create_request()
        request.action_submit()
        with self.assertRaises(UserError):
            request.write({"state": "approved"})
        with self.assertRaises(UserError):
            request.with_user(self.user_approver).write({"state": "approved"})
        self.assertEqual(request.state, "submitted")

        submitted = self._create_request()
        submitted.action_submit()
        with self.assertRaises(UserError):
            submitted.with_user(self.user_treasury).write({"state": "paid"})
        self.assertEqual(submitted.state, "submitted")

        request.with_user(self.user_approver).action_approve()
        with self.assertRaises(UserError):
            request.with_user(self.user_treasury).write({"state": "paid"})
        with self.assertRaises(UserError):
            request.write({"state": "draft"})
        self.assertEqual(request.state, "approved")

    # -- 16. Auditoría no se escribe directamente ---------------------------------------------

    def test_16_audit_fields_cannot_be_written_directly(self):
        request = self._create_request()
        with self.assertRaises(UserError):
            request.write({"approved_by_id": self.user_approver.id})
        with self.assertRaises(UserError):
            request.write({"approved_at": fields.Datetime.now()})
        self.assertFalse(request.approved_by_id)
        self.assertFalse(request.approved_at)

        request.action_submit()
        request.with_user(self.user_approver).action_approve()
        approved_at = request.approved_at
        with self.assertRaises(UserError):
            request.with_user(self.user_treasury).write({
                "approved_by_id": self.user_treasury.id,
                "approved_at": False,
            })
        self.assertEqual(request.approved_by_id, self.user_approver)
        self.assertEqual(request.approved_at, approved_at)

    # -- 17. rejection_reason solo Aprobador y en submitted -------------------------------------

    def test_17_rejection_reason_only_approver_and_submitted(self):
        draft = self._create_request()
        with self.assertRaises(UserError):
            draft.with_user(self.user_approver).write({
                "rejection_reason": "Motivo en borrador",
            })

        request = self._create_request()
        request.action_submit()
        with self.assertRaises(AccessError):
            request.write({"rejection_reason": "Motivo del solicitante"})

        request.with_user(self.user_approver).write({
            "rejection_reason": "Motivo UI",
        })
        self.assertEqual(request.rejection_reason, "Motivo UI")
        request.with_user(self.user_approver).action_reject()
        self.assertEqual(request.state, "rejected")

        with self.assertRaises(UserError):
            request.with_user(self.user_approver).write({
                "rejection_reason": "Motivo cambiado",
            })
        self.assertEqual(request.rejection_reason, "Motivo UI")

    # -- 18. create sanea los campos del flujo ----------------------------------------------------

    def test_18_create_sanitizes_flow_fields(self):
        request = self._create_request(
            state="paid",
            approved_by_id=self.user_approver.id,
            approved_at=fields.Datetime.now(),
            rejection_reason="Motivo inyectado",
            name="HACK/2026/9999",
        )
        self.assertEqual(request.state, "draft")
        self.assertFalse(request.approved_by_id)
        self.assertFalse(request.approved_at)
        self.assertFalse(request.rejection_reason)
        year = fields.Date.today().year
        self.assertRegex(request.name, rf"^SP/{year}/\d{{4}}$")

    # -- 19. Solo el solicitante edita datos de negocio en borrador --------------------------------

    def test_19_only_requester_edits_draft_business_fields(self):
        draft = self._create_request()
        draft.write({"amount": 150.0, "concept": "Ajuste del solicitante"})
        self.assertEqual(draft.amount, 150.0)
        self.assertEqual(draft.concept, "Ajuste del solicitante")

        with self.assertRaises(AccessError):
            draft.with_user(self.user_approver).write({
                "amount": 999.0,
                "concept": "Edición del aprobador",
            })
        with self.assertRaises(AccessError):
            draft.with_user(self.user_treasury).write({"amount": 999.0})
        self.assertEqual(draft.amount, 150.0)
        self.assertEqual(draft.concept, "Ajuste del solicitante")

    # -- 20. Record rule de compañía rechaza create en compañía no permitida -----------------------

    def test_20_cannot_create_in_unauthorized_company(self):
        company_b = self.env["res.company"].create({"name": "Compañía B"})
        with self.assertRaises(AccessError):
            with self.env.cr.savepoint():
                self.env["payment.request"].with_user(self.user_requester).create({
                    "partner_id": self.partner.id,
                    "amount": 50.0,
                    "concept": "Compañía no permitida",
                    "company_id": company_b.id,
                })
        self.assertFalse(
            self.env["payment.request"].search_count([
                ("company_id", "=", company_b.id),
            ])
        )
