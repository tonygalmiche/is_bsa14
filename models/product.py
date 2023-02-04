# -*- coding: utf-8 -*-
from odoo import models,fields,api
from lxml import etree
import xml.etree.ElementTree as ET
import uuid
import base64
import codecs
import unicodedata
import os
import time
import logging
_logger = logging.getLogger(__name__)


class is_position_dans_produit(models.Model):
    _name = "is.position.dans.produit"
    _description = "is.position.dans.produit"
    name = fields.Char(string='Position dans produit', size=32)


class is_stock_category(models.Model):
    _name = "is.stock.category"
    _description="is_stock_category"
    name = fields.Char(string="Code", size=32)


class is_famille(models.Model):
    _name = "is.famille"
    _description="Famille d'article"
    name = fields.Char(string="Famille")


class is_product_type_cuve(models.Model):
    _name = "is.product.type.cuve"
    _description="Type de cuve pour la fiche article"
    _order="name"
    name = fields.Char(string="Type de cuve", required=True)


class is_volume_cuve(models.Model):
    _name = "is.volume.cuve"
    _description="Volume de cuve pour la fiche article"
    _order="name"
    name = fields.Char(string="Volume", required=True)


class product_template(models.Model):
    _inherit = 'product.template'
    
    is_ce_en1090                 = fields.Boolean('CE EN1090', help="Si cette case est cochée, le logo CE 1166 apparaîtra sur le BL")
    is_numero_certificat         = fields.Char('Numéro du certificat',help=u"Numéro du certificat associé au logo CE 1166",default="1166-CPR-0258")
    is_stock_prevu_valorise      = fields.Float('Stock prévu valorisé'     , store=False, compute='_compute')
    is_stock_disponible_valorise = fields.Float('Stock disponible valorisé', store=False, compute='_compute')
    is_recalcul_prix_revient     = fields.Boolean('Recalcul automatique du prix de revient', help="Si cette case est cochée, le prix de revient sera recalculé pendant la nuit")
    is_position_dans_produit_ids = fields.Many2many('is.position.dans.produit','is_position_dans_produit_product_rel','product_id','position_id', string="Position dans produit")
    is_doublon                   = fields.Char('Doublon', store=False, compute='_compute_doublon')
    is_import_par_mail           = fields.Boolean('Article importé par mail')
    is_masse_tole                = fields.Float('Masse tôle')
    is_famille_id                = fields.Many2one("is.famille", string="Famille")
    is_stock_category_id         = fields.Many2one("is.stock.category", string="Catégorie de stock")
    is_type_equipement_id        = fields.Many2one("is.type.equipement", string="Type d'équipement")
    is_trace_reception           = fields.Boolean('Traçabilité en réception')
    is_gestion_lot               = fields.Boolean('Gestion par lots', default=False)
    is_description_devis         = fields.Text('Description devis')
    is_simulation_livrable       = fields.Boolean('Simulation livrable', help="Utilisé dans le calcul des besoins de la simulation livrable des ventes")
    is_article_pour_devis        = fields.Boolean('Article pour devis' , help="Utilisé pour calculer le cout des équipements pour les devis paramètrable")
    is_type_livraison            = fields.Selection([
            ('livraison_biens'    , 'Livraison de biens'),
            ('prestation_services', 'Prestation de services'),
        ], "Type de livraison", default='livraison_biens', help="Mention obligatoire sur les factures depuis le 01/10/22")

    is_cuve_thermoregulation  = fields.Boolean("Thermorégulation", default=False)
    is_cuve_isolation         = fields.Boolean("Isolation"       , default=False)
    is_cuve_compartimente     = fields.Boolean("Compartimenté"   , default=False)
    is_cuve_plafond_mobile    = fields.Boolean("Plafond mobile"  , default=False)
    is_cuve_niveau_complexite = fields.Text('Niveau de compléxité', store=True, compute='_compute_is_cuve_niveau_complexite')
    is_type_cuve_id           = fields.Many2one("is.product.type.cuve", string="Type de cuve")
    is_volume_cuve_id         = fields.Many2one("is.volume.cuve", string="Volume cuve")


    @api.depends('is_cuve_thermoregulation','is_cuve_isolation','is_cuve_compartimente','is_cuve_plafond_mobile')
    def _compute_is_cuve_niveau_complexite(self):
        for obj in self:
            t=[]
            if obj.is_cuve_thermoregulation:
                t.append("Thermorégulation")
            if obj.is_cuve_isolation:
                t.append("Isolation")
            if obj.is_cuve_compartimente:
                t.append("Compartimenté")
            if obj.is_cuve_plafond_mobile:
                t.append("Plafond mobile")
            val = ", ".join(t)
            obj.is_cuve_niveau_complexite = val


    # x : Position x à partir de la gauche
    # y : Position y à partir du bas (entre 0 et 200)
    # sizex : Taille X des caractères (1 à 9)
    # sizey : Taille Y des caractères (1 à 9)
    def datamax(self,sizex, sizey, y, x, txt):
        sizex="0"+str(sizex)
        sizex=sizex[-1:]

        sizey="0"+str(sizey)
        sizey=sizey[-1:]

        x="0000"+str(x)
        x=x[-4:]

        y="0000"+str(y)
        y=y[-4:]

        r="10"+sizex+sizey+"000"+y+x+(txt or '')+chr(10)
        return r


    def generer_etiquette(self):
        for obj in self:
            txt=""
            txt=txt+chr(2)+"qC"+chr(10)
            txt=txt+chr(2)+"qC"+chr(10)
            txt=txt+chr(2)+"n"+chr(10)
            txt=txt+chr(2)+"e"+chr(10)
            txt=txt+chr(2)+"c0000"+chr(10)
            txt=txt+chr(2)+"Kf0000"+chr(10)
            txt=txt+chr(2)+"V0"+chr(10)
            txt=txt+chr(2)+"M0591"+chr(10)
            txt=txt+chr(2)+"L"+chr(10)
            txt=txt+"A2"+chr(10)
            txt=txt+"D11"+chr(10)
            txt=txt+"z"+chr(10)
            txt=txt+"PG"+chr(10)
            txt=txt+"SG"+chr(10)
            txt=txt+"pC"+chr(10)
            txt=txt+"H20"+chr(10)

            name1=""
            name2=""
            name3=""
            name1=obj.name[0:30]
            if len(obj.name)>30:
                name2=obj.name[30:60]
            if len(obj.name)>60:
                name3=obj.name[60:]

            txt=txt+self.datamax(x=15,y=200,sizex=2,sizey=2,txt="ARTICLE:")
            txt=txt+self.datamax(x=15,y=180,sizex=3,sizey=4,txt=name1) #.encode("utf-8"))
            txt=txt+self.datamax(x=15,y=155,sizex=3,sizey=4,txt=name2) #.encode("utf-8"))
            txt=txt+self.datamax(x=15,y=130,sizex=3,sizey=4,txt=name3) #.encode("utf-8"))

            txt=txt+self.datamax(x=15,y=110,sizex=2,sizey=2,txt="FOURNISSEUR:")
            for line in obj.seller_ids:
                fournisseur=line.name.name
                txt=txt+self.datamax(x=15,y=90,sizex=4,sizey=4,txt=fournisseur) #.encode("utf-8"))
                break

            now=time.strftime('%Y-%m-%d',time.gmtime())
            txt=txt+self.datamax(x=15,y=70,sizex=2,sizey=2,txt="DATE:")
            txt=txt+self.datamax(x=15,y=50,sizex=4,sizey=4,txt=now)

            txt=txt+self.datamax(x=250,y=70,sizex=2,sizey=2,txt="ID:")
            txt=txt+self.datamax(x=250,y=50,sizex=4,sizey=4,txt=str(obj.id))

            txt=txt+self.datamax(x=15,y=30,sizex=2,sizey=2,txt="REFERENCE:")
            txt=txt+self.datamax(x=15,y=10 ,sizex=4,sizey=4,txt=obj.default_code) #.encode("utf-8"))

            txt=txt+"^01"+chr(10)
            txt=txt+"Q0001"+chr(10)
            txt=txt+"E"+chr(10)
            return txt


    def imprimer_etiquette_direct(self):
        for obj in self:
            etiquettes=self.generer_etiquette()
            path="/tmp/etiquette.txt"
            err=""
            fichier = open(path, "w", encoding="windows-1252")
            if err=="":
                fichier.write(etiquettes )
                fichier.close()
                user  = self.env['res.users'].browse(self._uid)
                imprimante = user.company_id.is_nom_imprimante or 'Datamax'
                cmd="lpr -h -P"+imprimante+" "+path
                os.system(cmd)


    def message_new(self, cr, uid, msg_dict, custom_values=None, context=None):
        """Méthode provenant par surcharge de mail.tread permettant de personnaliser la création de l'article lors de la réception d'un mail avec le serveur de courrier entrant créé"""
        if context is None:
            context = {}
        data = {}
        if isinstance(custom_values, dict):
            data = custom_values.copy()
        model = context.get('thread_model') or self._name
        model_pool = self.pool[model]
        fields = model_pool.fields_get(cr, uid, context=context)
        if 'name' in fields and not data.get('name'):
            data['name'] = msg_dict.get('subject', '')

        if msg_dict.get('body'):
            filename = '/tmp/product.template-%s.xml' % uuid.uuid4()
            temp = open(filename, 'w+b')
            description = msg_dict.get('body')
            description = description.encode('utf-8')
            temp.write(description)
            temp.close()
            tree = ET.parse(filename)
            root = tree.getroot()
            for n1 in root:
                if n1.tag in fields:
                    data[n1.tag] = n1.text.strip()
            data['is_import_par_mail'] = True
        res_id = model_pool.create(cr, uid, data, context=context)
        return res_id


    def _compute_doublon(self):
        for obj in self:
            doublon=False
            products=self.env['product.template'].search([
                ('name', '=' , obj.name),
                ('id'  , '!=', obj.id),
            ])
            ids=[]
            if len(products)>0:
                for product in products:
                    ids.append(str(product.id))
                doublon=u'Doublon Nom : '+', '.join(ids)
            products=self.env['product.template'].search([
                ('default_code', '=' , obj.default_code),
                ('default_code', '!=' , False),
                ('id'  , '!=', obj.id),
            ])
            ids=[]
            if len(products)>0:
                for product in products:
                    ids.append(str(product.id))
                doublon=u'Doublon Référence : '+', '.join(ids)
            p={}
            for line in obj.seller_ids:
                products=self.env['product.supplierinfo'].search([
                    ('product_code'   , '=' , line.product_code),
                    ('product_code'   , '!=', False),
                    ('id'             , '!=', line.id),
                ])
                if len(products)>0:
                    for product in products:
                        if product.product_tmpl_id.active:
                            id=product.product_tmpl_id.id
                            p[id]=id
            ids=[]
            if len(p)>0:
                for id in p:
                    ids.append(str(id))
                doublon=u'Doublon Référence fournisseur : '+', '.join(ids)
            obj.is_doublon=doublon


    def _compute(self):
        for obj in self:
            is_stock_disponible_valorise = 0
            is_stock_prevu_valorise      = 0
            if obj.qty_available > 0:
                is_stock_disponible_valorise = obj.standard_price * obj.qty_available
            if obj.virtual_available > 0:
                is_stock_prevu_valorise = obj.standard_price * obj.virtual_available
            obj.is_stock_disponible_valorise = is_stock_disponible_valorise
            obj.is_stock_prevu_valorise      = is_stock_prevu_valorise


    def recalcul_prix_revient_action(self):
        cr,uid,context,su = self.env.args
        prod_obj = self.env['product.template']
        for obj in self:
            produire=False
            for route in obj.route_ids:
                _logger.info("recalcul_prix_revient_action : %s (id=%s : route=%s)"%(obj.display_name,obj.id, route.name))
                if route.name=="Produire":
                    produire=True
            if obj.is_recalcul_prix_revient:
                if produire:
                    res=obj.button_bom_cost()
                else:
                    SQL="""
                        SELECT pol.price_unit
                        FROM purchase_order po join purchase_order_line pol on po.id=pol.order_id
                                            join product_product pp on pol.product_id=pp.id
                                            join product_template pt on pt.id=pp.product_tmpl_id
                        WHERE pol.price_unit>0 and pt.id=%s and po.state in ('purchase')
                        ORDER BY pol.id desc 
                        limit 1
                    """
                    cr.execute(SQL,[obj.id])
                    for row in cr.fetchall():
                        obj.standard_price=row[0]


            _logger.info("recalcul_prix_revient_action : %s (id=%s : produire=%s) => %s"%(obj.display_name,obj.id, produire, obj.standard_price))


    @api.model
    def recalcul_prix_revient_ir_cron(self):
        products=self.env['product.template'].search([])
        nb = len(products)
        ct=1
        for product in products:
            product.recalcul_prix_revient_action()
            _logger.info("%s/%s recalcul_prix_revient_ir_cron : %s (id=%s) => %s"%(ct,nb,product.display_name,product.id,product.standard_price))
            ct+=1
        return True


    def ligne_commande_action(self):
        for obj in self:
            filtre=[
                ('product_tmpl_id', '=', obj.id),
            ]
            products=self.env['product.product'].search(filtre)
            ids=[]
            for product in products:
                ids.append(product.id)
            action = self.env["ir.actions.actions"]._for_xml_id("is_bsa14.is_purchase_order_line_acion")
            action['domain'] = [('product_id', 'in',ids)]
            return action


class product_product(models.Model):
    _inherit = 'product.product'

    is_production_count = fields.Integer('# Productions', compute='_compute_is_production_count', compute_sudo=False)
    is_pmp_odoo8        = fields.Float('PMP Odoo 8', digits=(14,4))


    def _compute_is_production_count(self):
        for product in self:
            product.is_production_count = self.env['mrp.production'].search_count([('product_id', '=', product.id)])


class ProductTemplateAttributeValue(models.Model):
    _inherit = "product.template.attribute.value"

    def _get_combination_name(self):
        """Permet de retourner les attribtus des variantes même si une seule variante"""
        res = ", ".join([ptav.name for ptav in self._without_no_variant_attributes()])
        return res

