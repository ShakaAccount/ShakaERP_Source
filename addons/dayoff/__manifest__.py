{
    'name': 'Leave Request Workflow',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Leave requests with submit/approve/reject workflow and audit log',
    'depends': ['base', 'mail'],
    'data': [
        'security/leave_security.xml',
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
