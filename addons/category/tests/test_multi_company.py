from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMultiCompanyCategory(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        dw = cls.env['raes.md.company'].search([], limit=2)
        if len(dw) < 2:
            cls.skipTest(cls, 'needs two DW companies (md.company)')
        cls.dw1, cls.dw2 = dw
        cls.env.cr.execute("SELECT id FROM raes_md_entity LIMIT 1")
        row = cls.env.cr.fetchone()
        if not row:
            cls.skipTest(cls, 'needs a md.entity row')
        cls.entity = cls.env['raes.md.entity'].browse(row[0])
        cls.co1 = cls.env.company
        cls.co1.dw_company_id = cls.dw1
        cls.co2 = cls.env['res.company'].create(
            {'name': 'MC test', 'dw_company_id': cls.dw2.id})
        cls.env.user.company_ids |= cls.co2
        cls.Cat = cls.env['raes.md.category']

    def _root(self, **kw):
        return self.Cat.create(dict(
            title='root', entity_id=self.entity.id, **kw))

    def test_unmapped_company_raises(self):
        self.co1.dw_company_id = False
        with self.assertRaises(UserError):
            self._root()

    def test_shared_visibility_and_owner_delete(self):
        root = self._root(company_ids=[(6, 0, [self.dw2.id])])
        child = self.Cat.create({'title': 'kid', 'parent_id': root.id})
        self.assertEqual(child.company_id, self.dw1)
        self.assertEqual(child._dw_companies(), self.dw1 | self.dw2)

        as2 = self.env['raes.md.entity'].with_company(self.co2).with_context(
            allowed_company_ids=self.co2.ids)
        ids = {c['id'] for c in as2.get_category_tree()}
        self.assertTrue({root.id, child.id} <= ids)

        user = self.env['res.users'].create({
            'name': 'mc user', 'login': 'mc_user',
            'company_id': self.co1.id,
            'company_ids': [(6, 0, (self.co1 | self.co2).ids)],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('base.group_system').id])],
        })
        as_owner = root.with_user(user).with_context(
            allowed_company_ids=self.co1.ids)
        as_shared = root.with_user(user).with_context(
            allowed_company_ids=self.co2.ids)
        with self.assertRaises(AccessError):
            as_shared.unlink()
        as_owner.unlink()
        self.assertFalse(root.exists())
