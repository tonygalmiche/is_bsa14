# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
import re
import email
from email.header import decode_header
#import html2text


def decode(value):
    """Decode email header value"""
    if not value:
        return value
    decoded = decode_header(value)
    if decoded and decoded[0][0]:
        return decoded[0][0] if isinstance(decoded[0][0], str) else decoded[0][0].decode(decoded[0][1] or 'utf-8', errors='replace')
    return value


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _message_get_default_recipients(self):
        """
        Surcharge pour ne retourner aucun destinataire par défaut
        Cela évite complètement l'envoi automatique d'emails
        """
        # Ne jamais retourner de destinataires par défaut
        result = {}
        for record in self:
            result[record.id] = {
                'partner_ids': [],
                'reason': _('No automatic email sending')
            }
        
        return result

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        """
        Surcharge pour éviter l'envoi automatique d'emails lors des changements d'état
        """
        import traceback
        
        # Vérifier si l'appel vient du wizard mail_compose_message
        is_from_wizard = False
        for line in traceback.format_stack():
            if 'mail_compose_message.py' in line and 'send_mail' in line:
                is_from_wizard = True
                break
        
        # Si l'appel vient du wizard ET que c'est un stock.picking, vérifier le contexte
        if is_from_wizard and self._name == 'stock.picking':
            print(f"\n=== INTERCEPTION WIZARD POUR STOCK.PICKING ===")
            print(f"Picking ID: {self.ids}")
            print(f"Partner_ids originaux: {kwargs.get('partner_ids')}")
            
            # Vérifier le contexte pour voir si c'est un envoi automatique ou manuel
            context_mail_post_autofollow = self._context.get('mail_post_autofollow', False)
            
            if context_mail_post_autofollow:
                print(f"DEBUG: Envoi automatique détecté - suppression des destinataires")
                kwargs['partner_ids'] = []
            else:
                print(f"DEBUG: Envoi manuel détecté - conservation des destinataires")
            
            print(f"===============================================\n")
        
        # Si pas de destinataires explicites, ne pas envoyer d'email
        elif not kwargs.get('partner_ids') and not kwargs.get('email_to'):
            kwargs['partner_ids'] = []
        
        return super(MailThread, self).message_post(**kwargs)






    # def _message_extract_payload(self, message, save_original=False):
    #     """Extract body as HTML and attachments from the mail message"""
    #     attachments = []
    #     body = u''
    #     if save_original:
    #         attachments.append(('original_email.eml', message.as_string()))

    #     # Be careful, content-type may contain tricky content like in the
    #     # following example so test the MIME type with startswith()
    #     #
    #     # Content-Type: multipart/related;
    #     #   boundary="_004_3f1e4da175f349248b8d43cdeb9866f1AMSPR06MB343eurprd06pro_";
    #     #   type="text/html"
    #     if not message.is_multipart() or message.get('content-type', '').startswith("text/"):
    #         encoding = message.get_content_charset()
    #         body = message.get_payload(decode=True)
    #         body = tools.ustr(body, encoding, errors='replace')
    #         if message.get_content_type() == 'text/plain':
    #             # text/plain -> <pre/>
    #             body = tools.append_content_to_html(u'', body, preserve=True)
    #     else:
    #         alternative = False
    #         mixed = False
    #         html = u''
    #         for part in message.walk():
    #             if part.get_content_type() == 'multipart/alternative':
    #                 alternative = True
    #             if part.get_content_type() == 'multipart/mixed':
    #                 mixed = True
    #             if part.get_content_maintype() == 'multipart':
    #                 continue  # skip container
    #             # part.get_filename returns decoded value if able to decode, coded otherwise.
    #             # original get_filename is not able to decode iso-8859-1 (for instance).
    #             # therefore, iso encoded attachements are not able to be decoded properly with get_filename
    #             # code here partially copy the original get_filename method, but handle more encoding
    #             filename=part.get_param('filename', None, 'content-disposition')
    #             if not filename:
    #                 filename=part.get_param('name', None)
    #             if filename:
    #                 if isinstance(filename, tuple):
    #                     # RFC2231
    #                     filename=email.utils.collapse_rfc2231_value(filename).strip()
    #                 else:
    #                     filename=decode(filename)
    #             encoding = part.get_content_charset()  # None if attachment


    #             #TODO : J'ai surchargé cette méthode uniquement pour pouvoir définir un format par défaut pour les mails veant d'Excel sans encodage
    #             if not encoding:
    #                 encoding='windows-1252'


    #             # 1) Explicit Attachments -> attachments
    #             if filename or part.get('content-disposition', '').strip().startswith('attachment'):
    #                 attachments.append((filename or 'attachment', part.get_payload(decode=True)))
    #                 continue
    #             # 2) text/plain -> <pre/>
    #             if part.get_content_type() == 'text/plain' and (not alternative or not body):
    #                 body = tools.append_content_to_html(body, tools.ustr(part.get_payload(decode=True),
    #                                                                      encoding, errors='replace'), preserve=True)
    #             # 3) text/html -> raw
    #             elif part.get_content_type() == 'text/html':
    #                 # mutlipart/alternative have one text and a html part, keep only the second
    #                 # mixed allows several html parts, append html content
    #                 append_content = not alternative or (html and mixed)
    #                 html = tools.ustr(part.get_payload(decode=True), encoding, errors='replace')
    #                 if not append_content:
    #                     body = html
    #                 else:
    #                     body = tools.append_content_to_html(body, html, plaintext=False)
    #             # 4) Anything else -> attachment
    #             else:
    #                 attachments.append((filename or 'attachment', part.get_payload(decode=True)))
    #     return body, attachments
