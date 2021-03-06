# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
try:
    import pytz
except ImportError:
    pytz = None

from trytond.model import (
    ModelSQL, ModelView, fields, dualmethod, EvalEnvironment)
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If
from trytond.transaction import Transaction


class Sequence(metaclass=PoolMeta):
    __name__ = 'ir.sequence'
    company = fields.Many2One('company.company', 'Company',
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ], help="Restrict the sequence usage to the company.")

    @classmethod
    def __setup__(cls):
        super(Sequence, cls).__setup__()
        cls._order.insert(0, ('company', 'ASC'))

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


class SequenceStrict(Sequence):
    __name__ = 'ir.sequence.strict'


class Date(metaclass=PoolMeta):
    __name__ = 'ir.date'

    @classmethod
    def today(cls, timezone=None):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if timezone is None and company_id:
            company = Company(company_id)
            if company.timezone and pytz:
                timezone = pytz.timezone(company.timezone)
        return super(Date, cls).today(timezone=timezone)


class Rule(metaclass=PoolMeta):
    __name__ = 'ir.rule'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.domain.help += '\n- "employee" from the current user'

    @classmethod
    def _get_cache_key(cls):
        key = super(Rule, cls)._get_cache_key()
        # XXX Use company from context instead of browse to prevent infinite
        # loop, but the cache is cleared when User is written.
        return key + (Transaction().context.get('company'),
            Transaction().context.get('employee'))

    @classmethod
    def _get_context(cls):
        pool = Pool()
        User = pool.get('res.user')
        Employee = pool.get('company.employee')
        context = super()._get_context()
        # Use root to avoid infinite loop when accessing user attributes
        with Transaction().set_user(0):
            user = User(Transaction().user)
        if user.employee:
            with Transaction().set_context(
                    _check_access=False, _datetime=None):
                context['employee'] = EvalEnvironment(
                    Employee(user.employee.id), Employee)
        return context


class Cron(metaclass=PoolMeta):
    __name__ = "ir.cron"
    companies = fields.Many2Many('ir.cron-company.company', 'cron', 'company',
            'Companies', help='Companies registered for this cron.')

    @dualmethod
    @ModelView.button
    def run_once(cls, crons):
        for cron in crons:
            if not cron.companies:
                super(Cron, cls).run_once([cron])
            else:
                for company in cron.companies:
                    with Transaction().set_context(company=company.id):
                        super(Cron, cls).run_once([cron])

    @staticmethod
    def default_companies():
        Company = Pool().get('company.company')
        return list(map(int, Company.search([])))


class CronCompany(ModelSQL):
    'Cron - Company'
    __name__ = 'ir.cron-company.company'
    _table = 'cron_company_rel'
    cron = fields.Many2One('ir.cron', 'Cron', ondelete='CASCADE',
            required=True, select=True)
    company = fields.Many2One('company.company', 'Company', ondelete='CASCADE',
            required=True, select=True)
