# -*- coding: utf-8 -*-
{
    'name': 'Quotation Sync — TTS Builder ↔ Odoo',
    'version': '19.0.2.0.0',
    'summary': 'Sync approved quotations from TTS Quotation Builder into Odoo Sale Orders and BOQs',
    'description': """
       
      
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
        'boq_management_v19',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/tts_quotation_views.xml',
        'views/tts_sync_log_views.xml',
        'views/res_config_settings_views.xml',
        'views/boq_boq_inherit_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
