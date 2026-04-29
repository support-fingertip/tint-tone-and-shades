# -*- coding: utf-8 -*-
{
    'name': 'Quotation Sync — TTS Builder ↔ Odoo',
    'version': '19.0.1.0.0',
    'summary': 'Sync approved quotations from TTS Quotation Builder into Odoo Sale Orders',
    'description': """
        Polls the TTS Quotation Builder REST API, imports approved quotations,
        optionally auto-creates Sale Orders (wood / civil / handles line items),
        and calls back the API to mark each quotation as Success or Failure.
    """,
    'author': 'Tint Tone & Shades',
    'category': 'Sales/Sales',
    'license': 'OPL-1',
    'depends': [
        'base',
        'mail',
        'product',
        'sale',
        'sale_management',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/tts_quotation_views.xml',
        'views/tts_sync_log_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
