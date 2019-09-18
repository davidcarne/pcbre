from qtpy import QtWidgets

class EditMenu(QtWidgets.QMenu):
    def __init__(self, mw):
        QtWidgets.QMenu.__init__(self, "&Edit", mw)

        self.addSeparator()
        self.addAction(mw.actions.undo)
        self.addAction(mw.actions.redo)
        self.addSeparator()

        # Cut/Copy/Paste

        #def update_sub():
        #    mw.actions.undo.update_from_prop()
        #    mw.actions.redo.update_from_prop()

        #self.aboutToShow.connect(update_sub)



