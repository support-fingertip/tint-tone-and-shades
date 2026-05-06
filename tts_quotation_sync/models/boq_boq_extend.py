# -*- coding: utf-8 -*-
from odoo import fields, models


class BoqBoqExtend(models.Model):
    """
    Extends boq.boq to add a back-reference to the TTS quotation that
    originated this BOQ.  The field is set automatically by
    TtsQuotation.action_create_boq() and is never editable by the user.
    """
    _inherit = 'boq.boq'

    tts_quotation_id = fields.Many2one(
        comodel_name='tts.quotation',
        string='TTS Quotation',
        readonly=True,
        ondelete='set null',
        index=True,
        help='TTS quotation record from which this BOQ was generated',
    )
