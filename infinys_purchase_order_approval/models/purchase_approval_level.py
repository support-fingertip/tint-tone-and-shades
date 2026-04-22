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
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
        help='Company this approval level applies to. Levels only match POs from the same company.',
    )

    _sql_constraints = [
        ('unique_sequence_company', 'unique(sequence, company_id)', 'The sequence must be unique per approval level within a company!'),
        ('amount_check', 'CHECK(minimum_amount <= maximum_amount OR maximum_amount = 0)', 'Minimum amount must be less than or equal to maximum amount!'),
    ]

    type = fields.Selection([
        ('vendor', 'Vendor'),
        ('supplier', 'Supplier'),
    ], string="Type", required=True,
        default=lambda self: self.env.context.get('default_type', 'vendor'))