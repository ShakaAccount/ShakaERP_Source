from odoo import api, fields, models


def _source_relation(env, candidates):
    env.cr.execute(
        """SELECT n.nspname, c.relname
           FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
          WHERE c.relkind IN ('r', 'v', 'f', 'm', 'p')
            AND (n.nspname, c.relname) IN %s""",
        [tuple(candidates)],
    )
    found = {(row[0], row[1]) for row in env.cr.fetchall()}
    for candidate in candidates:
        if candidate in found:
            return candidate
    return None


def _connector_source(env, remote_table, fallback_names):
    """Resolve the public alias created by raes_dw_connector."""
    cr = env.cr
    names = []
    cr.execute("""SELECT local_view_name FROM raes_dw_table_map
                  WHERE lower(remote_table) = lower(%s)
                  ORDER BY id""", [remote_table])
    names.extend(row[0] for row in cr.fetchall())
    names.extend(fallback_names)
    cr.execute("""SELECT c.relname FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                  WHERE n.nspname = 'public' AND c.relname = ANY(%s)
                    AND c.relkind IN ('v', 'r', 'f', 'm', 'p')""", [names])
    found = {row[0] for row in cr.fetchall()}
    for name in names:
        if name in found:
            cr.execute("""SELECT column_name FROM information_schema.columns
                          WHERE table_schema = 'public' AND table_name = %s""", [name])
            return name, {row[0].lower() for row in cr.fetchall()}
    return None, set()


def _column(source, columns, candidates, sql_type):
    for candidate in candidates:
        if candidate.lower() in columns:
            return f'{source}.{candidate.lower()}'
    return f'NULL::{sql_type}'


def _create_fact_views(env):
    cr = env.cr
    receipt, receipt_cols = _connector_source(
        env, 'FactReceipt', ['raes_factreceipt', 'raes_fact_receipt'])
    sales, sales_cols = _connector_source(
        env, 'FactSales', ['raes_factsales', 'raes_fact_sales'])
    ledger, ledger_cols = _connector_source(
        env, 'DimDetailedLedger', ['raes_dimdetailedledger'])
    cr.execute('DROP VIEW IF EXISTS public.sales_analysis_receipt CASCADE')
    cr.execute('DROP VIEW IF EXISTS public.sales_analysis_sale CASCADE')
    if receipt:
        cr.execute(f'''CREATE VIEW public.sales_analysis_receipt AS
            SELECT {_column(receipt, receipt_cols, ['id'], 'integer')}::integer AS id,
                   {_column(receipt, receipt_cols, ['receiptitemid', 'receiptid', 'receiptno', 'number'], 'text')}::text AS receipt_item_id,
                   COALESCE(NULLIF({_column(receipt, receipt_cols, ['receiptitemid', 'receiptid', 'receiptno', 'number'], 'text')}::text, ''), 'رسید بدون شماره')
                   || ' | ' || to_char(COALESCE({_column(receipt, receipt_cols, ['amount', 'sumamount'], 'double precision')}::double precision, 0), 'FM999,999,999,999,999')
                   || ' ریال' AS receipt_preview,
                   {_column(receipt, receipt_cols, ['dateid', 'date_id'], 'integer')}::integer AS date_id,
                   {_column(receipt, receipt_cols, ['amount', 'sumamount'], 'double precision')}::double precision AS amount,
                   {_column(receipt, receipt_cols, ['branchid', 'branch_id'], 'integer')}::integer AS branch_id,
                   {_column(receipt, receipt_cols, ['detailedledgerid', 'detailed_ledger_id'], 'integer')}::integer AS detailed_ledger_id,
                   {_column(receipt, receipt_cols, ['detailedledgerid', 'recepientdlid'], 'integer')}::integer AS customer_id,
                   {_column(receipt, receipt_cols, ['description', 'descriptions'], 'text')}::text AS description,
                   {_column(receipt, receipt_cols, ['companyid', 'company_id'], 'integer')}::integer AS company_id,
                   {_column(receipt, receipt_cols, ['datasourceid', 'data_source_id'], 'integer')}::integer AS data_source_id
              FROM public.{receipt}''')
    else:
        cr.execute('''CREATE VIEW public.sales_analysis_receipt AS
            SELECT NULL::integer AS id, NULL::text AS receipt_item_id,
                   NULL::text AS receipt_preview,
                   NULL::integer AS date_id, NULL::double precision AS amount,
                   NULL::integer AS branch_id, NULL::integer AS detailed_ledger_id,
                   NULL::integer AS customer_id,
                   NULL::text AS description, NULL::integer AS company_id,
                   NULL::integer AS data_source_id WHERE false''')
    if sales:
        cr.execute(f'''CREATE VIEW public.sales_analysis_sale AS
            SELECT {_column(sales, sales_cols, ['id'], 'integer')}::integer AS id,
                   {_column(sales, sales_cols, ['salesid', 'saleid'], 'text')}::text AS sales_id,
                   {_column(sales, sales_cols, ['saleinvoicenumber', 'invoicenumber', 'invoiceno', 'number'], 'text')}::text AS invoice_number,
                   COALESCE(NULLIF({_column(sales, sales_cols, ['saleinvoicenumber', 'invoicenumber', 'invoiceno', 'number'], 'text')}::text, ''), 'فاکتور بدون شماره')
                   || ' | ' || to_char(COALESCE({_column(sales, sales_cols, ['sumfinal', 'amount', 'totalamount'], 'double precision')}::double precision, 0), 'FM999,999,999,999,999')
                   || ' ریال' AS invoice_preview,
                   {_column(sales, sales_cols, ['dateid', 'date_id'], 'integer')}::integer AS date_id,
                   {_column(sales, sales_cols, ['partyid', 'customerid', 'customer_id'], 'integer')}::integer AS customer_id,
                   {_column(sales, sales_cols, ['sumfinal', 'amount', 'totalamount'], 'double precision')}::double precision AS sum_final,
                   {_column(sales, sales_cols, ['remaining', 'remainamount'], 'double precision')}::double precision AS remaining,
                   {_column(sales, sales_cols, ['cashreceipt', 'cashamount'], 'double precision')}::double precision AS cash_receipt,
                   {_column(sales, sales_cols, ['receiptpos', 'posamount'], 'double precision')}::double precision AS receipt_pos,
                   {_column(sales, sales_cols, ['receiptonline', 'onlineamount'], 'double precision')}::double precision AS receipt_online,
                   {_column(sales, sales_cols, ['description', 'descriptions'], 'text')}::text AS description,
                   {_column(sales, sales_cols, ['branchid', 'branch_id'], 'integer')}::integer AS branch_id
              FROM public.{sales}''')
    else:
        cr.execute('''CREATE VIEW public.sales_analysis_sale AS
            SELECT NULL::integer AS id, NULL::text AS sales_id,
                   NULL::text AS invoice_number, NULL::text AS invoice_preview,
                   NULL::integer AS date_id,
                   NULL::integer AS customer_id, NULL::double precision AS sum_final,
                   NULL::double precision AS remaining, NULL::double precision AS cash_receipt,
                   NULL::double precision AS receipt_pos, NULL::double precision AS receipt_online,
                   NULL::text AS description, NULL::integer AS branch_id WHERE false''')

    cr.execute('DROP VIEW IF EXISTS public.sales_analysis_customer CASCADE')
    if ledger:
        cr.execute(f'''CREATE VIEW public.sales_analysis_customer AS
            SELECT {_column(ledger, ledger_cols, ['detailedledgerid', 'id'], 'integer')}::integer AS id,
                   {_column(ledger, ledger_cols, ['title', 'codetitle', 'code'], 'text')}::text AS name,
                   {_column(ledger, ledger_cols, ['code'], 'text')}::text AS code
              FROM public.{ledger}''')
    else:
        cr.execute('''CREATE VIEW public.sales_analysis_customer AS
            SELECT NULL::integer AS id, NULL::text AS name, NULL::text AS code WHERE false''')


class SalesAnalysisReceipt(models.Model):
    _name = 'sales.analysis.receipt'
    _description = 'FactReceipt (Read Only)'
    _auto = False
    _log_access = False
    _rec_name = 'receipt_preview'
    _order = 'date_id desc, id desc'

    receipt_item_id = fields.Char(string='شناسه رسید', readonly=True)
    receipt_preview = fields.Char(string='پیش‌نمایش رسید', readonly=True)
    date_id = fields.Integer(string='شناسه تاریخ', readonly=True)
    amount = fields.Float(string='مبلغ رسید', readonly=True)
    branch_id = fields.Integer(string='شناسه شعبه', readonly=True)
    detailed_ledger_id = fields.Integer(string='دفتر معین', readonly=True)
    description = fields.Text(string='توضیحات', readonly=True)
    company_id = fields.Integer(string='شرکت', readonly=True)
    data_source_id = fields.Integer(string='منبع داده', readonly=True)

    customer_id = fields.Many2one('sales.analysis.customer', string='مشتری', readonly=True)

    @api.depends('receipt_item_id', 'amount', 'date_id', 'description')
    def _compute_display_name(self):
        for record in self:
            number = record.receipt_item_id or '-'
            amount = f'{record.amount:,.0f}' if record.amount is not False else '0'
            record.display_name = f'{number} | {amount} | Date {record.date_id or "-"}'

    def init(self):
        _create_fact_views(self.env)
        return
        cr = self.env.cr
        source = _source_relation(self.env, [
            ('public', 'raes_fact_receipt'),
            ('public', 'fact_receipt'),
            ('fdw_raes', 'FactReceipt'),
        ])
        cr.execute('DROP VIEW IF EXISTS public.sales_analysis_receipt CASCADE')
        if source:
            schema, table = source
            q = f'"{schema}"."{table}"'
            cr.execute(f'''CREATE VIEW public.sales_analysis_receipt AS
                SELECT COALESCE("ID", 0)::integer AS id,
                       "ReceiptItemID"::text AS receipt_item_id,
                       "DateID"::integer AS date_id,
                       "Amount"::double precision AS amount,
                       "BranchID"::integer AS branch_id,
                       "DetailedLedgerID"::integer AS detailed_ledger_id,
                       "Description"::text AS description,
                       "CompanyID"::integer AS company_id,
                       "DataSourceID"::integer AS data_source_id
                  FROM {q}''')
        else:
            cr.execute('''CREATE VIEW public.sales_analysis_receipt AS
                SELECT NULL::integer AS id, NULL::text AS receipt_item_id,
                       NULL::integer AS date_id, NULL::double precision AS amount,
                       NULL::integer AS branch_id, NULL::integer AS detailed_ledger_id,
                       NULL::text AS description, NULL::integer AS company_id,
                       NULL::integer AS data_source_id WHERE false''')


class SalesAnalysisSale(models.Model):
    _name = 'sales.analysis.sale'
    _description = 'FactSales (Read Only)'
    _auto = False
    _log_access = False
    _rec_name = 'invoice_preview'
    _order = 'date_id desc, id desc'

    sales_id = fields.Char(string='شناسه فروش', readonly=True)
    invoice_number = fields.Char(string='شماره فاکتور', readonly=True)
    invoice_preview = fields.Char(string='پیش‌نمایش فاکتور', readonly=True)
    date_id = fields.Integer(string='شناسه تاریخ', readonly=True)
    customer_id = fields.Integer(string='شناسه مشتری', readonly=True)
    sum_final = fields.Float(string='مبلغ نهایی', readonly=True)
    remaining = fields.Float(string='مانده', readonly=True)
    cash_receipt = fields.Float(string='دریافت نقدی', readonly=True)
    receipt_pos = fields.Float(string='دریافت پوز', readonly=True)
    receipt_online = fields.Float(string='دریافت آنلاین', readonly=True)
    description = fields.Text(string='توضیحات', readonly=True)
    branch_id = fields.Integer(string='شناسه شعبه', readonly=True)

    @api.depends('invoice_number', 'sum_final', 'remaining', 'date_id', 'description')
    def _compute_display_name(self):
        for record in self:
            number = record.invoice_number or '-'
            amount = f'{record.sum_final:,.0f}' if record.sum_final is not False else '0'
            remaining = f'{record.remaining:,.0f}' if record.remaining is not False else '0'
            record.display_name = f'{number} | {amount} | Remaining {remaining}'

    def init(self):
        _create_fact_views(self.env)
        return
        cr = self.env.cr
        source = _source_relation(self.env, [
            ('public', 'raes_fact_sales'),
            ('public', 'fact_sales'),
            ('fdw_raes', 'FactSales'),
        ])
        cr.execute('DROP VIEW IF EXISTS public.sales_analysis_sale CASCADE')
        if source:
            schema, table = source
            q = f'"{schema}"."{table}"'
            cr.execute(f'''CREATE VIEW public.sales_analysis_sale AS
                SELECT COALESCE("ID", 0)::integer AS id,
                       "SalesID"::text AS sales_id,
                       "SaleInvoiceNumber"::text AS invoice_number,
                       "DateID"::integer AS date_id,
                       "CustomerID"::integer AS customer_id,
                       "SumFinal"::double precision AS sum_final,
                       "Remaining"::double precision AS remaining,
                       "CashReceipt"::double precision AS cash_receipt,
                       "ReceiptPOS"::double precision AS receipt_pos,
                       "ReceiptOnline"::double precision AS receipt_online,
                       "Description"::text AS description,
                       "BranchID"::integer AS branch_id
                  FROM {q}''')
        else:
            cr.execute('''CREATE VIEW public.sales_analysis_sale AS
                SELECT NULL::integer AS id, NULL::text AS sales_id,
                       NULL::text AS invoice_number, NULL::integer AS date_id,
                       NULL::integer AS customer_id, NULL::double precision AS sum_final,
                       NULL::double precision AS remaining, NULL::double precision AS cash_receipt,
                       NULL::double precision AS receipt_pos, NULL::double precision AS receipt_online,
                       NULL::text AS description, NULL::integer AS branch_id WHERE false''')


class SalesAnalysisCustomer(models.Model):
    _name = 'sales.analysis.customer'
    _description = 'Customer from DimDetailedLedger'
    _auto = False
    _log_access = False
    _rec_name = 'name'

    name = fields.Char(string='نام مشتری', readonly=True)
    code = fields.Char(string='کد مشتری', readonly=True)

    def init(self):
        _create_fact_views(self.env)
