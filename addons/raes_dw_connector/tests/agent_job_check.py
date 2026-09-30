"""Standalone self-check for models/agent_schedule.py (not an Odoo test).
Run: .venv/bin/python addons/raes_dw_connector/tests/agent_job_check.py"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'models'))
import agent_schedule as s  # noqa: E402

assert s.to_hhmmss(s.from_hhmmss(235959)) == 235959
assert s.to_hhmmss(10.5) == 103000
assert s.from_yyyymmdd(s.to_yyyymmdd(date(2026, 5, 26))) == date(2026, 5, 26)
assert s.from_yyyymmdd(s.to_yyyymmdd(False)) is False

base = dict(schedule_name='ScheduleETL', schedule_enabled=True,
            schedule_type='recurring', start_date=date(2026, 5, 26),
            start_time=0.0, end_date=False, end_time=s.from_hhmmss(235959),
            subday_type='minutes', subday_interval=10, recurs_every=1,
            occurs='daily', monthly_mode='day', month_day=1,
            relative_week='first', relative_day='1',
            **{d: False for d in s.WEEKDAYS})
cases = [
    {},  # the SSMS screenshot: daily, every 10 minutes
    dict(occurs='weekly', recurs_every=2, mon=True, wed=True),
    dict(occurs='monthly', month_day=15, recurs_every=3, subday_type='once',
         subday_interval=1),
    dict(occurs='monthly', monthly_mode='relative', relative_week='last',
         relative_day='6'),
    dict(schedule_type='one_time', start_time=10.5),
]
for case in cases:
    v = dict(base, **case)
    p = s.schedule_params(v)
    back = s.schedule_values(dict(p, name=v['schedule_name']))
    for k, val in back.items():
        assert val == v[k] or abs(val - v[k]) < 1e-6, (case, k, val, v[k])
assert s.schedule_params(base)['freq_type'] == 4
assert s.schedule_params(dict(base, occurs='weekly', mon=True, wed=True))[
    'freq_interval'] == 2 | 8

params = [('CompanyID', 'int', ''), ('DataSourceID', 'int', '3'),
          ('Rate', 'decimal', '-1.5'), ('Label', 'nvarchar', "it's"),
          ('Day', 'date', '2026-05-26')]
cmd = s.build_exec('ETL.spGatheringData', params)
assert "@CompanyID = NULL" in cmd and "@DataSourceID = 3" in cmd
assert "@Label = N'it''s'" in cmd and "@Day = '2026-05-26'" in cmd
assert s.parse_exec(cmd) == ('ETL.spGatheringData', [
    ('CompanyID', False, False), ('DataSourceID', 'numeric', '3'),
    ('Rate', 'numeric', '-1.5'), ('Label', 'nvarchar', "it's"),
    ('Day', 'varchar', '2026-05-26')])
# a Load -> Apply round trip reproduces the command
proc, args = s.parse_exec(cmd)
assert s.build_exec(proc, args) == cmd
orig = ("EXEC ETL.spGatheringData\n  @CompanyID = NULL,\n  @DataSourceID = "
        "NULL,\n  @ModuleID = NULL,\n  @EntityID = NULL,\n  @DateID = 0,\n"
        "  @Label = NULL")
assert s.build_exec(*s.parse_exec(orig)) == orig
assert s.parse_exec('EXEC [ETL].[spX];') == ('[ETL].[spX]', [])
assert s.parse_exec('TRUNCATE TABLE x') is None
assert s.parse_exec('EXEC a.b @x = 1; DROP TABLE y') is None
for bad in ('x; DROP TABLE y', "a'b", ''):
    try:
        s.check_identifier(bad)
        raise AssertionError(bad)
    except ValueError:
        pass
try:
    s.sql_literal('int', '1; DROP TABLE y')
    raise AssertionError('non-number accepted')
except ValueError:
    pass
cmd = s.build_ssas_command('Sales', 'full')
assert s.parse_ssas_command(cmd) == ('Sales', 'full')
assert s.parse_ssas_command('<Process/>') == (False, 'full')
print('ok')
