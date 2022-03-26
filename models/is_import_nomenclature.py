# -*- coding: utf-8 -*-
from odoo import models,fields,api
from odoo.exceptions import Warning
import base64


def str2int(s):
    try:
        return int(s)
    except ValueError:
        return 0


class is_import_nomenclature(models.Model):
    _name='is.import.nomenclature'
    _description='is.import.nomenclature'
    _order='name'
    _sql_constraints = [('name_uniq','UNIQUE(name)', 'Ce code existe déjà')]

    name           =  fields.Many2one('product.template', 'Article', domain="[('type', '!=', 'service')]", required=True)
    bom_id         =  fields.Many2one('mrp.bom', 'Nomenclature', readonly=True)
    resultat       =  fields.Text("Résultat de l'importation", readonly=True)
    attachment_ids = fields.Many2many('ir.attachment', 'is_import_nomenclature_attachment_rel', 'import_id', 'attachment_id', 'Nomenclature à importer')


    def action_import_nomenclature(self):
        for obj in self:
            boms=self.env['mrp.bom'].search([('product_tmpl_id', '=', obj.name.id)])
            if len(boms)>0:
                raise Warning("Il existe déja une nomenclature par cet article")
            err=[]
            for attachment in obj.attachment_ids:
                vals = {
                    'product_tmpl_id': obj.name.id,
                }
                bom_id = self.env['mrp.bom'].create(vals)
                csv=base64.b64decode(attachment.datas).decode('latin-1') # 'latin-1' cp1252
                rows=csv.split("\r\n")
                lig=0
                for row in rows:
                    if lig:
                        cols=row.split(";")
                        if len(cols)>2:
                            test=True
                            product_tmpl_id=str2int(cols[1])
                            if product_tmpl_id:
                                products = self.env['product.product'].search([('product_tmpl_id','=',product_tmpl_id)])
                                for product in products:
                                    test=False
                                    vals={
                                        'bom_id'     : bom_id.id,
                                        'sequence'   : cols[0],
                                        'product_id' : product.id,
                                        'product_qty': cols[2],
                                    }
                                    line_id = self.env['mrp.bom.line'].create(vals)
                                    err.append('OK : '+cols[2]+' x '+product.name)
                            if test:
                                err.append('ERR : Composant '+cols[2]+' (id='+(cols[1] or '')+') non trouvé ('+cols[3]+')')
                    lig=lig+1
            obj.bom_id=bom_id.id
            obj.resultat='\n'.join(err)

