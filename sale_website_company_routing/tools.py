# -*- coding: utf-8 -*-
from odoo.http import request


def get_request_memo(name):
    """
    Diccionario que vive lo que dura el request HTTP, para no repetir lecturas por producto en
    las grillas de la tienda.

    Fuera de un request (tests, cron, shell) devuelve un diccionario nuevo: no memoriza nada.

    :param name: nombre de la memoria
    :type name: str
    :return: diccionario de la memoria
    :rtype: dict
    """
    if not request:
        return {}
    attr = "scr_memo_%s" % name
    memo = getattr(request, attr, None)
    if memo is None:
        memo = {}
        setattr(request, attr, memo)
    return memo

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
