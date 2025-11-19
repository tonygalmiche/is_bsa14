# -*- coding: utf-8 -*-
from itertools import product
from odoo import models,fields,api,tools
from datetime import datetime, timedelta
import time
import os


def datamax(sizex, sizey, y, x, txt):
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


class is_tracabilite_reception(models.Model):
    _name = 'is.tracabilite.reception'
    _description = "Traçabilité réception"
    _order = "create_date desc"
    
    name           = fields.Char('Numéro', required=True, readonly=True, default=" ")
    picking_id     = fields.Many2one('stock.picking', 'Réception', readonly=False)
    product_id     = fields.Many2one('product.template', 'Article', readonly=False)
    bl_fournisseur = fields.Char('Numéro du BL fournisseur', readonly=False)
    move_id        = fields.Many2one('stock.move', 'Mouvement de stock', readonly=False)
    quantity       = fields.Float('Quantité', readonly=False)
 

    @api.model
    def create(self, vals):
        self.update_product(vals)
        vals['name'] = self.env['ir.sequence'].next_by_code('is.tracabilite.reception')
        res = super(is_tracabilite_reception, self).create(vals)
        return res


    def write(self, vals):
        self.update_product(vals)
        res = super(is_tracabilite_reception, self).write(vals)
        return res


    def update_product(self, vals):
        if "move_id" in vals:
            obj = self.env['stock.move']
            doc = obj.browse(vals["move_id"])
            product_id=doc.product_id.product_tmpl_id.id
            vals.update({'product_id': product_id})
        return vals


    def imprimer_etiquette_direct(self):
        for obj in self:
            company = self.env.user.company_id
            if company.is_type_imprimante=='zebra':
                etiquette=obj.generer_etiquette_zpl()
            else:
                etiquette=obj.generer_etiquette()
            obj.imprimer_etiquette(etiquette)


    def zpl_text(self,x,y,size,txt):
        ZPL=''
        ZPL+='^FO%s,%s'%(x,y)   # Positionnement en x,y
        ZPL+='^CF0,%s'%size     # Taille des caractères
        ZPL+='^FD%s^FS \n'%txt  # Texte à imprimer
        return ZPL


    def generer_etiquette_zpl(self):
        for obj in self:
            ZPL=''
            ZPL+='^XA \n'                                     # Début de l'étiquette
            ZPL+='^CI28 \n'                                   # Encodage en UTF-8
            ZPL+='^PR3~SD25 \n'                               # PR4=Vitesse de 4 (sur 6) et SD30= Contraste à 30 => Pour imprimer sur du papier Plolypro avec un ruban transfert résine, il est nécessaire de mettre une valeur de chauffe (contraste) de la tête d impression entre 20 et 30 e
            ZPL+='^LH170,35 \n'                               # Décalage x,y depuis le point supérieur gauche
            ZPL+='^FO1,1 ^GB920,675,3,0,1^FS \n'              # Cadre de l'étiquette (Largeur, Hauteur, Epaisseur, Couleur, Arrondi) => 300pt = 2,54mm
   
   
            size=40; x=15
            y=40;  ZPL+=obj.zpl_text(x,y,size,'ARTICLE : %s'%obj.product_id.name)
            y+=50; ZPL+=obj.zpl_text(x,y,size,'FOURNISSEUR : %s'%obj.picking_id.partner_id.name)
            y+=50; ZPL+=obj.zpl_text(x,y,size,'REF INTERNE : %s'%(obj.product_id.default_code or ''))
            y+=50; ZPL+=obj.zpl_text(x,y,size,'RECEPTION : %s'%obj.picking_id.name)
            y+=50; ZPL+=obj.zpl_text(x,y,size,'BL FOURNISSEUR : %s'%obj.bl_fournisseur)
            y+=50; ZPL+=obj.zpl_text(x,y,size,'DATE : %s'%obj.move_id.create_date)[0:10]
            y+=50; ZPL+=obj.zpl_text(x,y,size,'LOT : %s'%obj.name)
            height=150;         ZPL+='^BY5,2,%s'%height         # Taille du code barre
            x=70; y=400;        ZPL+='^FO%s,%s'%(x,y)           # Positionnement en x, y
            codebar=obj.name;   ZPL+='^BC^FD%s^FS \n'%(codebar) # Code barre
            ZPL+='^XZ'                                          # Fin de l'étiquette
            return ZPL


    def generer_etiquette(self):
        for eti in self:
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

            txt=txt+datamax(x=15,y=220,sizex=2,sizey=2,txt="ARTICLE:")
            if eti.product_id:
                txt=txt+datamax(x=15,y=200,sizex=3,sizey=4,txt=eti.product_id.name) #.encode("utf-8"))

            if eti.product_id:
                txt=txt+datamax(x=190,y=220,sizex=2,sizey=2,txt="ID:"+str(eti.product_id.id))

            txt=txt+datamax(x=15,y=180,sizex=2,sizey=2,txt="FOURNISSEUR:")
            if eti.picking_id:
                txt=txt+datamax(x=15,y=160,sizex=4,sizey=4,txt=eti.picking_id.partner_id.name) #.encode("utf-8"))

            txt=txt+datamax(x=190,y=180,sizex=2,sizey=2,txt="REF INTERNE:")
            if eti.picking_id:
                txt=txt+datamax(x=190,y=160,sizex=3,sizey=4,txt=eti.product_id.default_code) 

            txt=txt+datamax(x=15,y=140,sizex=2,sizey=2,txt="RECEPTION:")
            if eti.picking_id:
                txt=txt+datamax(x=15,y=120,sizex=4,sizey=4,txt=eti.picking_id.name) #.encode("utf-8"))

            txt=txt+datamax(x=190,y=140,sizex=2,sizey=2,txt="BL FOURNISSEUR:")
            if eti.bl_fournisseur:
                txt=txt+datamax(x=190,y=120,sizex=4,sizey=4,txt=eti.bl_fournisseur) #.encode("utf-8"))

            txt=txt+datamax(x=15,y=100 ,sizex=2,sizey=2,txt="DATE:")
            if eti.move_id:
                txt=txt+datamax(x=15,y=80  ,sizex=4,sizey=4,txt=str(eti.move_id.create_date)[0:10])

            txt=txt+datamax(x=190,y=100 ,sizex=2,sizey=2,txt="LOT:")
            txt=txt+datamax(x=190,y=80  ,sizex=4,sizey=4,txt=eti.name) #.encode("utf-8"))

            txt=txt+"1E1406100060025B"+str(eti.name)+chr(10) # Code barre

            txt=txt+"^01"+chr(10)
            txt=txt+"Q0001"+chr(10)
            txt=txt+"E"+chr(10)
            return txt


    def imprimer_etiquette(self, etiquette):
        path="/tmp/etiquette.txt"
        err=""
        fichier = open(path, "w")
        if err=="":
            fichier.write(etiquette)
            fichier.close()
            user  = self.env['res.users'].browse(self._uid)
            imprimante = user.company_id.is_nom_imprimante or 'Datamax'
            cmd="lpr -h -P"+imprimante+" "+path
            os.system(cmd)


class is_tracabilite_livraison(models.Model):
    _name = 'is.tracabilite.livraison'
    _description = u"Traçabilité livraison"
    _order = "name"
    
    name                    = fields.Char('Numéro de série', required=True, readonly=True, default=" ")
    production_id           = fields.Many2one('mrp.production', 'OF', required=False)
    lot_fabrication         = fields.Integer('Lot de fabrication', default=1)
    product_id              = fields.Many2one('product.template', 'Article', readonly=False)
    fabrique                = fields.Datetime("Produit fabriqué le")
    consomme                = fields.Datetime("Semi-fini consommé le")
    operateur_ids           = fields.Many2many('hr.employee', 'is_tracabilite_livraison_operateur_rel', 'tracabilite_livraison_id', 'employee_id', 'Opérateurs Fabrication')
    sale_id                 = fields.Many2one('sale.order', 'Commande Client')
    move_id                 = fields.Many2one('stock.move', 'Ligne de livraison')
    picking_id              = fields.Many2one('stock.picking', 'Réception', readonly=False)
    quantity                = fields.Float('Quantité')
    livraison               = fields.Datetime("Produit livré le")
    operateur_livraison_ids = fields.Many2many('hr.employee', 'is_tracabilite_livraison_operateur_livraison_rel', 'tracabilite_livraison_id', 'employee_id', 'Opérateurs Livraison')
    etiquette_reception_id  = fields.One2many('is.tracabilite.reception.line', 'livraison_id', 'Etiquettes réception')
    etiquette_livraison_id  = fields.One2many('is.tracabilite.livraison.line', 'livraison_id', 'Etiquettes semi-fini')
    suivi_temps_ids         = fields.One2many('is.ordre.travail.line.temps.passe', 'tracabilite_livraison_id', 'Suivi du temps')
    temps_passe             = fields.Float("Temps passé (HH:MM)", compute="_compute_temps_passe", readonly=True, store=True)


    @api.depends("suivi_temps_ids","suivi_temps_ids.temps_passe")
    def _compute_temps_passe(self):
        for obj in self:
            print(obj.suivi_temps_ids)
            temps_passe = 0
            # domain=[
            #     ('tracabilite_livraison_id', '=', obj.id),
            # ]
            # lines=self.env['is.ordre.travail.line.temps.passe'].search(domain)
            for line in obj.suivi_temps_ids:
                temps_passe+=(line.temps_passe or 0)
            obj.temps_passe = temps_passe



    #num_serie               = fields.Char('N°série', store=True, readonly=True, compute='_compute_num_serie')
    

    # @api.depends('production_id','production_id.is_date_prevue','name')
    # def _compute_num_serie(self):
    #     for obj in self:
    #         date_client=''
    #         if obj.production_id.is_date_prevue:
    #             date_client = obj.production_id.is_date_prevue.strftime('%m%y') 
    #         num_serie =  "%s%s%s"%(obj.production_id.name,date_client,obj.name)
    #         obj.num_serie = num_serie
 

    def ajouter_etiquette_of(self, etiquette, production_id):
        """ Ajouter l'etiquette à la liste des etiquettes de l'OF correspondant """
        if production_id:
            production_obj = self.env['mrp.production']
            productions = production_obj.search([('id','=',production_id)])
            for production in productions:
                ids=[etiquette.id]
                for line in production.etiquette_ids:
                    ids.append(line.id)
                production.write({'etiquette_ids': [(6, 0, ids)]})
        return True
            
        
    @api.model
    def create(self, vals):
        self.update_product(vals)
        vals['name'] = self.env['ir.sequence'].next_by_code('is.tracabilite.livraison')
        res = super(is_tracabilite_livraison, self).create(vals)
        self.ajouter_etiquette_of(res, vals['production_id'])
        return res


    def write(self, vals):
        self.update_product(vals)
        res = super(is_tracabilite_livraison, self).write(vals)
        return res


    def update_product(self, vals):
        if "production_id" in vals:
            obj = self.env['mrp.production']
            doc = obj.browse(vals["production_id"])
            product_id=doc.product_id.product_tmpl_id.id
            vals.update({'product_id': product_id})
        return vals


    def imprimer_etiquette_livraison_direct(self):
        for obj in self:
            company = self.env.user.company_id
            if company.is_type_imprimante=='zebra':
                etiquettes=obj.generer_etiquette_zpl()
            else:
                etiquettes=obj.generer_etiquette_livraison()
            self.env['is.tracabilite.reception'].imprimer_etiquette(etiquettes)


    def generer_etiquette_zpl(self):
        o = self.env['is.tracabilite.reception']
        #TODO : Ajout d'une image en la convertissant ici => https://labelary.com/viewer.html
        path='/opt/addons/is_bsa14'
        if not os.path.isdir(path):
            path='/media/sf_dev_odoo/14.0/bsa/is_bsa14'
        file_path='%s/static/src/img/logo-bsa-tech.zpl'%path
        logo = open(file_path,'rb').read().decode("utf-8")
        file_path='%s/static/src/img/logo-ce.zpl'%path
        logo_ce = open(file_path,'rb').read().decode("utf-8")
        for obj in self:
            ZPL=''
            ZPL+='^XA \n'                                     # Début de l'étiquette
            ZPL+='^CI28 \n'                                   # Encodage en UTF-8
            ZPL+='^PR3~SD25 \n'                               # PR4=Vitesse de 4 (sur 6) et SD30= Contraste à 30 => Pour imprimer sur du papier Plolypro avec un ruban transfert résine, il est nécessaire de mettre une valeur de chauffe (contraste) de la tête d impression entre 20 et 30 e
            ZPL+='^LH170,35 \n'                               # Décalage x,y depuis le point supérieur gauche
            ZPL+='^FO1,1 ^GB920,675,3,0,1^FS \n'              # Cadre de l'étiquette (Largeur, Hauteur, Epaisseur, Couleur, Arrondi) => 300pt = 2,54mm
            size=40; x=15
            y=40;  ZPL+=o.zpl_text(x,y,size,'ARTICLE é€ : %s'%obj.product_id.name)
            y+=50; ZPL+=o.zpl_text(x,y,size,'REF : %s'%(obj.product_id.default_code or ''))
            #y+=50; ZPL+=o.zpl_text(x,y,size,'QT : %s'%(obj.lot_fabrication))
            y+=50; ZPL+=o.zpl_text(x,y,size,'DATE : %s'%str(obj.create_date)[0:10])
            #y+=50; ZPL+=o.zpl_text(x,y,size,'LOT : %s'%obj.name)
            y+=50; ZPL+=o.zpl_text(x,y,size,'OF : %s'%obj.production_id.name)
            y+=150; ZPL+=o.zpl_text(x,y,60,'N°Série : %s'%obj.name)

            ZPL+='^FO%s,%s'%(450,150)   # Positionnement en x,y du logo
            ZPL+=logo

            ZPL+='^FO%s,%s'%(770,500)   # Positionnement en x,y du logo_ce
            ZPL+=logo_ce

            height=150;         ZPL+='^BY5,2,%s'%height         # Taille du code barre
            x=70; y=450;        ZPL+='^FO%s,%s'%(x,y)           # Positionnement en x, y
            codebar=obj.name;   ZPL+='^BCN,150,N,N,N^FD%s^FS \n'%(codebar) # Code barre
            ZPL+='^XZ'                                          # Fin de l'étiquette
            return ZPL



    def generer_etiquette_livraison(self):
        for eti in self:
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
            txt=txt+datamax(x=15,y=220,sizex=2,sizey=2,txt="ARTICLE:")
            txt=txt+datamax(x=15,y=200,sizex=3,sizey=4,txt=eti.product_id.name) #.encode("utf-8"))
            txt=txt+datamax(x=15,y=180,sizex=2,sizey=2,txt="REF")
            default_code=eti.product_id.default_code or ''
            txt=txt+datamax(x=15,y=160,sizex=4,sizey=4,txt=default_code) #.encode("utf-8"))
            txt=txt+datamax(x=200,y=180,sizex=2,sizey=2,txt="QT:")
            txt=txt+datamax(x=200,y=160,sizex=3,sizey=4,txt=str(eti.lot_fabrication))
            txt=txt+datamax(x=15,y=140 ,sizex=2,sizey=2,txt="DATE:")
            #txt=txt+datamax(x=15,y=120  ,sizex=3,sizey=4,txt=str(eti.production_id.date_planned)[0:10])
            txt=txt+datamax(x=15,y=120  ,sizex=3,sizey=4,txt=str(eti.create_date)[0:10])

            txt=txt+datamax(x=120,y=140 ,sizex=2,sizey=2,txt="LOT:")
            txt=txt+datamax(x=120,y=120  ,sizex=3,sizey=4,txt=eti.name) #.encode("utf-8"))
            txt=txt+datamax(x=200,y=140,sizex=2,sizey=2,txt="OF:")
            txt=txt+datamax(x=200,y=120,sizex=3,sizey=4,txt=eti.production_id.name) #.encode("utf-8"))

            txt=txt+datamax(x=250,y=55,sizex=6,sizey=6,txt="BSA")

            t=str(eti.name)
            sizex="3"
            sizey="7"
            x="025"
            y="020"
            txt=txt+"1E1"+sizex+"0"+sizey+"10"+y+"0"+x+"B"+t+chr(10) # Code barre
            txt=txt+"^01"+chr(10)
            txt=txt+"Q0001"+chr(10)
            txt=txt+"E"+chr(10)
            return txt




    def get_picking_id(self, pick_ids):
        if pick_ids:
            return max(pick_ids)
        else:
            return False       


    def get_products_from_move_lines(self, picking):
        products = []
        if picking.move_lines:
            for move in picking.move_lines:
                if move.product_id.id in products:
                    continue
                else:
                    products.append(move.product_id.product_tmpl_id)
        return products


    def verifier_product_etiquette(self, etiquettes, products):
        if etiquettes:
            for etiquette in etiquettes:
                if etiquette.product_id.id in products:
                    continue
                else:
                    return False
        return True


    def terminer_suivi_temps_employe(self, employe_id, now=False):
        """
        Termine toutes les lignes de suivi du temps en cours pour un employé
        en mettant une heure de fin sur toutes les lignes sans heure de fin
        """
        if not now:
            now = fields.Datetime.now()
        
        # Rechercher toutes les lignes de suivi du temps de l'employé sans heure de fin
        domain = [
            ('employe_id', '=', employe_id),
            ('heure_fin', '=', False),
        ]
        lines_en_cours = self.env['is.ordre.travail.line.temps.passe'].search(domain)
        
        # Mettre une heure de fin sur toutes les lignes trouvées
        for line in lines_en_cours:
            line.write({'heure_fin': now})
        
        return True


    def demarrer_suivi_temps_action(self, employe_id=False):
        """
        Démarre le suivi du temps pour cette étiquette :
        - Recherche l'ordre de travail attaché à production_id
        - Trouve la première ligne de l'ordre de travail
        - Termine tous les suivis en cours de l'employé
        - Ajoute une ligne de suivi du temps avec la date de début à maintenant,
          l'étiquette indiquée et l'utilisateur connecté (ou l'employé passé en paramètre)
        """
        for obj in self:
            if not obj.production_id:
                raise Warning("Aucun ordre de production associé à cette étiquette")
            
            ordre_travail = obj.production_id.is_ordre_travail_id
            if not ordre_travail:
                raise Warning("Aucun ordre de travail associé à l'ordre de production %s" % obj.production_id.name)
            
            # Recherche de la première ligne (triée par sequence)
            lines = ordre_travail.line_ids.sorted(key=lambda l: l.sequence)
            if not lines:
                raise Warning("Aucune ligne trouvée dans l'ordre de travail %s" % ordre_travail.name)
            
            first_line = lines[0]
            
            # Récupération de l'employé
            if not employe_id:
                # Récupération de l'employé lié à l'utilisateur connecté
                employes = self.env['hr.employee'].search([("user_id", "=", self._uid)])
                if not employes:
                    raise Warning("Aucun employé trouvé pour l'utilisateur connecté")
                employe_id = employes[0].id
            
            # Terminer tous les suivis en cours de l'employé
            now = fields.Datetime.now()
            obj.terminer_suivi_temps_employe(employe_id, now)
            
            # Création de la ligne de suivi du temps
            vals = {
                "line_id": first_line.id,
                "employe_id": employe_id,
                "heure_debut": now,
                "tracabilite_livraison_id": obj.id,
            }
            self.env['is.ordre.travail.line.temps.passe'].create(vals)
            
        return []


class is_tracabilite_reception_line(models.Model):
    _name = 'is.tracabilite.reception.line'
    _description = "Traçabilité reception line"
    
    etiquette_id = fields.Many2one('is.tracabilite.reception', 'Etiquettes réception', required=True)
    quantity     = fields.Float('Quantité', required=True, default=1.0)
    livraison_id = fields.Many2one('is.tracabilite.livraison', 'Etiquette livraison')
    

class is_tracabilite_livraison_line(models.Model):
    _name = 'is.tracabilite.livraison.line'
    _description = "Traçabilité livraison line"
    
    etiquette_id = fields.Many2one('is.tracabilite.livraison', 'Etiquettes semi-fini', required=True)
    quantity     = fields.Float('Quantité', required=True, default=1.0)
    livraison_id = fields.Many2one('is.tracabilite.livraison', 'Etiquette livraison')
    




class is_suivi_tracabilite_reception(models.Model):
    _name='is.suivi.tracabilite.reception'
    _description='Suivi tracabilité reception'
    _order='id desc'
    _auto = False

    etiquette_reception_id = fields.Many2one('is.tracabilite.reception', 'Etiquette réception')
    picking_id             = fields.Many2one('stock.picking', 'Réception')
    product_id             = fields.Many2one('product.template', 'Article')
    bl_fournisseur         = fields.Char('Numéro du BL fournisseur')
    move_id                = fields.Many2one('stock.move', 'Mouvement de stock')
    qt_receptionnee        = fields.Float('Qt receptionnée')
    qt_consommee           = fields.Float('Qt consommée')
    qt_reste               = fields.Float('Qt reste')
    create_uid             = fields.Many2one('res.users', 'Créé par')
    create_date            = fields.Datetime('Date création')
    write_uid              = fields.Many2one('res.users', 'Modifié par')
    write_date             = fields.Datetime('Date modification')

    def init(self):
        cr=self._cr
        tools.drop_view_if_exists(cr, 'is_suivi_tracabilite_reception')
        cr.execute("""
            CREATE OR REPLACE view is_suivi_tracabilite_reception AS (
                select
                    tr.id,
                    tr.picking_id,
                    tr.product_id,
                    tr.bl_fournisseur,
                    tr.move_id,
                    tr.create_uid,
                    tr.create_date,
                    tr.write_uid,
                    tr.write_date,
                    tr.id etiquette_reception_id,
                    tr.quantity qt_receptionnee,
                    sum(trl.quantity) qt_consommee,
                    (tr.quantity-sum(trl.quantity)) qt_reste
                from is_tracabilite_reception tr join is_tracabilite_reception_line trl on tr.id=trl.etiquette_id
                group by tr.id, tr.quantity
            );
        """)




    def liste_livraisons_action(self):
        for obj in self: 
            lines = self.env['is.tracabilite.reception.line'].search([('etiquette_id','=',obj.id)])
            ids=[]
            for line in lines:
                ids.append(line.livraison_id.id)
            return {
                "name": "Livraisons "+obj.etiquette_reception_id.name,
                "view_mode": "tree,form",
                "res_model": "is.tracabilite.livraison",
                "domain": [
                    ("id" ,"in",ids),
                ],
                "type": "ir.actions.act_window",
            }

    def liste_etiquettes_action(self):
        for obj in self: 
            return {
                "name": "Consommtions "+obj.etiquette_reception_id.name,
                "view_mode": "tree,form",
                "res_model": "is.tracabilite.reception.line",
                "domain": [
                    ("etiquette_id" ,"=",obj.id),
                ],
                "type": "ir.actions.act_window",
            }

