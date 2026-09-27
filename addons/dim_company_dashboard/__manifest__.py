{
    'name': 'Company Dimension (SQL Server BI)',
    'version': '19.0.1.0.0',
    'category': 'Shaka ERP',
    'summary': 'Read-only view of Shaka_DW.BI.DimCompany',
    'description': """
Company Dimension
=================
Read-only ``dim.company`` model over the Shaka DW company dimension
(``BI.DimCompany``), exposing the company hierarchy levels as a list view.
""",
    'author': 'ShakaERP',
    'maintainer': 'ShakaERP',
    'website': 'https://shakasystem.com',
    'license': 'LGPL-3',
    'icon': '/dim_company_dashboard/static/description/icon.svg',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
