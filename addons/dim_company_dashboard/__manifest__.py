{
    'name': 'Company Dimension (SQL Server BI)',
    'version': '19.0.1.0.0',
    'category': 'Reporting',
    'summary': 'Read-only view of Shaka_DW.BI.DimCompany',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    'installable': True,
    'application': False,
}
