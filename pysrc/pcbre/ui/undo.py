import functools
from typing import Callable, List, Dict, Tuple, Optional, TYPE_CHECKING, Any, Union

from qtpy import QtGui, QtWidgets

if TYPE_CHECKING:
    from pcbre.model.project import Project
    from pcbre.model.artwork import InsertableGeomComponent


class UndoStateError(Exception):
    pass


class UndoStack(QtWidgets.QUndoStack):
    def setup_actions(self, target: QtWidgets.QDialog) -> None:
        undo_action = self.createUndoAction(target)
        undo_action.setShortcuts(QtGui.QKeySequence.Undo)

        redo_action = self.createRedoAction(target)
        redo_action.setShortcuts(QtGui.QKeySequence.Redo)

        target.addAction(undo_action)
        target.addAction(redo_action)


class UndoMerge(QtWidgets.QUndoCommand):
    def __init__(self, project: 'Project', artwork: 'Union[InsertableGeomComponent, List[InsertableGeomComponent]]', desc: str) -> None:
        super(UndoMerge, self).__init__(desc)

        if isinstance(artwork, list):
            self.artwork: List['InsertableGeomComponent'] = artwork
        else:
            self.artwork = [artwork]

        self.project = project

    def redo(self) -> None:
        for i in self.artwork:
            self.project.artwork.merge(i)

    def undo(self) -> None:
        for i in reversed(self.artwork):
            self.project.artwork.remove(i)


SigType = Tuple[Tuple[Any, ...], Dict[str, Any]]
CallableType = Callable[..., SigType]


class UndoHelperFnCall(QtWidgets.QUndoCommand):
    def __init__(self,
                 set_state: CallableType,
                 *args: Any, **kwargs: Dict[str, Any]) -> None:

        super(UndoHelperFnCall, self).__init__()

        self.new_state: Optional[SigType] = (args, kwargs)
        self.old_state: Optional[SigType] = None

        self.set_state: CallableType = set_state

    def undo(self) -> None:
        if self.old_state is None:
            raise UndoStateError("Attempted to call undo on non-done action")

        args, kwargs = self.old_state
        self.set_state(*args, **kwargs)
        self.old_state = None

    def redo(self) -> None:
        if self.new_state is None:
            raise UndoStateError("Attempted to call redo on done action")

        args, kwargs = self.new_state
        self.old_state = self.set_state(*args, **kwargs)


class UndoFunc(object):
    def __init__(self, set_state: CallableType) -> None:
        self.__set_state = set_state

    def __call__(self, target: Any, *args: Any, **kwargs: Dict[str, Any]) -> Any:
        return UndoHelperFnCall(functools.partial(self.__set_state, target),
                                *args, **kwargs)


def sig(*args: Any, **kwargs: Dict[str, Any]) -> SigType:
    return args, kwargs
