# -*- coding: utf-8 -*-
from openerp.osv import fields, osv

class res_company(osv.osv):
    _inherit = 'res.company'
    
    _columns = {
            'report_external_link': fields.char("Report External Link", size=128)
    }

class hr_config_settings(osv.osv_memory):
    _inherit = 'hr.config.settings'

    _columns = {
            'report_external_link': fields.char("Report External Link", size=128)
    }

    def _get_report_external_link(self, cr, uid, context):
        company = self.pool.get('res.users').browse(cr, uid, uid, context).company_id
        if company and company.report_external_link:
            return company.report_external_link
        return False
    
    _defaults= {
        'report_external_link': _get_report_external_link
    }

    def execute(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids, context)[0]
        if wizard.report_external_link:
            user = self.pool.get('res.users').browse(cr, uid, uid, context)
            user.company_id.write({'report_external_link': wizard.report_external_link})
        return super(hr_config_settings, self).execute(cr, uid, ids, context=context)
