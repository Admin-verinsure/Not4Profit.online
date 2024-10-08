# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import controllers
from . import wizard

from odoo.addons.payment import setup_provider, reset_payment_provider

def post_init_hook(env):
    setup_provider(env, 'windcave')
    

def uninstall_hook(env):
    reset_payment_provider(env, 'windcave')
