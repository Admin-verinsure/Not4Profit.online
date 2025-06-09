# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Ammu Raj (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import api, fields, models
from odoo.exceptions import UserError


class ProjectTaskType(models.Model):
    """Inherits the project Task Type Model for adding new fields
    and functions"""
    _inherit = 'project.task.type'

    progress_bar = fields.Float(string='Progress (%)',
                                help='Set your progress of the stage')
    is_progress_stage = fields.Boolean(string='Is Progress Bar',
                                       help='You can only see the progress '
                                            'if you enable this ')

    @api.constrains('progress_bar', 'sequence')
    def project_progress_bar(self):
        """The Constraints for the project Task Type Model"""
        for stage in self:
            all_progress = self.env['project.task.type'].search([]).filtered(
                lambda progress: progress.is_progress_stage and progress.id != stage.id
            )
            res1 = {rec.progress_bar: rec.sequence for rec in all_progress}

            if stage.progress_bar in res1:
                raise UserError('Ensure that the progress is not duplicated.')

            for rec in all_progress.mapped('progress_bar'):
                if stage.progress_bar < rec:
                    if float(stage.sequence) >= res1[rec]:
                        raise UserError(
                            'The progress in this stage must be greater than that of the '
                            'other stages progress bars. Alternatively, reassess '
                            'the priority assigned to this stage.'
                        )
                else:
                    if float(stage.sequence) < res1[rec]:
                        raise UserError(
                            'The progress in this stage must be less than that of the '
                            'other stages progress bars. Alternatively, reassess '
                            'the priority assigned to this stage.'
                        )

            if stage.progress_bar > 100:
                raise UserError('The progress must be less than or equal to 100')
