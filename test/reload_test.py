# encoding: utf-8

import unittest


class TestReload(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        return cls.prepare()

    @classmethod
    def tearDownClass(cls):
        return cls.cleanup()

    @classmethod
    def prepare(cls):
        import shutil
        import os

        cls.cleanup()
        shutil.copy2('reload_me_before.py', 'reload_me.py')
        shutil.copy2(os.path.join('..', 'python_reloader.py'), 'python_reloader.py')

    @classmethod
    def cleanup(cls):
        import os

        for file_name in ('python_reloader.py', 'reload_me.py'):
            if os.path.exists(file_name):
                os.remove(file_name)

    def test_reload(self):
        self.prepare()
        import reload_me

        # save ids
        ids = self.GetIds(reload_me.__dict__)

        # make sure before correct
        self.assertEqual(reload_me.const_value_not_reload, 0)
        self.assertEqual(reload_me.const_value_reload, 0)
        self.assertEqual(reload_me.func_ret(), 0)
        self.assertEqual(reload_me.func_wrapped(), (0, 0))
        self.assertEqual(reload_me.AClass.const_value_not_reload, 0)
        self.assertEqual(reload_me.AClass.const_value_reload, 0)
        self.assertEqual(reload_me.AClass().func(), 0)
        self.assertTrue(hasattr(reload_me.AClass(), 'func_del'))
        self.assertEqual(reload_me.AClass.method(), 0)
        self.assertEqual(reload_me.AClass.smethod(), 0)

        self.do_reload()

        new_ids = self.GetIds(reload_me.__dict__)
        self.CheckIds(ids, new_ids)

        self.assertEqual(reload_me.const_value_not_reload, 0)
        self.assertEqual(reload_me.const_value_reload, 1)
        self.assertEqual(reload_me.const_value_new, 1)
        self.assertEqual(reload_me.func_ret(), 1)
        self.assertEqual(reload_me.func_wrapped(), (1, 1, 1))
        self.assertEqual(reload_me.AClass.const_value_not_reload, 0)
        self.assertEqual(reload_me.AClass.const_value_reload, 1)
        self.assertEqual(reload_me.AClass().func(), 1)
        self.assertFalse(hasattr(reload_me.AClass(), 'func_del'))
        self.assertEqual(reload_me.AClass.method(), 1)
        self.assertEqual(reload_me.AClass.smethod(), 1)

    def do_reload(self):
        import os
        import shutil
        import python_reloader

        os.remove('reload_me.py')
        shutil.copy2('reload_me_after.py', 'reload_me.py')
        python_reloader.Reload(['reload_me'])

    def GetIds(self, object_dict):
        import inspect
        ids = {}
        for name, obj in object_dict.items():
            ids[name] = id(obj)
            if inspect.isclass(obj):
                ids[name + '.__dict__'] = self.GetIds(obj.__dict__)
        return ids

    def CheckIds(self, old_ids, new_ids):
        for name, info in old_ids.items():
            lower_name = name.lower()
            if 'func' in lower_name or 'method' in lower_name:
                if name not in new_ids:
                    continue
                self.assertEqual(info, new_ids[name], 'func/method [%s] not the same' % name)

            if 'class' in lower_name and isinstance(info, int):
                self.assertEqual(info, new_ids[name], 'class [%s] not the same' % name)
                dict_name = name + '.__dict__'
                self.CheckIds(old_ids[dict_name], new_ids[dict_name])


if __name__ == '__main__':
    unittest.main()
