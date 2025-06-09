{
    'name': 'LDAP Reset Password',
    'version': '18.0.1.0.0',
    'summary': 'Add LDAP Reset Password functionality',
    'description': 'A module to allow a user to reset their password in LDAP from the reset password form.',
    'author': 'Verinsure',
    'depends': ['auth_ldap','base', 'membership', 'rotary_project_map'],
    'data': [
        'reset_ldap_password.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}

