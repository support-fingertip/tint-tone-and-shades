{
    'name': 'TT Purchase Portal Pricing',
    'version': '19.0.1.0.0',
    'category': 'Purchase',
    'summary': 'Show pricing columns on RFQ portal and allow vendors to edit unit price',
    'description': """
        Extends the Purchase Order portal view to:
        - Show Unit Price, Taxes, Discount, Amount columns on RFQ portal (not just confirmed POs)
        - Allow vendors to edit Unit Price directly on the RFQ portal page
        - Show totals section on RFQ portal page
        - Unit Price becomes read-only once the order is confirmed as a Purchase Order
    """,
    'author': 'Tint Tone & Shade',
    'website': 'https://tinttoneandshade.com',
    'license': 'LGPL-3',
    'depends': ['purchase'],
    'data': [
        'views/purchase_portal_templates.xml',
        'views/template_rfq.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'tt_purchase_portal_pricing/static/src/js/purchase_portal_update_price.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
