"""Pure conversions between raes.dw.agent.job field values and SQL Server
Agent's msdb encoding (sysschedules columns / sp_add_schedule arguments) and
the ETL.spGatheringData step command. No Odoo import, so
tests/agent_job_check.py can run it standalone."""
import re
from datetime import date

PROCEDURE = 'ETL.spGatheringData'
# (proc parameter, field) — p_date is always emitted, the rest NULL when empty
PARAMS = [('CompanyID', 'p_company'), ('DataSourceID', 'p_data_source'),
          ('ModuleID', 'p_module'), ('EntityID', 'p_entity'),
          ('DateID', 'p_date'), ('Label', 'p_label')]

SUBDAY = {'once': 1, 'seconds': 2, 'minutes': 4, 'hours': 8}
WEEKDAYS = ('sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat')  # bit i = 1 << i
REL_WEEK = {'first': 1, 'second': 2, 'third': 4, 'fourth': 8, 'last': 16}
NO_END_DATE = 99991231
END_OF_DAY = 235959


def to_hhmmss(hours):
    s = min(round((hours or 0) * 3600), 86399)
    return s // 3600 * 10000 + s % 3600 // 60 * 100 + s % 60


def from_hhmmss(n):
    n = n or 0
    return n // 10000 + n % 10000 // 100 / 60 + n % 100 / 3600


def to_yyyymmdd(d):
    return d.year * 10000 + d.month * 100 + d.day if d else NO_END_DATE


def from_yyyymmdd(n):
    if not n or n >= NO_END_DATE:
        return False
    return date(n // 10000, n // 100 % 100, n % 100)


def schedule_params(v):
    """Field values -> sp_add_schedule / sp_update_schedule arguments."""
    p = {
        'enabled': int(bool(v['schedule_enabled'])),
        'active_start_date': to_yyyymmdd(v['start_date'] or date.today()),
        'active_start_time': to_hhmmss(v['start_time']),
        'active_end_date': NO_END_DATE,
        'active_end_time': END_OF_DAY,
        'freq_interval': 0,
        'freq_subday_type': 0,
        'freq_subday_interval': 0,
        'freq_relative_interval': 0,
        'freq_recurrence_factor': 0,
    }
    if v['schedule_type'] == 'one_time':
        p['freq_type'] = 1
        return p
    p['active_end_date'] = to_yyyymmdd(v['end_date'])
    p['freq_subday_type'] = SUBDAY[v['subday_type']]
    if v['subday_type'] != 'once':
        p['freq_subday_interval'] = v['subday_interval']
        p['active_end_time'] = to_hhmmss(v['end_time'])
    every = v['recurs_every'] or 1
    if v['occurs'] == 'daily':
        p.update(freq_type=4, freq_interval=every)
    elif v['occurs'] == 'weekly':
        mask = sum(1 << i for i, d in enumerate(WEEKDAYS) if v[d])
        if not mask:
            raise ValueError('Pick at least one weekday.')
        p.update(freq_type=8, freq_interval=mask, freq_recurrence_factor=every)
    elif v['monthly_mode'] == 'day':
        p.update(freq_type=16, freq_interval=v['month_day'],
                 freq_recurrence_factor=every)
    else:
        p.update(freq_type=32, freq_interval=int(v['relative_day']),
                 freq_relative_interval=REL_WEEK[v['relative_week']],
                 freq_recurrence_factor=every)
    return p


def schedule_values(row):
    """msdb.dbo.sysschedules row (dict) -> field values."""
    ft = row['freq_type']
    v = {
        'schedule_name': row['name'],
        'schedule_enabled': bool(row['enabled']),
        'schedule_type': 'one_time' if ft == 1 else 'recurring',
        'start_date': from_yyyymmdd(row['active_start_date']),
        'start_time': from_hhmmss(row['active_start_time']),
        'end_date': from_yyyymmdd(row['active_end_date']),
        'end_time': from_hhmmss(row['active_end_time']),
    }
    if ft == 1:
        return v
    v['subday_type'] = {n: k for k, n in SUBDAY.items()}.get(
        row['freq_subday_type'], 'once')
    v['subday_interval'] = row['freq_subday_interval'] or 1
    if ft == 4:
        v.update(occurs='daily', recurs_every=row['freq_interval'])
    elif ft == 8:
        v.update(occurs='weekly', recurs_every=row['freq_recurrence_factor'],
                 **{d: bool(row['freq_interval'] & (1 << i))
                    for i, d in enumerate(WEEKDAYS)})
    elif ft == 16:
        v.update(occurs='monthly', monthly_mode='day',
                 month_day=row['freq_interval'],
                 recurs_every=row['freq_recurrence_factor'])
    elif ft == 32:
        v.update(occurs='monthly', monthly_mode='relative',
                 relative_day=str(row['freq_interval']),
                 relative_week={n: k for k, n in REL_WEEK.items()}.get(
                     row['freq_relative_interval'], 'first'),
                 recurs_every=row['freq_recurrence_factor'])
    return v


def build_command(v):
    lines = []
    for name, field in PARAMS:
        val = v[field]
        if field == 'p_label':
            # trust boundary: free text into T-SQL -> quote strictly
            lit = "N'%s'" % val.replace("'", "''") if val else 'NULL'
        elif field == 'p_date':
            lit = str(int(val or 0))
        else:
            lit = str(int(val)) if val else 'NULL'
        lines.append('  @%s = %s' % (name, lit))
    return 'EXEC %s\n%s' % (PROCEDURE, ',\n'.join(lines))


_ARG = re.compile(r"@(\w+)\s*=\s*(NULL|N?'(?:[^']|'')*'|-?\d+)", re.I)


def parse_command(cmd):
    fields = {n.lower(): f for n, f in PARAMS}
    out = {}
    for name, lit in _ARG.findall(cmd or ''):
        field = fields.get(name.lower())
        if not field:
            continue
        if lit.upper() == 'NULL':
            out[field] = False if field == 'p_label' else 0
        elif lit.endswith("'"):
            out[field] = lit[lit.index("'") + 1:-1].replace("''", "'")
        else:
            out[field] = int(lit)
    return out
