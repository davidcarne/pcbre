__author__ = "davidc"

from qtpy import QtCore
from contextlib import contextmanager
import numpy

class mdlbase(object):
    pass

class mdlacc(mdlbase):
    def __init__(self, initial, on=lambda self: None):
        self.value = initial
        self.on = on

    def fixup(self, name):
        assert not hasattr(self, "name")
        self.name = "_%s" % name

    def __get__(self, instance, objtype):
        try:
            name = self.name
        except AttributeError:
            raise NotImplementedError("mdlacc only works when the setup metaclass has been called")

        try:
            return getattr(instance, self.name)
        except AttributeError:
            setattr(instance, self.name, self.value)
            return getattr(instance, self.name)

    def __set__(self, instance, value):
        try:
            name = self.name
        except AttributeError:
            raise NotImplementedError("mdlacc only works when the setup metaclass has been called")

        old = getattr(instance, self.name)
        setattr(instance, self.name, value)

        if value is None and old is not None or value is not None and old is None:
            instance.change()
            self.on(instance)
        elif isinstance(value, numpy.ndarray) and isinstance(old, numpy.ndarray):
            if (old != value).any():
                instance.change()
                self.on(instance)
        elif old != value:
            instance.change()
            self.on(instance)

_base = type(QtCore.QObject.__bases__[0])

class GenModelMeta(_base):
    def __new__(mcs, name, bases, dict):
        for k, v in list(dict.items()):
            if isinstance(v, mdlbase):
                v.fixup("_%s" % k)

        return _base.__new__(mcs, name, bases, dict)

wc = 0
import threading
class GenModel(QtCore.QObject, metaclass=GenModelMeta):
    """
    GenModel is a smart "model" class that may be used to construct models that will
    """
    def __init__(self):
        super(GenModel, self).__init__()
        self.__editing = 0
        self.__changed = False

    changed = QtCore.Signal()

    @QtCore.Slot()
    def change(self):
        if self.__editing:
            self.__changed = True
        else:
            self.changed.emit()

    @contextmanager
    def edit(self):
        self.__editing += 1
        yield
        self.__editing -= 1
        if self.__changed and self.__editing == 0:
            self.changed.emit()
            self.__changed = False

    def __setattr__(self, key, value):
        if key not in ("changed", "__editing", "__changed"):
            if hasattr(self, key):
                old_value = getattr(self, key)
                if hasattr(old_value, "changed"):
                    old_value.changed.disconnect(self.change)

            if hasattr(value, "changed"):
                value.changed.connect(self.change)

        object.__setattr__(self, key, value)

