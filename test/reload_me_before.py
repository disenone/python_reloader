# encoding: utf-8

const_value_reload = 0

const_value_not_reload = 0


def func_ret():
    return 0


def func_wrapper(val):
    from functools import wraps
    func_ref = func_ret

    def _wrapper(func):

        @wraps(func)
        def _wrapped(*args, **kwargs):
            return func(func_ref(), val, *args, **kwargs)

        return _wrapped

    return _wrapper


@func_wrapper(0)
def func_wrapped(*args):
    return args


class AClass:

    const_value_reload = 0

    const_value_not_reload = 0

    def func(self):
        return 0

    def func_del(self):
        return 0

    @classmethod
    def method(cls):
        return 0

    @staticmethod
    def smethod():
        return 0
