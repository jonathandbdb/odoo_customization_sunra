# -*- coding: utf-8 -*-
import logging
import re
from html import unescape

from odoo import api, models

_logger = logging.getLogger(__name__)

# Leyenda "Cod: XXX" que se cargaba a mano en las descripciones del producto antes de que el codigo
# saliera de la variante. Ver README.md, seccion "Limpieza de las leyendas manuales".
MANUAL_CODE_RE = re.compile(r"^\s*cod\.?\s*:", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]*>")

# Campos donde vivia la leyenda: (nombre, es_html)
DESCRIPTION_FIELDS = (
    ("description_ecommerce", True),
    ("description_sale", False),
)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    #=== BUSINESS METHODS ===#

    def _get_additionnal_combination_info(self, product_or_template, quantity, uom, date, website):
        # La pagina de producto se renderiza para la plantilla, asi que el frontend no tiene forma
        # de saber el codigo de la variante elegida: lo agregamos al payload que ya consume el JS
        # al cambiar la seleccion (/website_sale/get_combination_info).
        combination_info = super()._get_additionnal_combination_info(
            product_or_template, quantity, uom, date, website
        )
        combination_info["default_code"] = product_or_template.default_code or ""
        return combination_info

    #=== DATAFIX ===#

    @api.model
    def _extract_manual_code_residue(self, value, is_html):
        """
        Devolver el contenido de una descripcion sin las leyendas "Cod: ...".

        :param value: contenido actual del campo (str)
        :param is_html: True si el campo es HTML (no se edita a ciegas)
        :type is_html: bool
        :return: str con lo que queda al sacar las leyendas, o None si el campo tiene contenido
            real mezclado con la leyenda en HTML (ahi no tocamos nada: revision manual)
        :rtype: str | None
        """
        if not value:
            return ""
        text = HTML_TAG_RE.sub("\n", value) if is_html else value
        lines = [line.strip() for line in unescape(text).splitlines()]
        kept = [line for line in lines if line and not MANUAL_CODE_RE.match(line)]
        if not kept:
            return ""
        if is_html:
            # Reescribir HTML parcialmente es riesgoso: lo dejamos para revision manual.
            return None
        return "\n".join(kept)

    @api.model
    def _has_manual_code(self, value, is_html):
        # Detectar si el campo trae la leyenda en alguna de sus lineas
        if not value:
            return False
        text = HTML_TAG_RE.sub("\n", value) if is_html else value
        return any(MANUAL_CODE_RE.match(line.strip()) for line in unescape(text).splitlines())

    @api.model
    def _clean_manual_code_descriptions(self, dry_run=True):
        """
        Limpiar las leyendas "Cod: ..." cargadas a mano en las descripciones de los productos.

        El codigo interno ahora sale de la variante (ver README.md), asi que la leyenda manual
        quedaria duplicada y, en los productos con varias variantes, contradictoria.

        Solo borra lo que reconoce como leyenda: si el campo tiene contenido real ademas de la
        leyenda, lo deja intacto y lo reporta para revision manual. Es idempotente: correrlo dos
        veces no cambia nada la segunda vez.

        :param dry_run: si es True (default) no escribe, solo informa que haria
        :type dry_run: bool
        :return: dict con 'cleaned' (lo limpiado, con el valor previo) y 'skipped' (lo que
            necesita revision manual)
        :rtype: dict
        """
        langs = self.env["res.lang"].get_installed()
        lang_codes = [code for code, _name in langs] or ["en_US"]

        # El campo es traducible: buscamos idioma por idioma para no perder los productos cuya
        # leyenda esta solo en una traduccion.
        candidates = self.env["product.template"]
        for lang in lang_codes:
            candidates |= self.with_context(active_test=False, lang=lang).search([
                "|",
                ("description_ecommerce", "ilike", "cod:"),
                ("description_sale", "ilike", "cod:"),
            ])

        cleaned = []
        skipped = []
        for template in candidates:
            for fname, is_html in DESCRIPTION_FIELDS:
                values = {
                    lang: template.with_context(lang=lang)[fname] or ""
                    for lang in lang_codes
                }
                if not any(self._has_manual_code(value, is_html) for value in values.values()):
                    continue

                residues = {}
                for lang, value in values.items():
                    residue = self._extract_manual_code_residue(value, is_html)
                    if residue is None:
                        skipped.append({
                            "id": template.id,
                            "field": fname,
                            "lang": lang,
                            "reason": "contenido real mezclado con la leyenda",
                            "value": value,
                        })
                        break
                    residues[lang] = residue
                else:
                    cleaned.append({
                        "id": template.id,
                        "field": fname,
                        "previous": values,
                        "residue": residues,
                    })
                    # El valor previo va al log: es la unica copia auditable de lo que se borra.
                    _logger.info(
                        "[variant_code] product.template %s.%s previo=%r nuevo=%r%s",
                        template.id, fname, values, residues, " (dry run)" if dry_run else "",
                    )
                    if dry_run:
                        continue
                    if any(residues.values()):
                        for lang, residue in residues.items():
                            template.with_context(lang=lang)[fname] = residue or False
                    else:
                        # Nada que conservar en ningun idioma: se limpia el campo entero.
                        template[fname] = False

        _logger.info(
            "[variant_code] limpieza de leyendas: %s campos limpiados, %s para revision manual%s",
            len(cleaned), len(skipped), " (dry run)" if dry_run else "",
        )
        return {"cleaned": cleaned, "skipped": skipped}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
