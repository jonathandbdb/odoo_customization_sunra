# -*- coding: utf-8 -*-


def pre_init_hook(env):
    """
    Crear y completar la columna de la compañia de la linea antes de cargar el modelo.

    Asi el ORM no recalcula `sale_company_id` sobre todo el historico al instalar.

    :param env: entorno de Odoo
    """
    env.cr.execute("ALTER TABLE sale_order_line ADD COLUMN IF NOT EXISTS sale_company_id int4")
    env.cr.execute(
        "UPDATE sale_order_line SET sale_company_id = company_id WHERE display_type IS NULL"
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
