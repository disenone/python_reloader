# encoding: utf-8

_reload_data = set([
    'const_value_reload',
])

const_value_reload = 1

const_value_not_reload = 1


def func_ret():
    return 1


def func_wrapper(val):
    from functools import wraps
    func_ref = func_ret

    def _wrapper(func):

        @wraps(func)
        def _wrapped(*args, **kwargs):
            return func(func_ref(), val, *args, **kwargs)

        return _wrapped

    return _wrapper


@func_wrapper(1)
def func_wrapped(*args):
    return args + (1, )


class AClass:
    _reload_data = set(['const_value_reload'])
    _del_func = True

    const_value_reload = 1

    const_value_not_reload = 1

    def func(self):
        return 1

    @classmethod
    def method(cls):
        return 1

    @staticmethod
    def smethod():
        return 1
