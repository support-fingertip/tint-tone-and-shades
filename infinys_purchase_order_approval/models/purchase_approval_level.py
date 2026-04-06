from odoo import models, fields

class PurchaseApprovalLevel(models.Model):
    _name = 'purchase.approval.level'
    _description = 'Purchase Approval Level'
    _order = 'sequence'

    name = fields.Char(string='Level Name', required=True)
    minimum_amount = fields.Float(string='Minimum Amount', required=True, help='Minimum amount for this approval level to be required.')
    maximum_amount = fields.Float(string='Maximum Amount', help='Maximum amount for this approval level to be required. Leave 0 for no upper limit.')
    sequence = fields.Integer(string='Sequence', default=10, help='The order in which approval levels are checked.')
    user_ids = fields.Many2many('res.users', string='Required Users', help='Specific users who can approve at this level.')

    _sql_constraints = [
        ('unique_sequence', 'unique(sequence)', 'The sequence must be unique per approval level!'),
        ('amount_check', 'CHECK(minimum_amount <= maximum_amount OR maximum_amount = 0)', 'Minimum amount must be less than or equal to maximum amount!'),
    ]