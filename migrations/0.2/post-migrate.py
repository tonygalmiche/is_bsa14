# -*- coding: utf-8 -*-
"""
Migration 0.2 : désactive les règles d'accès natives Odoo sur project.project
et project.task afin d'appliquer les règles basées sur is_equipe_projet_ids.
"""


def migrate(cr, version):
    cr.execute("""
        UPDATE ir_rule
        SET active = False
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'project'
            AND name IN ('project_public_members_rule', 'task_visibility_rule')
        )
    """)
