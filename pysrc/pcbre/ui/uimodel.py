__author__ = "davidc"

from contextlib import contextmanager
import numpy
from typing import List, Type, Callable, Any, Generator

class mdlacc:
    def __init__(self, initial: 'Any', on : 'Callable[[Any], None]' =lambda self: None) -> None:
        self.value = initial
        self.on = on

    def fixup(self, name: str) -> None:
        assert not hasattr(self, "name")
        self.name = "_%s" % name

    def __get__(self, instance: 'GenModel', objtype: Any) -> Any:
        try:
            name = self.name
        except AttributeError:
            raise NotImplementedError("mdlacc only works when the setup metaclass has been called")

        try:
            return getattr(instance, self.name)
        except AttributeError:
            setattr(instance, self.name, self.value)
            return getattr(instance, self.name)

    def __set__(self, instance: 'GenModel', value : Any) -> None:
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


class GenModelMeta(type):
    def __new__(mcs, name: 'str', bases: List[Type], d: 'dict[str, Any]') -> 'Any':
        for k, v in list(d.items()):
            if isinstance(v, mdlacc):
                v.fixup("_%s" % k)

        return type.__new__(mcs, name, bases, d)

class TinySignal:
    def __init__(self) -> None:
        self.__l = set()

    def connect(self, x: Callable[[], None]) -> None:
        self.__l.add(x)

    def disconnect(self, x: Callable[[], None]) -> None:
        self.__l.remove(x)

    def emit(self) -> None:
        for i in self.__l:
            i()

class GenModel(metaclass=GenModelMeta):
    """
    GenModel is a smart "model" class that may be used to construct models that will
    """
    def __init__(self) -> None:
        super(GenModel, self).__init__()
        self.__editing = 0
        self.__changed = False

        self.changed = TinySignal()

    def change(self) -> None:
        if self.__editing:
            self.__changed = True
        else:
            self.changed.emit()

    @contextmanager
    def edit(self) -> 'Generator[None, None, None]':
        self.__editing += 1
        yield
        self.__editing -= 1
        if self.__changed and self.__editing == 0:
            self.changed.emit()
            self.__changed = False

    def __setattr__(self, key: str, value: Any) -> None:
        if key not in ("changed", "__editing", "__changed"):
            if hasattr(self, key):
                old_value = getattr(self, key)
                if hasattr(old_value, "changed"):
                    old_value.changed.disconnect(self.change)

            if hasattr(value, "changed"):
                value.changed.connect(self.change)

        object.__setattr__(self, key, value)

