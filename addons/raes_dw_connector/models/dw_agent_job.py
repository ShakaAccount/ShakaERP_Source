from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from . import agent_schedule as sched

SCHEDULE_FIELDS = [
    'schedule_name', 'schedule_enabled', 'schedule_type', 'occurs',
    'recurs_every', 'monthly_mode', 'month_day', 'relative_week',
    'relative_day', 'subday_type', 'subday_interval', 'start_time',
    'end_time', 'start_date', 'end_date', *sched.WEEKDAYS]
# every SQL Agent subsystem, so any loaded step fits a "Custom" step
SUBSYSTEMS = ['TSQL', 'CmdExec', 'PowerShell', 'SSIS', 'ANALYSISQUERY',
              'ANALYSISCOMMAND', 'Distribution', 'Snapshot', 'LogReader',
              'Merge', 'QueueReader']
RUN_STATUS = {0: 'Failed', 1: 'Succeeded', 2: 'Retry', 3: 'Canceled',
              4: 'In progress'}


class RaesDwAgentJob(models.Model):
    """A SQL Server Agent job (ordered ETL / SSAS steps + one schedule),
    edited from Odoo.

    SQL Agent stays the scheduler; this record is only an editor over msdb
    (sp_add_* / sp_update_*), talking to it through the catalog's pymssql
    connection. Apply creates the job and schedule when they don't exist."""
    _name = 'raes.dw.agent.job'
    _description = 'DW SQL Agent Job'
    _inherit = ['mail.thread']
    _rec_name = 'job_name'
    connection_id = fields.Many2one(
        'raes.dw.connection', required=True, ondelete='cascade',
        default=lambda self: self.env['raes.dw.connection'].search([],
                                                                   limit=1))
    job_name = fields.Char(required=True, tracking=True)
    job_exists = fields.Boolean(readonly=True)
    last_sync = fields.Datetime(readonly=True)
    last_run_outcome = fields.Char(readonly=True)
    step_ids = fields.One2many(
        'raes.dw.agent.job.step', 'job_id', copy=True,
        default=lambda self: [
            Command.create(dict(
                self.env['raes.dw.agent.job.step']._etl_defaults(
                    self.env['raes.dw.connection'].search([], limit=1)),
                name='Run ETL', step_type='etl', sequence=10,
                ssas_refresh_type='full')),
            # every value spelled out: the form's defaults for new rows don't
            # apply to one2many default commands
            Command.create({'name': 'Process SSAS', 'step_type': 'ssas',
                            'sequence': 20, 'ssas_database': 'Shaka_SSAS',
                            'ssas_refresh_type': 'full'})])

    # --- schedule, mirrors the SSMS "Job Schedule Properties" dialog -----
    schedule_name = fields.Char(required=True, default='ScheduleETL')
    schedule_enabled = fields.Boolean('Enabled', default=True)
    schedule_type = fields.Selection(
        [('recurring', 'Recurring'), ('one_time', 'One time')],
        default='recurring', required=True)
    occurs = fields.Selection(
        [('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')],
        default='daily', required=True)
    recurs_every = fields.Integer(
        default=1, help='Days (daily), weeks (weekly) or months (monthly).')
    sun = fields.Boolean('Sunday')
    mon = fields.Boolean('Monday')
    tue = fields.Boolean('Tuesday')
    wed = fields.Boolean('Wednesday')
    thu = fields.Boolean('Thursday')
    fri = fields.Boolean('Friday')
    sat = fields.Boolean('Saturday')
    monthly_mode = fields.Selection(
        [('day', 'Day of month'), ('relative', 'The …')], default='day')
    month_day = fields.Integer('Day', default=1)
    relative_week = fields.Selection(
        [(k, k.capitalize()) for k in sched.REL_WEEK], default='first')
    relative_day = fields.Selection(
        [('1', 'Sunday'), ('2', 'Monday'), ('3', 'Tuesday'),
         ('4', 'Wednesday'), ('5', 'Thursday'), ('6', 'Friday'),
         ('7', 'Saturday'), ('8', 'Day'), ('9', 'Weekday'),
         ('10', 'Weekend day')], default='2')
    subday_type = fields.Selection(
        [('once', 'Occurs once at'), ('hours', 'Hour(s)'),
         ('minutes', 'Minute(s)'), ('seconds', 'Second(s)')],
        string='Daily frequency', default='minutes', required=True)
    subday_interval = fields.Integer('Occurs every', default=10)
    start_time = fields.Float(default=0.0)
    end_time = fields.Float(default=23 + 59 / 60 + 59 / 3600)
    start_date = fields.Date(default=fields.Date.context_today)
    end_date = fields.Date(help='Empty = no end date.')

    def _vals(self, names):
        return {n: self[n] for n in names}

    def _connect(self):
        return self.env['raes.dw.catalog']._mssql_connect(self.connection_id)

    def _run(self, fn):
        """Run fn(cursor) in one MSSQL transaction; MSSQL errors -> UserError."""
        ms = self._connect()
        try:
            cur = ms.cursor(as_dict=True)
            result = fn(cur)
            ms.commit()
            return result
        except UserError:
            ms.rollback()
            raise
        except Exception as e:
            ms.rollback()
            raise UserError(_('SQL Server Agent error:\n%s', str(e)[:800]))
        finally:
            ms.close()

    # ------------------------------------------------------------------
    def action_load(self):
        self.ensure_one()

        def load(cur):
            cur.execute(
                "SELECT st.step_id, st.step_name, st.subsystem, st.command, "
                "st.database_name, st.server FROM msdb.dbo.sysjobs j "
                "JOIN msdb.dbo.sysjobsteps st ON st.job_id = j.job_id "
                "WHERE j.name = %s ORDER BY st.step_id", (self.job_name,))
            steps = cur.fetchall()
            cur.execute("SELECT 1 AS x FROM msdb.dbo.sysjobs WHERE name = %s",
                        (self.job_name,))
            if not cur.fetchone():
                return None
            cur.execute(
                "SELECT TOP 1 s.* FROM msdb.dbo.sysjobs j "
                "JOIN msdb.dbo.sysjobschedules js ON js.job_id = j.job_id "
                "JOIN msdb.dbo.sysschedules s "
                "ON s.schedule_id = js.schedule_id WHERE j.name = %s "
                "ORDER BY CASE WHEN s.name = %s THEN 0 ELSE 1 END, "
                "s.schedule_id", (self.job_name, self.schedule_name))
            return steps, cur.fetchone(), self._last_outcome(cur)

        found = self._run(load)
        if not found:
            self.write({'job_exists': False, 'last_sync': fields.Datetime.now()})
            return self._notify(_('Job "%s" not found on SQL Server — '
                                  'Apply will create it.', self.job_name))
        steps, schedule, outcome = found
        cmds = [Command.clear()] + [Command.create(dict(
            self.env['raes.dw.agent.job.step']._from_msdb(row),
            sequence=row['step_id'])) for row in steps]
        vals = {'job_exists': True, 'last_sync': fields.Datetime.now(),
                'last_run_outcome': outcome, 'step_ids': cmds}
        if schedule:
            vals.update(sched.schedule_values(schedule))
        self.write(vals)
        return self._notify(_('Loaded "%s" from SQL Server.', self.job_name))

    def action_apply(self):
        self.ensure_one()
        if not self.step_ids:
            raise UserError(_('Add at least one step.'))
        try:
            params = sched.schedule_params(self._vals(SCHEDULE_FIELDS))
            steps = [s._agent_args() for s in self.step_ids]
        except ValueError as e:
            raise UserError(str(e))
        sched_args = ', '.join('@%s = %%(%s)s' % (k, k) for k in params)

        def apply(cur):
            cur.execute("SELECT 1 AS x FROM msdb.dbo.sysjobs WHERE name = %s",
                        (self.job_name,))
            created = not cur.fetchone()
            if created:
                cur.execute(
                    "EXEC msdb.dbo.sp_add_job @job_name = %s", (self.job_name,))
                cur.execute("EXEC msdb.dbo.sp_add_jobserver @job_name = %s",
                            (self.job_name,))
            else:
                # step_id 0 = every step; re-added below in the Odoo order
                cur.execute("EXEC msdb.dbo.sp_delete_jobstep @job_name = %s, "
                            "@step_id = 0", (self.job_name,))
            for i, step in enumerate(steps, 1):
                # success -> next step (3), last one -> quit OK (1);
                # failure always quits the job (2), so later steps never run
                # on bad data
                cur.execute(
                    "EXEC msdb.dbo.sp_add_jobstep @job_name = %(job)s, "
                    "@step_id = %(step_id)s, @step_name = %(name)s, "
                    "@subsystem = %(subsystem)s, "
                    "@database_name = %(database)s, @server = %(server)s, "
                    "@command = %(command)s, @on_success_action = %(ok)s, "
                    "@on_fail_action = 2",
                    dict(step, job=self.job_name, step_id=i,
                         ok=1 if i == len(steps) else 3))
            cur.execute("EXEC msdb.dbo.sp_update_job @job_name = %s, "
                        "@start_step_id = 1", (self.job_name,))
            cur.execute(
                "SELECT TOP 1 s.schedule_id FROM msdb.dbo.sysjobs j "
                "JOIN msdb.dbo.sysjobschedules js ON js.job_id = j.job_id "
                "JOIN msdb.dbo.sysschedules s "
                "ON s.schedule_id = js.schedule_id "
                "WHERE j.name = %s AND s.name = %s",
                (self.job_name, self.schedule_name))
            attached = cur.fetchone()
            args = dict(params, job_name=self.job_name,
                        schedule_name=self.schedule_name)
            if attached:
                args['schedule_id'] = attached['schedule_id']
                cur.execute("EXEC msdb.dbo.sp_update_schedule "
                            "@schedule_id = %(schedule_id)s, " + sched_args,
                            args)
            else:
                # by id: schedule names aren't unique in msdb
                cur.execute(
                    "DECLARE @sid int; EXEC msdb.dbo.sp_add_schedule "
                    "@schedule_name = %(schedule_name)s, " + sched_args +
                    ", @schedule_id = @sid OUTPUT; "
                    "EXEC msdb.dbo.sp_attach_schedule "
                    "@job_name = %(job_name)s, @schedule_id = @sid", args)
            return created

        created = self._run(apply)
        self.write({'job_exists': True, 'last_sync': fields.Datetime.now()})
        msg = (_('Created SQL Agent job "%s".', self.job_name) if created
               else _('Updated SQL Agent job "%s".', self.job_name))
        self.message_post(body=msg)
        return self._notify(msg)

    def action_run_now(self):
        self.ensure_one()
        self._run(lambda cur: cur.execute(
            "EXEC msdb.dbo.sp_start_job @job_name = %s", (self.job_name,)))
        self.message_post(body=_('Started job "%s".', self.job_name))
        return self._notify(_('Job "%s" started.', self.job_name))

    def _last_outcome(self, cur):
        cur.execute(
            "SELECT TOP 1 h.run_status, h.run_date, h.run_time "
            "FROM msdb.dbo.sysjobhistory h JOIN msdb.dbo.sysjobs j "
            "ON j.job_id = h.job_id WHERE j.name = %s AND h.step_id = 0 "
            "ORDER BY h.instance_id DESC", (self.job_name,))
        row = cur.fetchone()
        if not row:
            return False
        d, t = row['run_date'], row['run_time']
        return '%s — %04d-%02d-%02d %02d:%02d:%02d' % (
            RUN_STATUS.get(row['run_status'], row['run_status']),
            d // 10000, d // 100 % 100, d % 100,
            t // 10000, t // 100 % 100, t % 100)

    def _notify(self, message):
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'message': message, 'type': 'success',
                       'next': {'type': 'ir.actions.client',
                                'tag': 'soft_reload'}},
        }


class RaesDwAgentJobStep(models.Model):
    """One SQL Agent job step: an ETL stored-procedure call (TSQL) or an SSAS
    Tabular refresh (ANALYSISCOMMAND). Run in sequence order."""
    _name = 'raes.dw.agent.job.step'
    _description = 'DW SQL Agent Job Step'
    _order = 'sequence, id'

    job_id = fields.Many2one('raes.dw.agent.job', required=True,
                             ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char('Step name', required=True)
    step_type = fields.Selection(
        [('etl', 'ETL (stored procedure)'), ('ssas', 'SSAS process'),
         ('custom', 'Custom')],
        string='Type', required=True, default='etl')

    # --- ETL -------------------------------------------------------------
    database = fields.Char(
        help='Database the step runs in. Empty = the connection database.')
    procedure = fields.Char()
    param_ids = fields.One2many('raes.dw.agent.job.param', 'step_id',
                                'Parameters', copy=True)
    command_preview = fields.Text(compute='_compute_command_preview')

    # --- Custom: any subsystem, command sent as typed ------------------
    subsystem = fields.Selection([(x, x) for x in SUBSYSTEMS], default='TSQL')
    command = fields.Text()
    server = fields.Char(help='Analysis Services server, for ANALYSIS* '
                              'subsystems. Empty = the DW connection host.')

    # --- SSAS ------------------------------------------------------------
    ssas_server = fields.Char(
        'SSAS server',
        help='Empty = the DW connection host. Set only for a named instance, '
             r'e.g. HOST\TABULAR. The SQL Agent service account needs admin '
             'rights on the SSAS database.')
    ssas_database = fields.Char('SSAS database name', default='Shaka_SSAS')
    ssas_refresh_type = fields.Selection(
        [(t, t) for t in sched.SSAS_REFRESH], string='Refresh type',
        default='full', required=True)

    @api.model
    def _etl_defaults(self, connection):
        """procedure + parameter rows from the connection's default ETL
        command (the built-in one when there's no connection yet)."""
        proc, args = sched.parse_exec(
            connection.default_etl_command or sched.DEFAULT_ETL_COMMAND)
        return {'procedure': proc, 'param_ids': [Command.create(
            {'sequence': i, 'name': n, 'sql_type': t, 'value': v})
            for i, (n, t, v) in enumerate(args)]}

    @api.onchange('step_type')
    def _onchange_step_type(self):
        if self.step_type == 'etl' and not self.param_ids:
            self.update(self._etl_defaults(self.job_id.connection_id))

    @api.depends('step_type', 'command', 'procedure', 'param_ids.value',
                 'param_ids.name', 'param_ids.sql_type', 'ssas_database',
                 'ssas_refresh_type')
    def _compute_command_preview(self):
        for rec in self:
            try:
                rec.command_preview = rec._command()
            except ValueError as e:
                rec.command_preview = '-- %s' % e

    def _command(self):
        if self.step_type == 'custom':
            return self.command or ''
        if self.step_type == 'ssas':
            return sched.build_ssas_command(self.ssas_database,
                                            self.ssas_refresh_type)
        return sched.build_exec(self.procedure, [
            (p.name, p.sql_type, p.value) for p in self.param_ids])

    def _agent_args(self):
        """sp_add_jobstep arguments; ValueError on anything unsafe/missing."""
        conn = self.job_id.connection_id
        if self.step_type == 'custom':
            if not (self.subsystem and self.command):
                raise ValueError('Step "%s": set the subsystem and command.'
                                 % self.name)
            tsql = self.subsystem == 'TSQL'
            return {'name': self.name, 'subsystem': self.subsystem,
                    'command': self.command,
                    'database': sched.check_identifier(
                        self.database or conn.database) if tsql else None,
                    'server': (self.server or conn.host)
                    if self.subsystem.startswith('ANALYSIS') else None}
        if self.step_type == 'ssas':
            if not self.ssas_database:
                raise ValueError('Step "%s": set the SSAS database.' % self.name)
            return {'name': self.name, 'subsystem': 'ANALYSISCOMMAND',
                    'database': None, 'command': self._command(),
                    'server': self.ssas_server or conn.host}
        return {'name': self.name, 'subsystem': 'TSQL', 'server': None,
                'database': sched.check_identifier(
                    self.database or conn.database),
                'command': self._command()}

    @api.model
    def _from_msdb(self, row):
        """sysjobsteps row -> create values. Anything that isn't a plain EXEC
        or an SSAS refresh loads as a Custom step, kept verbatim."""
        vals = {'name': row['step_name']}
        if row['subsystem'] == 'ANALYSISCOMMAND':
            db, refresh = sched.parse_ssas_command(row['command'])
            if db:
                return dict(vals, step_type='ssas', ssas_database=db,
                            ssas_refresh_type=refresh,
                            ssas_server=row['server'] or False)
        elif row['subsystem'] == 'TSQL':
            parsed = sched.parse_exec(row['command'])
            if parsed:
                proc, args = parsed
                return dict(vals, step_type='etl', procedure=proc,
                            database=row['database_name'] or False,
                            param_ids=[Command.create(
                                {'name': n, 'sql_type': t, 'value': v,
                                 'sequence': i})
                                for i, (n, t, v) in enumerate(args)])
        return dict(vals, step_type='custom', subsystem=row['subsystem'],
                    command=row['command'],
                    database=row['database_name'] or False,
                    server=row['server'] or False)

    def action_fetch_params(self):
        """Rebuild the parameter rows from the procedure's signature
        (sys.parameters), keeping values of parameters that still exist."""
        self.ensure_one()
        job = self.job_id
        try:
            proc = sched.check_identifier(self.procedure)
            db = sched.check_identifier(
                self.database or job.connection_id.database)
        except ValueError as e:
            raise UserError(str(e))

        def fetch(cur):
            # identifiers validated above; [db] can't be a bound parameter
            cur.execute(
                "SELECT SUBSTRING(p.name, 2, 200) AS name, "
                "TYPE_NAME(p.user_type_id) AS sql_type "
                "FROM [%s].sys.parameters p WHERE p.object_id = OBJECT_ID(%%s) "
                "ORDER BY p.parameter_id" % db.strip('[]'),
                ('%s.%s' % (db, proc),))
            return cur.fetchall()

        rows = job._run(fetch)
        if not rows:
            raise UserError(_('Procedure %(proc)s not found in %(db)s, or it '
                              'has no parameters.', proc=proc, db=db))
        old = {p.name.lower(): p.value for p in self.param_ids}
        self.param_ids = [Command.clear()] + [Command.create({
            'sequence': i, 'name': r['name'], 'sql_type': r['sql_type'],
            'value': old.get(r['name'].lower(), False)})
            for i, r in enumerate(rows)]


class RaesDwAgentJobParam(models.Model):
    _name = 'raes.dw.agent.job.param'
    _description = 'DW SQL Agent Job Step Parameter'
    _order = 'sequence, id'

    step_id = fields.Many2one('raes.dw.agent.job.step', required=True,
                              ondelete='cascade')
    sequence = fields.Integer()
    name = fields.Char(required=True, help='Without the leading @.')
    sql_type = fields.Char('Type', readonly=True)
    value = fields.Char(help='Empty = NULL.')
