from qtpy import QtWidgets

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pcbre.ui.main_gui import MainWindow


class DebugMenu(QtWidgets.QMenu):
    def __init__(self, mw: 'MainWindow') -> None:
        QtWidgets.QMenu.__init__(self, "&Debug", mw)

        self.addAction(mw.debug_actions.debug_draw)
        self.addAction(mw.debug_actions.debug_draw_bbox)
        self.addAction(mw.debug_actions.debug_log_action_history)
        self.addAction(mw.debug_actions.debug_throw_exception)

        def update_sub() -> None:
            mw.debug_actions.debug_draw.update_from_prop()
            mw.debug_actions.debug_draw_bbox.update_from_prop()

        self.aboutToShow.connect(update_sub)
