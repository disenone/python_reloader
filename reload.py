# encoding: utf-8
import sys
import importlib
from importlib import util as import_util
import inspect


class MetaFinder:
    def __init__(self, reloader):
        self._reloader = reloader


    def find_spec(self, fullname, path, target=None):
        # find source file
        finder = importlib.machinery.PathFinder()
        spec = finder.find_spec(fullname, path)
        if not spec:
            return

        old_module = self._reloader.GetOldModule(fullname)
        if old_module:
            # save old

            # run new code in old module dict
            code = spec.loader.get_code(fullname)
            exec(code, old_module.__dict__)
            module = old_module
        else:
            module = import_util.module_from_spec(spec)
            spec.loader.exec_module(module)

        try:
            self._reloader.UpdateModule(module)
        except:
            sys.excepthook(*sys.exc_info())

        return import_util.spec_from_loader(fullname, MetaLoader(module))


class MetaLoader:
    def __init__(self, module):
        self._module = module

    def create_module(self, spec):
        return self._module

    def exec_module(self, module):
        # restore __spec__
        module.__spec__ = module.__dict__.pop('__backup_spec__')
        module.__loader__ = module.__dict__.pop('__backup_loader__')


class Reloader:

    IGNORE_ATTRS = {"__module__", "__dict__", "__weakref__"}

    def __init__(self):
        self._old_module_infos = {}
        self._old_modules = {}

    def SaveOldModule(self, module_name):
        module = sys.modules.pop(module_name)
        if not module:
            return

        module_info = dict(module.__dict__)
        for ignore_key in ('__spec__', '_reload_all_data', '_reload_data'):
            module_info.pop(ignore_key, None)
        self._old_module_infos[module_name] = module_info

        module.__backup_spec__ = module.__spec__
        module.__backup_loader__ = module.__loader__
        self._old_modules[module_name] = module

    def GetOldModule(self, module_name):
        return self._old_modules.get(module_name)

    def CanReload(self, module_name):
        if module_name not in sys.modules:
            return False

        module = sys.modules[module_name]
        module_file = module.__file__
        if module_file.startswith('/usr') or 'python3/lib' in module_file or 'Python312' in module_file or __file__ == module_file:
            # ignore python modules
            # add you python lib path
            return False

        return True

    def Reload(self, module_names):
        import gc
        gc_enable = gc.isenabled()
        if gc_enable:
            gc.disable()

        sys.backup_meta_path = sys.meta_path
        sys.meta_path = [MetaFinder(self)]

        module_names = list(filter(self.CanReload, module_names))

        print('reload modules: %s' % module_names)
        for name in module_names:
            self.SaveOldModule(name)

        for name in module_names:
            __import__(name)

        sys.meta_path = sys.backup_meta_path
        delattr(sys, 'backup_meta_path')
        if gc_enable:
            gc.enable()

    def NeedUpdateData(self, module, dict_info, data_name):
        if data_name in ('__dict__', ):
            return False

        return getattr(module, '_reload_all_data', None) or dict_info.get('_reload_all_data', False) or data_name in dict_info.get('_reload_data', ())

    def UpdateModule(self, module):
        old_module_info = self._old_module_infos.get(module.__name__)
        if not old_module_info:
            return

        self.UpdateDict(module, old_module_info, module.__dict__)

    def UpdateDict(self, module, old_dict, new_dict, _reload_all_data=False, _del_func=False):
        dels = []

        for attr_name, old_attr in old_dict.items():

            if attr_name in self.IGNORE_ATTRS:
                continue

            if attr_name not in new_dict:
                if _del_func and (inspect.isfunction(old_attr) or inspect.ismethod(old_attr)):
                    dels.append(attr_name)
                continue

            new_attr = new_dict[attr_name]

            if inspect.isclass(old_attr):
                new_dict[attr_name] = self.ReloadClass(module, old_attr, new_attr)

            elif inspect.isfunction(old_attr):
                new_dict[attr_name] = self.ReloadFunction(module, old_attr, new_attr)

            elif inspect.ismethod(old_attr) or isinstance(old_attr, classmethod) or isinstance(old_attr, staticmethod):
                self.ReloadFunction(module, old_attr.__func__, new_attr.__func__)
                new_dict[attr_name] = old_attr

            elif inspect.isbuiltin(old_attr) \
                    or inspect.ismodule(old_attr) \
                    or inspect.ismethoddescriptor(old_attr) \
                    or isinstance(old_attr, property):
                # keep new
                pass

            elif not _reload_all_data and not self.NeedUpdateData(module, new_dict, attr_name):
                # keep old data
                new_dict[attr_name] = old_attr

        if dels:
            for name in dels:
                old_dict.pop(name)

    def ReloadFunction(self, module, old_func, new_func, recursion_set=None):
        if recursion_set and id(old_func) in recursion_set:
            return old_func

        if not inspect.isfunction(new_func):
            return old_func

        new_closure = new_func.__closure__
        new_closure_num = len(new_closure) if new_closure else 0

        old_closure = old_func.__closure__
        old_closure_num = len(old_closure) if old_closure else 0

        # __closure__ is readonly, num must be the same
        if new_closure_num != old_closure_num:
            return old_func

        recursion_set = recursion_set or set()
        recursion_set.add(id(old_func))

        for keys in ('__code__', '__doc__', '__annotations__'):
            setattr(old_func, keys, getattr(new_func, keys))

        # __dict__
        self.UpdateDict(module, old_func.__dict__, new_func.__dict__, _reload_all_data=True)

        # __defaults__
        old_func.__defaults__ = new_func.__defaults__
        if old_func.__defaults__:
            old_func.__defaults__ = [self.ReloadObject(module, obj) for obj in old_func.__defaults__]

        # __kwdefaults__
        old_func.__kwdefaults__ = new_func.__kwdefaults__
        if old_func.__kwdefaults__:
            old_func.__kwdefaults__ = {key: self.ReloadObject(module, obj) for key, obj in old_func.__kwdefaults__.items()}

        # __closure__
        if old_closure_num:
            for index, old_cell in enumerate(old_closure):
                new_cell_contents = new_closure[index].cell_contents
                old_cell.cell_contents = self.ReloadObject(module, new_cell_contents, old_cell.cell_contents, recursion_set=recursion_set)

        return old_func

    def ReloadObject(self, module, new_obj, old_obj=None, recursion_set=None):
        # keep object old class

        if inspect.isfunction(new_obj):
            if inspect.isfunction(old_obj) and new_obj.__name__ == old_obj.__name__:
                return self.ReloadFunction(old_obj, new_obj, recursion_set)
            else:
                return new_obj

        class_name = new_obj.__class__.__name__
        module_name = new_obj.__class__.__module__
        if module_name in self._old_module_infos:
            old_module_info = self._old_module_infos[module_name]
            if class_name in old_module_info:
                old_class = old_module_info[class_name]
                new_obj.__class__ = old_class

        return new_obj

    def ReloadClass(self, module, old_class, new_class):
        # if not (getattr(new_class, "__flags__", 0) & 0x200):  # Py_TPFLAGS_HEAPTYPE
        #     return

        if old_class.__module__ != module.__name__:
            return old_class

        old_class_dict = ClassDict(old_class)
        self.UpdateDict(module, old_class_dict, ClassDict(new_class), _del_func=new_class.__dict__.get('_del_func', False))

        # copy class __dict__
        new_class_dict = new_class.__dict__
        for name, attr in new_class_dict.items():
            if name not in self.IGNORE_ATTRS:
                old_class_dict[name] = attr

        return old_class


class ClassDict:
    def __init__(self, cls):
        self._cls = cls

    def __contains__(self, name):
        return hasattr(self._cls, name)

    def __setitem__(self, name, val):
        return setattr(self._cls, name, val)

    def __getitem__(self, name):
        return self._cls.__dict__[name]

    def __delitem__(self, name):
        return delattr(self._cls, name)

    def pop(self, name):
        ret = self[name]
        del self[name]
        return ret

    def get(self, name, default):
        return self._cls.__dict__.get(name, default)

    def keys(self):
        return self._cls.__dict__.keys()

    def items(self):
        return self._cls.__dict__.items()


def Reload(module_names):
    reloader = Reloader()
    reloader.Reload(module_names)
