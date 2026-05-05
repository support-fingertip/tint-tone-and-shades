# -*- coding: utf-8 -*-
{
    'name': 'Quotation Sync — TTS Builder ↔ Odoo',
    'version': '19.0.2.0.0',
    'summary': 'Sync approved quotations from TTS Quotation Builder into Odoo Sale Orders and BOQs',
    'description': """
        Polls the TTS Quotation Builder REST API, imports approved quotations,
        optionally auto-creates Sale Orders (wood / civil / handles line items),
        calls back the API to mark each quotation as Success or Failure,
        and enables BOQ creation directly from each synced quotation record.

        Features:
        - Full API response body captured and stored per record (Task 1)
        - Exact error reason stored on the record when processing fails (Task 2)
        - Automatic retry up to 3 times before marking a record as failed (Task 3)
        - Two-step API flow: Second API (mark-reviewed) only fires after
          the First API data is fully processed in Odoo (Task 4)
        - BOQ created only from the TTS quotation form; line categories
          map automatically to BOQ work categories (Task 5)
    """,
    'author': 'Tint Tone & Shades',
    'category': 'Sales/Sales',
    'license': 'OPL-1',
    'depends': [
        'base',
        'base_setup',
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
    'application': True,
    'auto_install': False,
}
