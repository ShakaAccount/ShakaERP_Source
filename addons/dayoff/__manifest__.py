{
    'name': 'Leave Request Workflow',
    'version': '19.0.1.0.0',
    'category': 'Shaka ERP',
    'summary': 'Leave requests with submit/approve/reject workflow and audit log',
    'description': """
Leave Request Workflow
======================
Lightweight leave requests (independent of ``hr_holidays``) with a
submit / approve / reject workflow and a chatter-based audit log.
""",
    'author': 'ShakaERP',
    'maintainer': 'ShakaERP',
    'website': 'https://shakasystem.com',
    'license': 'LGPL-3',
    'icon': '/dayoff/static/description/icon.svg',
    'depends': ['base', 'mail'],
    'data': [
        'security/leave_security.xml',
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
