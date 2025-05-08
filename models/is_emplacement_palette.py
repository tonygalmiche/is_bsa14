from odoo import models,fields,api


class is_emplacement_palette(models.Model):
    _name = "is.emplacement.palette"
    _description="Emplacement des palettes"
    _order='name'

    name = fields.Char(string="Emplacement",required=True)


class is_emplacement_palette_stock(models.Model):
    _name = "is.emplacement.palette.stock"
    _description="Stock par emplacement des palettes"
    _rec_name = 'product_id'
    _order='product_id,emplacement_id'

    emplacement_id = fields.Many2one("is.emplacement.palette", string="Emplacement",required=True)
    product_id     = fields.Many2one("product.product", string="Article",required=True)
    quantite       = fields.Float('Quantité',required=True)


class is_emplacement_palette_mouvement(models.Model):
    _name = "is.emplacement.palette.mouvement"
    _description="Mouvements de stock des palettes"
    _rec_name = 'id'
    _order='id desc'

    emplacement_src_id = fields.Many2one("is.emplacement.palette", string="Emplacement source",required=True)
    emplacement_dst_id = fields.Many2one("is.emplacement.palette", string="Emplacement de destination",required=True)
    product_id     = fields.Many2one("product.product", string="Article",required=True)
    quantite       = fields.Float('Quantité',required=True)
    state          = fields.Selection([
        ('creation', 'Création'),
        ('valide'  , 'Validé'),
    ], "État", required=True, copy=False, default='creation')


    def validation_action(self):
        for obj in self:
            #** Enlever le stock de l'emplacement d'origine *******************
            domain=[
                ('product_id' ,'=', obj.product_id.id),
                ('emplacement_id' ,'=', obj.emplacement_src_id.id),
            ]
            stock=self.env['is.emplacement.palette.stock'].search(domain,limit=1)
            if len(stock)==0:
                vals={
                    'emplacement_id': obj.emplacement_src_id.id,
                    'product_id'    : obj.product_id.id,
                    'quantite'      : - obj.quantite,
                }
                self.env['is.emplacement.palette.stock'].create(vals)
            else:
                stock.quantite = stock.quantite - obj.quantite
            #******************************************************************

            #** Ajouter le stock de l'emplacement de destination **************
            domain=[
                ('product_id' ,'=', obj.product_id.id),
                ('emplacement_id' ,'=', obj.emplacement_dst_id.id),
            ]
            stock=self.env['is.emplacement.palette.stock'].search(domain,limit=1)
            if len(stock)==0:
                vals={
                    'emplacement_id': obj.emplacement_dst_id.id,
                    'product_id'    : obj.product_id.id,
                    'quantite'      : obj.quantite,
                }
                self.env['is.emplacement.palette.stock'].create(vals)
            else:
                stock.quantite = stock.quantite + obj.quantite
            #******************************************************************

            obj.state='valide'
        return True