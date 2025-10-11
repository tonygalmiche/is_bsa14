odoo.define('is_bsa14.message_enhancement', function (require) {
"use strict";


var core = require('web.core');
var session = require('web.session');
var rpc = require('web.rpc');

// Fonction pour améliorer l'affichage des messages
function enhanceMessageDisplay() {
    // Attendre un peu que les messages soient chargés
    setTimeout(function() {
        var $messages = $('.o_Message[data-message-local-id]');
        
        $messages.each(function(index) {
            var $message = $(this);
            
            // Éviter de traiter le même élément plusieurs fois
            if ($message.hasClass('bsa-enhanced')) {
                return;
            }
            $message.addClass('bsa-enhanced');
            
            // Récupérer l'ID du message
            var messageLocalId = $message.attr('data-message-local-id');
            
            // Chercher l'icône d'enveloppe dans ce message
            var $icon = $message.find('.o_Message_notificationIconClickable');
            if ($icon.length > 0) {
                // Extraire l'ID numérique du message
                var messageId = messageLocalId.replace('mail.message_', '');
                
                // Appel AJAX pour récupérer les informations du message
                getMessageRecipients(messageId, $icon);
            }
        });
    }, 500);
}

function getMessageRecipients(messageId, $icon) {
    rpc.query({
        model: 'mail.message',
        method: 'read',
        args: [[parseInt(messageId)], ['partner_ids', 'email_from', 'is_destinataires']],
    }).then(function(result) {
        if (result && result.length > 0) {
            var messageData = result[0];
            var partnerIds = messageData.partner_ids;
            var emailFrom = messageData.email_from;
            var isDestinataires = messageData.is_destinataires;
            
            // Afficher email_from et is_destinataires directement si disponibles
            if (emailFrom || isDestinataires) {
                displayMessageInfo($icon, emailFrom, isDestinataires);
            }
            
            // Continuer avec l'affichage des destinataires comme avant
            if (partnerIds && partnerIds.length > 0) {
                getPartnersInfo(partnerIds, $icon);
            }
        }
    }).catch(function(error) {
        // Erreur silencieuse
    });
}

function displayMessageInfo($icon, emailFrom, isDestinataires) {
    // Éviter de dupliquer l'information
    if ($icon.siblings('.o_Message_infoList').length > 0 || $icon.closest('.o_Message').find('.o_Message_infoList').length > 0) {
        return;
    }
    
    var infoHtml = [];
    
    // Fonction pour échapper le HTML
    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Ajouter email_from si disponible
    if (emailFrom) {
        infoHtml.push('<div class="message-email-from"><strong>De:</strong> <span style="color: #666;">' + escapeHtml(emailFrom) + '</span></div>');
    }
    
    // Ajouter is_destinataires si disponible
    if (isDestinataires) {
        // Remplacer les \n par <br> pour l'affichage HTML
        var destinatairesFormatted = escapeHtml(isDestinataires).replace(/\n/g, '<br>');
        infoHtml.push('<div class="message-destinataires"><strong>Destinataires:</strong> <span style="color: #28a745;">' + destinatairesFormatted + '</span></div>');
    }
    
    if (infoHtml.length > 0) {
        var $infoDiv = $('<div class="o_Message_infoList" style="font-size: 0.85em; margin-top: 5px; margin-left: 5px;">' + 
                        infoHtml.join('') + 
                        '</div>');
        
        // Ajouter après l'en-tête du message
        var $header = $icon.closest('.o_Message_header');
        if ($header.length > 0) {
            $header.after($infoDiv);
        }
    }
}

function getPartnersInfo(partnerIds, $icon) {
    rpc.query({
        model: 'res.partner',
        method: 'read',
        args: [partnerIds, ['name', 'email']],
    }).then(function(partners) {
        if (partners && partners.length > 0) {
            displayRecipients(partners, $icon);
        }
    }).catch(function(error) {
        // Erreur silencieuse
    });
}

function displayRecipients(partners, $icon) {
    // Vérifier qu'on n'a pas déjà ajouté les destinataires
    if ($icon.siblings('.o_Message_recipientsList').length > 0) {
        return;
    }
    
    var recipientsHtml = [];
    partners.forEach(function(partner) {
        var name = partner.name || 'Sans nom';
        var email = partner.email || '';
        
        if (email) {
            recipientsHtml.push('<strong>' + name + '</strong> (<span class="recipient-email">' + email + '</span>)');
        } else {
            recipientsHtml.push('<strong>' + name + '</strong> (<span class="no-email">Pas d\'email</span>)');
        }
    });
    
    
    
    // Ajouter les destinataires après l'icône d'enveloppe
    // if (recipientsHtml.length > 0) {
    //     var recipientsText = recipientsHtml.join(', ');
        
    //     var $recipientsList = $('<span class="o_Message_recipientsList">' + 
    //                            '<strong> → </strong>' + recipientsText + 
    //                            '</span>');
    //     $icon.after($recipientsList);
    // }
}

// Exécuter au chargement de la page
$(document).ready(function() {
    enhanceMessageDisplay();
    
    // Observer les changements pour les nouveaux messages
    var observer = new MutationObserver(function(mutations) {
        var shouldEnhance = false;
        mutations.forEach(function(mutation) {
            if (mutation.addedNodes.length > 0) {
                $(mutation.addedNodes).each(function() {
                    if ($(this).find('.o_Message').length > 0 || $(this).hasClass('o_Message')) {
                        shouldEnhance = true;
                        return false;
                    }
                });
            }
        });
        
        if (shouldEnhance) {
            setTimeout(function() {
                enhanceMessageDisplay();
            }, 200);
        }
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
});


});