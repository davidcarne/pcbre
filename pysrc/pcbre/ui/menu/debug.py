from PySide import QtGui

class DebugMenu(QtGui.QMenu):
    def __init__(self, mw):
        QtGui.QMenu.__init__(self, "&Debug", mw)

        self.addAction(mw.debug_actions.debug_draw)
        self.addAction(mw.debug_actions.debug_draw_bbox)

        def update_sub():
            mw.debug_actions.debug_draw.update_from_prop()
            mw.debug_actions.debug_draw_bbox.update_from_prop()

        self.aboutToShow.connect(update_sub)
