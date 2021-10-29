from qtpy import QtWidgets


class DebugMenu(QtWidgets.QMenu):
    def __init__(self, mw: QtWidgets.QMainWindow) -> None:
        QtWidgets.QMenu.__init__(self, "&Debug", mw)

        self.addAction(mw.debug_actions.debug_draw)
        self.addAction(mw.debug_actions.debug_draw_bbox)
        self.addAction(mw.debug_actions.debug_log_action_history)

        def update_sub() -> None:
            mw.debug_actions.debug_draw.update_from_prop()
            mw.debug_actions.debug_draw_bbox.update_from_prop()

        self.aboutToShow.connect(update_sub)
