# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.pool import Pool, PoolMeta
from trytond.model import ModelView, ModelSQL, fields
from trytond.model import UnionMixin
from sql import Union, Column

__all__ = ['Work', 'ProjectSummary']


class Work:
    __metaclass__ = PoolMeta
    __name__ = 'project.work'

    @staticmethod
    def _get_related_cost_and_revenue():
        # [(model, related_field, revenue_function, cost_function), ]
        return []

    @classmethod
    def _get_cost(cls, works):
        res = super(Work, cls)._get_cost(works)
        pool = Pool()
        for model, related_field, revenue_function, cost_function in \
                cls._get_related_cost_and_revenue():
            Model = pool.get(model)
            objects = Model.search([(related_field, 'in',
                [x.id for x in works])])
            func = getattr(Model, cost_function)
            costs = func(objects)
            for w, cost in costs.iteritems():
                obj = Model(w)
                key = getattr(obj, related_field)
                res[key.id] = res.get(key.id, Decimal(0)) + cost
        return res

    @classmethod
    def _get_revenue(cls, works):
        res = super(Work, cls)._get_revenue(works)
        pool = Pool()
        for model, related_field, revenue_function, cost_function in \
                cls._get_related_cost_and_revenue():
            Model = pool.get(model)
            func = getattr(Model, revenue_function)
            objects = Model.search([(related_field, 'in',
                [x.id for x in works])])
            revenues = func(objects)
            for w, revenue in revenues.iteritems():
                obj = Model(w)
                key = getattr(obj, related_field)
                res[key.id] = res.get(key.id, Decimal(0)) + revenue
        return res


class ProjectSummary(UnionMixin, ModelSQL, ModelView):
    'Project Summary'

    __name__ = 'project.work.summary'

    cost = fields.Function(fields.Numeric('cost', digits=(16, 4)), '_get_cost')
    revenue = fields.Function(fields.Numeric('revenue', digits=(16, 4)),
        '_get_revenue')
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
                # TODO: make parent field configurable instead 'project'
                union_field = Model._fields.get('project')
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
    def _get_cost(cls, lines, name=None):
        pool = Pool()
        res = {}
        for line in lines:
            Model = pool.get(line.type)
            func = getattr(Model, '_get_cost')
            obj = cls.union_unshard(line.id)
            val = func([obj])
            res[line.id], = val.values()
        return res

    @classmethod
    def _get_revenue(cls, lines, name=None):
        pool = Pool()
        res = {}
        for line in lines:
            Model = pool.get(line.type)
            func = getattr(Model, '_get_revenue')
            obj = cls.union_unshard(line.id)
            val = func([obj])
            res[line.id], = val.values()
        return res
