from qtpy import QtGui, QtCore, QtWidgets
import functools
import collections

__author__ = 'davidc'

class UndoStack(QtWidgets.QUndoStack):
    def setup_actions(self, target, menu=None):
        undoAction = self.createUndoAction(target)
        undoAction.setShortcuts(QtGui.QKeySequence.Undo)

        redoAction = self.createRedoAction(target)
        redoAction.setShortcuts(QtGui.QKeySequence.Redo)

        if menu is None:
            target.addAction(undoAction)
            target.addAction(redoAction)
        else:
            pass



class undo_helper_fncall(QtWidgets.QUndoCommand):
    def __init__(self, set_state, *args, **kwargs):
        super(undo_helper_fncall, self).__init__()

        self.new_state = args, kwargs
        self.old_state = None

        self.set_state = set_state

        self._id = -1

    def undo(self):
        args, kwargs = self.old_state
        self.set_state(*args, **kwargs)
        self.old_state = None

    def redo(self):
        args, kwargs = self.new_state
        self.old_state = self.set_state(*args, **kwargs)

    def set_merge_id(self, _id):
        self._id = ((1<<31)-1) & _id

    def id(self):
        return self._id

    def set_merge_fn(self, mf):
        self.mergeWith = functools.partial(mf, self)

class undofunc(object):
    def __new__(cls, *args, **kwargs):
        if len(args) == 1 and isinstance(args[0], collections.Callable):
            self = object.__new__(cls)
            self.__set_state = args[0]
            self.__simple_merge = kwargs.get("simple_merge", False)
            self.merge_check = cls.merge_check_default
            return self
        elif len(args) == 1 and isinstance(args[0], bool):
            return functools.partial(undofunc, simple_merge=args[0])
        else:
            raise ValueError("invalid args to undofunc args=%s kwargs=%s" % (args, kwargs))

    @staticmethod
    def merge_check_default(self, new):
        assert new.id() == self.id()
        assert self.id() != -1
        self.new_state = new.new_state
        return True

    def __call__(self, target, *args, **kwargs):
        self._id = -1
        merge = False
        if "merge" in kwargs and kwargs["merge"]:
            del kwargs["merge"]
            if self.__simple_merge:
                merge = True
            else:
                raise RuntimeError("Tried to merge but can't")

        v = undo_helper_fncall(functools.partial(self.__set_state, target),
                               *args, **kwargs)

        if merge:
            v.set_merge_id(hash((self.__set_state, id(target))))
            v.set_merge_fn(self.merge_check)

        return v

    def merge_check(self, fn):
        self.merge_check = fn
        return self

class undo_set_params(QtWidgets.QUndoCommand):
    def __init__(self, target, **kwargs):
        super(undo_set_params, self).__init__()
        self._id = -1
        if "merge" in kwargs:
            del kwargs["merge"]
            self._id = hash((frozenset(list(kwargs.keys())), id(target))) & ((1<<31) - 1)

        self.target = target
        self.new_state = kwargs
        self.old_state = None



    def redo(self):
        self.old_state = {}
        for k in list(self.new_state.keys()):
            self.old_state[k] = getattr(self.target, k)

        for k, v in list(self.new_state.items()):
            setattr(self.target, k, v)

    def undo(self):
        for k, v in list(self.old_state.items()):
            setattr(self.target, k, v)
        self.old_state = None

    def id(self):
        return self._id

def sig(*args, **kwargs):
    return args, kwargs
