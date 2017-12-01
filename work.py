# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.pool import Pool, PoolMeta
from trytond.model import ModelView, ModelSQL, fields
from trytond.model import UnionMixin
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, Button
from sql import Column
from trytond.pyson import PYSONEncoder


__all__ = ['Work', 'ProjectSummary', 'ProjectSummaryStart',
    'ProjectSummaryWizard']


class ProjectSummaryStart(ModelView):
    'Project Summary Start'
    __name__ = 'project.work.summary.start'

    limit_date = fields.Date('At Date')

    @staticmethod
    def default_limit_date():
        Date_ = Pool().get('ir.date')
        return Date_.today()


class ProjectSummaryWizard(Wizard):
    'Project Summary Wizard'
    __name__ = 'project.open_summary'

    start = StateView('project.work.summary.start',
        'project_management.open_project_summary_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_summary', 'tryton-ok', True),
            ])
    open_summary = StateAction('project_management.act_project_summary_id')

    def do_open_summary(self, action):
        pool = Pool()
        ProjectSummary = pool.get('project.work.summary')
        ProjectWork = pool.get('project.work')

        active_ids = Transaction().context.get('active_ids')
        projects = ProjectWork.browse(active_ids)
        res_ids = [ProjectSummary.union_shard(w.id, 'project.work') for
            w in projects]

        context = {}
        context['limit_date'] = self.start.limit_date
        data = {'res_ids': res_ids}
        action['pyson_domain'] = PYSONEncoder().encode([('id', 'in', res_ids)])
        action['pyson_context'] = PYSONEncoder().encode(context)
        return action, data


class Work:
    __metaclass__ = PoolMeta
    __name__ = 'project.work'

    progress_cost = fields.Function(fields.Numeric('Progress Cost',
            digits=(16, 4)), 'get_total')
    progress_revenue = fields.Function(fields.Numeric('Revenue(P)',
            digits=(16, 4)), 'get_total')

    invoiced_cost = fields.Function(fields.Numeric('Cost (F)',
            digits=(16, 4)), 'get_total')

    @staticmethod
    def _get_summary_models():
        # [(model, related_field, function), ]
        return []

    @staticmethod
    def _get_summary_fields():
        return ['cost', 'revenue', 'progress_cost', 'progress_revenue',
            'invoiced_cost']

    @classmethod
    def get_total(cls, works, names):
        names = list(set(names + cls._get_summary_fields()))
        res = super(Work, cls).get_total(works, names)
        return res

    @classmethod
    def get_amounts(cls, works, names):
        pool = Pool()
        res = {}
        for name in names:
            res[name] = {}
            for work in works:
                res[name][work.id] = Decimal(0)

        Company = pool.get('company.company')
        company = Transaction().context.get('company')
        company = Company(company)
        digits = company.currency.digits
        for model, related_field, calc_func in cls._get_summary_models():
            Model = pool.get(model)
            objects = Model.search([(related_field, 'in',
                [x.id for x in works])])
            if not objects:
                continue
            func = getattr(Model, calc_func)
            values = func(objects, names)
            for name in names:
                if name not in values:
                    continue
                for k, val in values[name].iteritems():
                    obj = Model(k)
                    key = getattr(obj, related_field)
                    res[name][key.id] = (res[name].get(key.id, Decimal(0)) +
                      val).quantize(
                          Decimal(str(10.0 ** -digits)))
        return res

    @classmethod
    def _get_invoiced_cost(cls, works):
        return cls.get_amounts(works, ['invoiced_cost'])['invoiced_cost']

    @classmethod
    def _get_progress_cost(cls, works):
        return cls.get_amounts(works, ['progress_cost'])['progress_cost']

    @classmethod
    def _get_cost(cls, works):
        return cls.get_amounts(works, ['cost'])['cost']

    @classmethod
    def _get_revenue(cls, works):
        return cls.get_amounts(works, ['revenue'])['revenue']

    @classmethod
    def _get_progress_revenue(cls, works):
        return cls.get_amounts(works, ['progress_revenue'])['progress_revenue']


class ProjectSummary(UnionMixin, ModelSQL, ModelView):
    'Project Summary'

    __name__ = 'project.work.summary'

    cost = fields.Function(fields.Numeric('Cost(T)', digits=(16, 4)),
            'get_total')
    revenue = fields.Function(fields.Numeric('Revenue(T)', digits=(16, 4)),
            'get_total')
    progress_cost = fields.Function(fields.Numeric('Cost(P)',
            digits=(16, 4)), 'get_total')
    progress_revenue = fields.Function(fields.Numeric('Revenue(P)',
            digits=(16, 4)), 'get_total')

    invoiced_cost = fields.Function(fields.Numeric('Cost(F)',
            digits=(16, 4)), 'get_total')
    invoiced_amount = fields.Function(fields.Numeric('Revenue(F)',
            digits=(16, 4)), 'get_total')

    type = fields.Selection('get_types', 'Type', required=True, readonly=True)
    parent = fields.Many2One('project.work.summary', 'Parent')
    children = fields.One2Many('project.work.summary', 'parent', 'Children')

    company = fields.Many2One('company.company', 'Company')
    name = fields.Char('Name')
    origin = fields.Function(fields.Reference('Origin', selection='get_types'),
        '_get_origin')

    @classmethod
    def _get_origin(cls, lines, name):
        m = {}
        for line in lines:
            obj = cls.union_unshard(line.id)
            m[line.id] = "%s,%s" % (obj.__name__, obj.id)
        return m

    @classmethod
    def get_types(cls):
        Model = Pool().get('ir.model')
        models = cls.union_models()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(m.model, m.name) for m in models]

    @classmethod
    def union_column(cls, name, field, table, Model):

        if name == 'type':
            return Model.__name__

        if name == 'parent':
            if Model.__name__ != 'project.work':
                field_name = Model._get_summary_related_field()
                union_field = Model._fields.get(field_name)

                if union_field:
                    column = Column(table, union_field.name)
                    target_model = union_field.model_name
                    column = cls.union_shard(column, target_model)
                    return column
        res = super(ProjectSummary, cls).union_column(name, field,
            table, Model)
        return res

    @staticmethod
    def union_models():
        return ['project.work']

    @classmethod
    def get_total(cls, lines, names):
        pool = Pool()
        res = {}
        for name in names:
            res[name] = {}
        for line in lines:
            Model = pool.get(line.type)
            func = getattr(Model, 'get_total')
            obj = cls.union_unshard(line.id)
            val = func([obj], names)
            for name in names:
                res[name][line.id] = val.get(name) and \
                    val[name].get(obj.id, Decimal(0)) or Decimal(0)
        return res
