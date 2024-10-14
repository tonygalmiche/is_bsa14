# -*- coding: utf-8 -*-
from odoo import models,fields,api
import datetime
#from odoo.exceptions import Warning
from odoo.exceptions import AccessError, UserError, ValidationError
import unicodedata
import base64


def s(txt,lg):
    #if type(txt)!=unicode:
    #    txt = unicode(txt,'utf-8')
    txt = txt or ''
    txt = unicodedata.normalize('NFD', txt).encode('ascii', 'ignore').decode()
    txt = (txt+'                                                             ')[:lg]
    return txt


class is_export_compta(models.Model):
    _name='is.export.compta'
    _description='is.export.compta'
    _order='name desc'

    name               = fields.Char("N°Folio"      , readonly=True)
    type_interface     = fields.Selection([('ventes', 'Ventes'),('achats', 'Achats')], "Interface", required=True, default="ventes")
    format_export      = fields.Selection([('cegid' , 'CEGID'),('ledonia', 'Cabinet LEDONIA EXPERTISE')], "Format export", required=True, default="ledonia")
    date_debut         = fields.Date("Date de début")
    date_fin           = fields.Date("Date de fin")
    num_debut          = fields.Char("N° facture début")
    num_fin            = fields.Char("N° facture fin")
    ligne_ids          = fields.One2many('is.export.compta.ligne', 'export_compta_id', 'Lignes')
    file_ids           = fields.Many2many('ir.attachment', 'is_export_compta_attachment_rel', 'export_id', 'attachment_id', 'Pièces jointes')


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('is.export.compta')
        res = super(is_export_compta, self).create(vals)
        return res


    def action_export_compta(self):
        cr=self._cr
        for obj in self:
            obj.ligne_ids.unlink()
            if obj.type_interface=='ventes':
                type_facture=['out_invoice', 'out_refund']
                journal='VE'
            else:
                type_facture=['in_invoice', 'in_refund']
                journal='AC'
            filter=[
                ('state'    , 'in' , ['posted']),
                ('move_type', 'in' , type_facture)
            ]
            if obj.date_debut:
                filter.append(('invoice_date', '>=', obj.date_debut))
            if obj.date_fin:
                filter.append(('invoice_date', '<=', obj.date_fin))
            if obj.num_debut:
                filter.append(('name', '>=', obj.num_debut))
            if obj.num_fin:
                filter.append(('name', '<=', obj.num_fin))
            invoices = self.env['account.move'].search(filter, order="invoice_date,id")
            if len(invoices)==0:
                raise ValidationError('Aucune facture à traiter')
            for invoice in invoices:
                sql="""
                    SELECT  
                        ai.invoice_date,
                        aa.code, 
                        ai.name, 
                        rp.name, 
                        ai.move_type, 
                        rp.is_code_client,
                        sum(aml.debit), 
                        sum(aml.credit),
                        rp.id partner_id,
                        ai.id
                    FROM account_move_line aml inner join account_move ai      on aml.move_id=ai.id
                                               inner join account_account aa   on aml.account_id=aa.id
                                               inner join res_partner rp       on ai.partner_id=rp.id
                    WHERE ai.id=%s
                    GROUP BY ai.invoice_date, ai.name, rp.id, rp.name, aa.code, ai.move_type, rp.is_code_client, ai.invoice_date_due, ai.id
                    ORDER BY ai.invoice_date, ai.name, rp.id, rp.name, aa.code, ai.move_type, rp.is_code_client, ai.invoice_date_due, ai.id
                """
                cr.execute(sql,[invoice.id])
                for row in cr.fetchall():
                    compte=str(row[1] or '')
                    if obj.type_interface=='ventes' and compte=='411100':
                        compte=str(row[5] or '')
                    vals={
                        'export_compta_id'  : obj.id,
                        'date_facture'      : row[0],
                        'journal'           : journal,
                        'compte'            : compte,
                        'libelle'           : row[3],
                        'debit'             : row[6],
                        'credit'            : row[7],
                        'devise'            : 'E',
                        'piece'             : row[2],
                        'commentaire'       : False,
                        'partner_id'        : row[8],
                        'invoice_id'        : row[9],
                    }
                    self.env['is.export.compta.ligne'].create(vals)
            if obj.format_export=='cegid':
                self.generer_fichier_cegid()
            else:
                self.generer_fichier_ledonia()


    def generer_fichier_cegid(self):
        for obj in self:
            model='is.export.compta'
            attachments = self.env['ir.attachment'].search([('res_model','=',model),('res_id','=',obj.id)])
            attachments.unlink()
            name='export-compta.txt'
            dest     = '/tmp/'+name
            f = open(dest,'w')
            for row in obj.ligne_ids:
                compte=str(row.compte)
                if compte=='None':
                    compte=''
                debit=row.debit
                credit=row.credit
                montant=credit-debit
                if montant>0.0:
                    sens='C'
                else:
                    montant=-montant
                    sens='D'
                montant=('000000000000'+str(int(round(100*montant))))[-12:]
                date_facture=row.date_facture
                #date_facture=datetime.datetime.strptime(date_facture, '%Y-%m-%d')
                date_facture=date_facture.strftime('%d%m%y')
                libelle=s(row.libelle,20)
                piece=(row.piece[-8:]+u'        ')[0:8]
                f.write('M')
                f.write((compte+'00000000')[0:8])
                f.write(row.journal)
                f.write('000')
                f.write(date_facture)
                f.write('F')
                f.write(libelle)
                f.write(sens)
                f.write('+')
                f.write(montant)
                f.write('        ')
                f.write('000000')
                f.write('     ')
                f.write(piece)
                f.write('                 ')
                f.write(piece)
                f.write('EURVE    ')
                f.write(libelle)
                f.write('\r\n')
            f.close()
            r = open(dest,'rb').read()
            r = base64.b64encode(r)
            vals = {
                'name':        name,
                #'datas_fname': name,
                'type':        'binary',
                'res_model':   model,
                'res_id':      obj.id,
                'datas':       r,
            }
            attachment = self.env['ir.attachment'].create(vals)
            obj.file_ids=[(6,0,[attachment.id])]


    def generer_fichier_ledonia(self):
        for obj in self:
            name='export-compta.csv'
            model='is.export.compta'
            attachments = self.env['ir.attachment'].search([('res_model','=',model),('res_id','=',obj.id),('name','=',name)])
            attachments.unlink()
            dest     = '/tmp/'+name
            f = open(dest,'w')

            f.write("ligne\tjournal_code\tecriture_num\tecriture_date\tcompte_num\tcomp_aux_num\tpiece_ref\tpiece_date\tecriture_lib\tdebit\tcredit\r\n")
            ligne=1
            for row in obj.ligne_ids:
                date_facture = row.date_facture
                #date_facture = datetime.datetime.strptime(date_facture, '%Y-%m-%d')
                date_facture=date_facture.strftime('%Y%m%d')
                f.write(str(ligne)+'\t')
                f.write(row.journal+'\t')
                f.write(row.piece+'\t')
                f.write(date_facture+'\t')
                f.write(row.compte+'\t')
                f.write((row.partner_id.is_code_client or '')+'\t')
                f.write(row.piece+'\t')
                f.write(date_facture+'\t')
                f.write(row.libelle+'\t')
                f.write(str(row.debit).replace('.','.')+'\t')
                f.write(str(row.credit).replace('.','.')+'\t')
                f.write('\r\n')
                ligne+=1
            f.close()
            r = open(dest,'rb').read()
            r = base64.b64encode(r)


            vals = {
                'name':        name,
                #'datas_fname': name,
                'type':        'binary',
                'res_model':   model,
                'res_id':      obj.id,
                'datas':       r,
            }
            attachment = self.env['ir.attachment'].create(vals)
            obj.file_ids=[(6,0,[attachment.id])]


class is_export_compta_ligne(models.Model):
    _name = 'is.export.compta.ligne'
    _description = u"Lignes d'export en compta"
    _order='date_facture'

    export_compta_id = fields.Many2one('is.export.compta', 'Export Compta', required=True)
    date_facture     = fields.Date("Date")
    journal          = fields.Char("Journal")
    compte           = fields.Char("N°Compte")
    piece            = fields.Char("Pièce")
    libelle          = fields.Char("Libellé")
    debit            = fields.Float("Débit")
    credit           = fields.Float("Crédit")
    devise           = fields.Char("Devise")
    commentaire      = fields.Char("Commentaire")
    partner_id       = fields.Many2one('res.partner', 'Partenaire')
    invoice_id       = fields.Many2one('account.move', 'Facture')

    _defaults = {
        'journal': 'VTE',
        'devise' : 'E',
    }







