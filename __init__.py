# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
import work


def register():
    Pool.register(
        work.Work,
        work.ProjectSummary,
        work.ProjectSummaryStart,
        module='project_management', type_='model')

    Pool.register(
        work.ProjectSummaryWizard,
        module='project_management', type_='wizard')
