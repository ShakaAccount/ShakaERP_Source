from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from . import agent_schedule as sched

SCHEDULE_FIELDS = [
    'schedule_name', 'schedule_enabled', 'schedule_type', 'occurs',
    'recurs_every', 'monthly_mode', 'month_day', 'relative_week',
    'relative_day', 'subday_type', 'subday_interval', 'start_time',
    'end_time', 'start_date', 'end_date', *sched.WEEKDAYS]
RUN_STATUS = {0: 'Failed', 1: 'Succeeded', 2: 'Retry', 3: 'Canceled',
              4: 'In progress'}


class RaesDwAgentJob(models.Model):
    """A SQL Server Agent job running ETL.spGatheringData, edited from Odoo.

    SQL Agent stays the scheduler; this record is only an editor over msdb
    (sp_add_* / sp_update_*), talking to it through the catalog's pymssql
    connection. Apply creates the job and schedule when they don't exist."""
    _name = 'raes.dw.agent.job'
    _description = 'DW ETL SQL Agent Job'
    _inherit = ['mail.thread']
    _rec_name = 'job_name'
    connection_id = fields.Many2one(
        'raes.dw.connection', required=True, ondelete='cascade')
    job_name = fields.Char(required=True, tracking=True)
    step_id = fields.Integer(default=1, required=True)
    step_database = fields.Char(
        help='Database the job step runs in. Empty = the connection database.')
    job_exists = fields.Boolean(readonly=True)
    last_sync = fields.Datetime(readonly=True)
    last_run_outcome = fields.Char(readonly=True)

    # --- ETL.spGatheringData parameters (0 / empty = NULL) --------------
    p_company = fields.Integer('@CompanyID', help='0 = NULL')
    p_data_source = fields.Integer('@DataSourceID', help='0 = NULL')
    p_module = fields.Integer('@ModuleID', help='0 = NULL')
    p_entity = fields.Integer('@EntityID', help='0 = NULL')
    p_date = fields.Integer('@DateID', default=0)
    p_label = fields.Char('@Label', help='Empty = NULL')
    command_preview = fields.Text(compute='_compute_command_preview')

    # --- SSAS processing, a job step run after the ETL step succeeds ------
    ssas_enabled = fields.Boolean(
        'Process SSAS after ETL', default=True,
        help='Adds a "Process SSAS" step that refreshes the Tabular database '
             'whenever the ETL step succeeds. The SQL Agent service account '
             'needs admin rights on that SSAS database.')
    ssas_server = fields.Char(
        'SSAS server',
        help='Empty = the DW connection host. Set only for a named instance, '
             r'e.g. HOST\TABULAR.')
    ssas_database = fields.Char('SSAS database name', default='Shaka_SSAS')
    ssas_refresh_type = fields.Selection(
        [(t, t) for t in sched.SSAS_REFRESH], string='Refresh type',
        default='full', required=True)

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

    @api.depends('p_company', 'p_data_source', 'p_module', 'p_entity',
                 'p_date', 'p_label')
    def _compute_command_preview(self):
        for rec in self:
            rec.command_preview = sched.build_command(rec._vals(
                [f for _n, f in sched.PARAMS]))

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
                "SELECT st.command, st.database_name "
                "FROM msdb.dbo.sysjobs j LEFT JOIN msdb.dbo.sysjobsteps st "
                "ON st.job_id = j.job_id AND st.step_id = %s "
                "WHERE j.name = %s", (self.step_id, self.job_name))
            job = cur.fetchone()
            if not job:
                return None
            cur.execute(
                "SELECT TOP 1 s.* FROM msdb.dbo.sysjobs j "
                "JOIN msdb.dbo.sysjobschedules js ON js.job_id = j.job_id "
                "JOIN msdb.dbo.sysschedules s "
                "ON s.schedule_id = js.schedule_id WHERE j.name = %s "
                "ORDER BY CASE WHEN s.name = %s THEN 0 ELSE 1 END, "
                "s.schedule_id", (self.job_name, self.schedule_name))
            schedule = cur.fetchone()
            ssas = self._ssas_step(cur)
            return job, schedule, ssas, self._last_outcome(cur)

        found = self._run(load)
        if not found:
            self.write({'job_exists': False, 'last_sync': fields.Datetime.now()})
            return self._notify(_('Job "%s" not found on SQL Server — '
                                  'Apply will create it.', self.job_name))
        job, schedule, ssas, outcome = found
        vals = sched.parse_command(job['command'])
        vals.update(job_exists=True, last_sync=fields.Datetime.now(),
                    last_run_outcome=outcome,
                    step_database=job['database_name'] or self.step_database,
                    ssas_enabled=bool(ssas))
        if ssas:
            db, refresh = sched.parse_ssas_command(ssas['command'])
            server = ssas['server']
            vals.update(ssas_server=False if server == self.connection_id.host
                        else server,
                        ssas_database=db or self.ssas_database,
                        ssas_refresh_type=refresh)
        if schedule:
            vals.update(sched.schedule_values(schedule))
        self.write(vals)
        return self._notify(_('Loaded "%s" from SQL Server.', self.job_name))

    def action_apply(self):
        self.ensure_one()
        try:
            params = sched.schedule_params(self._vals(SCHEDULE_FIELDS))
        except ValueError as e:
            raise UserError(str(e))
        if self.ssas_enabled and not self.ssas_database:
            raise UserError(_('Set the SSAS database, or untick '
                              '"Process SSAS after ETL".'))
        command = self.command_preview
        database = self.step_database or self.connection_id.database
        sched_args = ', '.join('@%s = %%(%s)s' % (k, k) for k in params)

        def apply(cur):
            cur.execute("SELECT 1 AS x FROM msdb.dbo.sysjobs WHERE name = %s",
                        (self.job_name,))
            created = not cur.fetchone()
            if created:
                cur.execute(
                    "EXEC msdb.dbo.sp_add_job @job_name = %s", (self.job_name,))
                cur.execute(
                    "EXEC msdb.dbo.sp_add_jobstep @job_name = %s, "
                    "@step_name = %s, @subsystem = 'TSQL', "
                    "@database_name = %s, @command = %s",
                    (self.job_name, 'Run spGatheringData', database, command))
                cur.execute("EXEC msdb.dbo.sp_add_jobserver @job_name = %s",
                            (self.job_name,))
            else:
                cur.execute(
                    "EXEC msdb.dbo.sp_update_jobstep @job_name = %s, "
                    "@step_id = %s, @database_name = %s, @command = %s",
                    (self.job_name, self.step_id, database, command))
            self._apply_ssas_step(cur)
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

    def _ssas_step(self, cur):
        cur.execute(
            "SELECT st.step_id, st.command, st.server "
            "FROM msdb.dbo.sysjobsteps st JOIN msdb.dbo.sysjobs j "
            "ON j.job_id = st.job_id WHERE j.name = %s AND st.step_name = %s",
            (self.job_name, sched.SSAS_STEP))
        return cur.fetchone()

    def _apply_ssas_step(self, cur):
        """Add / update / remove the "Process SSAS" step, then point the ETL
        step's on-success at it (4 = go to step) or at "quit with success"
        (1). On ETL failure the job stops, so SSAS never processes bad data."""
        step = self._ssas_step(cur)
        if self.ssas_enabled:
            args = (self.ssas_server or self.connection_id.host,
                    sched.build_ssas_command(self.ssas_database,
                                             self.ssas_refresh_type))
            if step:
                cur.execute(
                    "EXEC msdb.dbo.sp_update_jobstep @job_name = %s, "
                    "@step_id = %s, @server = %s, @command = %s",
                    (self.job_name, step['step_id'], *args))
            else:
                cur.execute(
                    "EXEC msdb.dbo.sp_add_jobstep @job_name = %s, "
                    "@step_name = %s, @subsystem = 'ANALYSISCOMMAND', "
                    "@server = %s, @command = %s, "
                    "@on_success_action = 1, @on_fail_action = 2",
                    (self.job_name, sched.SSAS_STEP, *args))
                step = self._ssas_step(cur)
            cur.execute(
                "EXEC msdb.dbo.sp_update_jobstep @job_name = %s, "
                "@step_id = %s, @on_success_action = 4, "
                "@on_success_step_id = %s",
                (self.job_name, self.step_id, step['step_id']))
            return
        if step:
            cur.execute("EXEC msdb.dbo.sp_delete_jobstep @job_name = %s, "
                        "@step_id = %s", (self.job_name, step['step_id']))
        cur.execute(
            "EXEC msdb.dbo.sp_update_jobstep @job_name = %s, @step_id = %s, "
            "@on_success_action = 1", (self.job_name, self.step_id))

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
