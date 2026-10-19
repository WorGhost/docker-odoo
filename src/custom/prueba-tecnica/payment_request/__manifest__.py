{
    "name": "Payment Requests",
    "summary": "Solicitudes de pago internas con flujo de aprobación (Ejercicio 4, tramo A)",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "author": "Binaural",
    "license": "LGPL-3",
    "depends": ["mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "security/payment_request_rules.xml",
        "data/ir_sequence_data.xml",
        "views/payment_request_views.xml",
        "views/payment_request_menus.xml",
    ],
    "installable": True,
    "application": False,
}
