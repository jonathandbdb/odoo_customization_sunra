# -*- coding: utf-8 -*-
import logging
import re

from . import models
from . import controllers

_logger = logging.getLogger(__name__)

# El mail de orden pendiente ("Sales: Payment Done") no lleva los datos bancarios: si el cliente
# cierra la pestaña de la confirmacion, pierde el CBU. La plantilla de correo no es heredable y
# copiarla al modulo obligaria a mantener todo el cuerpo (y perder su traduccion), asi que se
# inserta una linea en la plantilla del core (que es `noupdate="1"`, o sea que la edicion sobrevive
# a los upgrades) y se quita al desinstalar. Lo que se muestra lo arma
# `payment.transaction._get_wire_transfer_mail_block()`: asi la linea insertada no depende del
# idioma y sirve igual para todos los idiomas activos.
MAIL_TEMPLATE = "sale.mail_template_sale_payment_executed"
MAIL_ANCHOR = "</t>\n        <br/><br/>"
MAIL_MARKER = "o_swt_mail_transfer_data"
MAIL_BLOCK = (
    '        <t t-out="transaction_sudo._get_wire_transfer_mail_block()"'
    ' class="o_swt_mail_transfer_data"/>\n'
)
# Solo la linea del bloque: nada de `\s*` suelto, que se comeria la indentacion de la linea
# siguiente y dejaria el ancla (y con ella el reinstall) roto.
MAIL_BLOCK_RE = re.compile(
    r"[ \t]*<t[^>]*%s[^>]*(?:/>|>[ \t]*</t>)[ \t]*\r?\n?" % MAIL_MARKER
)


def _mail_template_langs(env):
    """
    Idiomas en los que hay que tocar el cuerpo de la plantilla.

    `body_html` es traducible: cada idioma guarda su propio cuerpo (Odoo distribuye los traducidos
    en los `.po` de `sale`). Escribir solo el idioma fuente dejaria a los idiomas ya traducidos
    mandando el mail sin los datos bancarios, en silencio.

    :rtype: list(str)
    """
    codes = env["res.lang"].search([("active", "=", True)]).mapped("code")
    return sorted(set(codes) | {"en_US"})


def _patch_mail_template(env, add):
    """
    Insertar o quitar la linea del bloque de transferencia en el mail de orden pendiente.

    Siempre se opera sobre el texto plano: los valores de un campo Html vuelven como `Markup`, y
    `Markup.replace()` escapa sus argumentos (sin convertir a `str` el reemplazo no encuentra nada
    y se pierde en silencio). El quite se hace por el marcador, no por igualdad de string, para que
    siga funcionando si el sanitizer o una edicion posterior reacomodan el nodo.

    :param add: True para insertar la linea, False para quitarla
    :type add: bool
    """
    template = env.ref(MAIL_TEMPLATE, raise_if_not_found=False)
    if not template:
        _logger.warning("no se encontro la plantilla de correo %s", MAIL_TEMPLATE)
        return
    for lang in _mail_template_langs(env):
        template_lang = template.with_context(lang=lang)
        body = str(template_lang.body_html or "")
        patched = MAIL_MARKER in body
        if add and not patched:
            if body.count(MAIL_ANCHOR) != 1:
                # La plantilla fue editada a mano: no se adivina donde va el bloque.
                _logger.warning(
                    "no se pudo ubicar el punto de insercion en %s (%s): el mail de orden"
                    " pendiente queda sin los datos bancarios",
                    MAIL_TEMPLATE, lang,
                )
                continue
            template_lang.body_html = body.replace(
                MAIL_ANCHOR, "</t>\n" + MAIL_BLOCK + "        <br/><br/>"
            )
        elif not add and patched:
            clean = MAIL_BLOCK_RE.sub("", body)
            # Si quedo algo del bloque (p.ej. porque una version anterior insertaba varias lineas),
            # mejor dejarlo que escribir un cuerpo a medio limpiar.
            if MAIL_MARKER in clean or "_get_wire_transfer_" in clean:
                # Mejor dejarlo que romper el cuerpo con un reemplazo a ciegas.
                _logger.warning(
                    "no se pudo quitar el bloque de %s (%s): revisar la plantilla a mano",
                    MAIL_TEMPLATE, lang,
                )
                continue
            if MAIL_ANCHOR not in clean:
                _logger.warning(
                    "el cuerpo de %s (%s) quedo sin el punto de insercion: revisar si hace falta"
                    " restaurar la plantilla (boton 'Restablecer plantilla')",
                    MAIL_TEMPLATE, lang,
                )
            template_lang.body_html = clean


def _check_cbu_configuration(env):
    """ Avisar en el log si falta lo que la feature necesita para hacer algo. """
    providers = env["payment.provider"].search([
        ("code", "=", "custom"), ("custom_mode", "=", "wire_transfer"),
    ])
    if providers and not any(p._get_wire_transfer_cbu_account() for p in providers):
        _logger.warning(
            "ninguna compania con proveedor de transferencia tiene cargada una cuenta bancaria con"
            " CBU (res.partner.bank con acc_type 'cbu', tipo que aporta l10n_ar): el boton"
            " 'Copiar CBU' no se va a mostrar hasta que se cargue"
        )


def post_init_hook(env):
    _patch_mail_template(env, add=True)
    _check_cbu_configuration(env)


def uninstall_hook(env):
    # Sin el modulo, el bloque llamaria a un metodo que ya no existe y el mail del core dejaria de
    # renderizarse para TODAS las ordenes pendientes, no solo para las transferencias.
    _patch_mail_template(env, add=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
