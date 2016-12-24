# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
import work

def register():
    Pool.register(
        work.Work,
        work.ProjectSummary,
        module='project_management', type_='model')
