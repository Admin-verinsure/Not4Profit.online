from odoo import http
from odoo.http import request

class LdapResetPassword(http.Controller):

    @http.route('/ldap/reset_password', type='http', auth='public', website=True)
    def reset_password_form(self, **kw):
        # Fetch all Rotary clubs from res.partner
        clubs = request.env['res.partner'].search([('is_rotary_club', '=', True)])

        # Define the available program types
        program_type = [" ", "None", "Rotary", "Rotaract", "Interact", "Rota-Kids",]

        return request.render("ldap_module.ldap_reset_password.fields", {
            'clubs': clubs,
            'program_type': program_type
        })
