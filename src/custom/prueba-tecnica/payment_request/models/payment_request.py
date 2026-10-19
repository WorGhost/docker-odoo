from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class PaymentRequest(models.Model):
    _name = "payment.request"
    _description = "Payment request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "request_date desc, id desc"

    #: Campos de negocio que quedan bloqueados cuando la solicitud ya no es borrador.
    #: En borrador solo puede modificarlos el solicitante propietario.
    _BUSINESS_FIELDS = {
        "partner_id",
        "requester_id",
        "amount",
        "currency_id",
        "request_date",
        "concept",
        "company_id",
    }
    #: Campos que solo cambian mediante las acciones del flujo.
    _FLOW_FIELDS = {"state", "name", "approved_by_id", "approved_at"}

    name = fields.Char(
        string="Referencia",
        default="New",
        required=True,
        copy=False,
        readonly=True,
        help="Se asigna automáticamente con la secuencia SP/AÑO/NNNN.",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Beneficiario",
        required=True,
        tracking=True,
    )
    requester_id = fields.Many2one(
        "res.users",
        string="Solicitante",
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
    )
    amount = fields.Monetary(string="Monto", required=True, tracking=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    request_date = fields.Date(
        string="Fecha de solicitud",
        default=fields.Date.context_today,
        required=True,
    )
    concept = fields.Char(string="Concepto", required=True)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("submitted", "Enviada"),
            ("approved", "Aprobada"),
            ("rejected", "Rechazada"),
            ("paid", "Pagada"),
        ],
        string="Estado",
        default="draft",
        required=True,
        copy=False,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    approved_by_id = fields.Many2one(
        "res.users",
        string="Aprobada por",
        readonly=True,
        copy=False,
    )
    approved_at = fields.Datetime(
        string="Fecha de aprobación",
        readonly=True,
        copy=False,
    )
    rejection_reason = fields.Text(
        string="Motivo de rechazo",
        copy=False,
        help="Obligatorio al rechazar. Se puede escribir mientras la solicitud está enviada.",
    )

    # ------------------------------------------------------------------
    # Creación y validaciones
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        clean_vals_list = []
        for vals in vals_list:
            clean_vals = dict(vals)
            clean_vals["name"] = (
                self.env["ir.sequence"].next_by_code("payment.request") or "New"
            )
            clean_vals["state"] = "draft"
            clean_vals.pop("approved_by_id", None)
            clean_vals.pop("approved_at", None)
            clean_vals.pop("rejection_reason", None)
            clean_vals_list.append(clean_vals)
        return super().create(clean_vals_list)

    @api.constrains("amount")
    def _check_amount_positive(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_("El monto debe ser mayor que cero."))

    def write(self, vals):
        # El superusuario conserva el comportamiento administrativo.
        if self.env.su:
            return super().write(vals)

        if self._FLOW_FIELDS & set(vals):
            raise UserError(
                _(
                    "El estado, la referencia y los datos de aprobación solo "
                    "cambian mediante las acciones del flujo."
                )
            )

        if "rejection_reason" in vals:
            if not self.env.user.has_group(
                "payment_request.group_payment_approver"
            ):
                raise AccessError(
                    _("Solo el grupo Aprobador puede indicar el motivo de rechazo.")
                )
            if any(record.state != "submitted" for record in self):
                raise UserError(
                    _(
                        "El motivo de rechazo solo puede modificarse mientras "
                        "la solicitud está enviada."
                    )
                )

        if self._BUSINESS_FIELDS & set(vals):
            for record in self:
                if record.state != "draft":
                    raise UserError(
                        _(
                            "La solicitud %(name)s ya fue enviada: no se pueden "
                            "modificar sus datos de negocio.",
                            name=record.name,
                        )
                    )
                if record.requester_id != self.env.user:
                    raise AccessError(
                        _(
                            "Solo el solicitante puede modificar los datos de "
                            "negocio de un borrador."
                        )
                    )

        return super().write(vals)

    @api.private
    def _write_flow(self, vals):
        """Escritura interna de las transiciones de estado y auditoría.

        Omite las guardas de ``write`` pero conserva las ACL y record rules
        del usuario actual (no usa ``sudo``) y el tracking de ``mail.thread``.
        No es invocable por RPC: Odoo bloquea los métodos privados.
        """
        return super().write(vals)

    # ------------------------------------------------------------------
    # Transiciones (validadas dentro de cada método, no solo por botones)
    # ------------------------------------------------------------------
    def action_submit(self):
        """Enviar: solo el solicitante, y solo desde borrador."""
        self.ensure_one()
        if self.requester_id != self.env.user:
            raise AccessError(
                _("Solo el solicitante puede enviar su propia solicitud.")
            )
        if self.state != "draft":
            raise UserError(_("Solo una solicitud en borrador puede enviarse."))
        self._write_flow({"state": "submitted"})

    def action_approve(self):
        """Aprobar: solo Aprobador, desde enviada. Registra aprobador y fecha."""
        self.ensure_one()
        if not self.env.user.has_group("payment_request.group_payment_approver"):
            raise AccessError(
                _("Solo el grupo Aprobador puede aprobar solicitudes.")
            )
        if self.state != "submitted":
            raise UserError(_("Solo una solicitud enviada puede aprobarse."))
        self._write_flow(
            {
                "state": "approved",
                "approved_by_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
            }
        )

    def action_reject(self, reason=None):
        """Rechazar: solo Aprobador, desde enviada y con motivo obligatorio.

        El motivo puede venir por argumento o estar escrito en el campo
        ``rejection_reason`` antes de pulsar el botón.
        """
        self.ensure_one()
        if not self.env.user.has_group("payment_request.group_payment_approver"):
            raise AccessError(
                _("Solo el grupo Aprobador puede rechazar solicitudes.")
            )
        if self.state != "submitted":
            raise UserError(_("Solo una solicitud enviada puede rechazarse."))
        reason = (reason if reason is not None else self.rejection_reason) or ""
        reason = reason.strip()
        if not reason:
            raise UserError(_("Debe indicar un motivo de rechazo."))
        self._write_flow({"state": "rejected", "rejection_reason": reason})

    def action_pay(self):
        """Marcar como pagada: solo Tesorería y solo si está aprobada."""
        self.ensure_one()
        if not self.env.user.has_group("payment_request.group_payment_treasury"):
            raise AccessError(
                _("Solo el grupo Tesorería puede marcar solicitudes como pagadas.")
            )
        if self.state != "approved":
            raise UserError(_("Solo una solicitud aprobada puede marcarse como pagada."))
        self._write_flow({"state": "paid"})
