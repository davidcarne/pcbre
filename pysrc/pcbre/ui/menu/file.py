__author__ = 'davidc'

from PySide import QtGui

class FileMenu(QtGui.QMenu):
    def __init__(self, mw):
        QtGui.QMenu.__init__(self, "&File", mw)

        # Build the "Add" menu
        self.__menu_add = self.addMenu("Add")

        # TODO: Move the addImage action to the action package
        act = QtGui.QAction("Image", mw, triggered=mw.addImage)
        self.__menu_add.addAction(act)

        # Add the rest of the actions
        self.addSeparator()
        self.addAction(mw.saveAction)
        self.addAction(mw.saveAsAction)
        self.addSeparator()
        self.addAction(mw.exitAct)


        # the "save" option is disabled if a) the project hasn't changed
        # or b) the save location isn't defined
        def updateCanSave():
            mw.saveAction.setEnabled(mw.project.can_save)

        # So update the "greyed" state immediately before rendering
        self.aboutToShow.connect(updateCanSave)

