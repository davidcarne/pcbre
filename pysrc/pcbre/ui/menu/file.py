from pcbre.ui.actions.add import AddImageDialogAction
from pcbre.ui.actions.save import SaveAction, SaveAsDialogAction, ExitAction

__author__ = 'davidc'

from PySide import QtGui


class FileMenu(QtGui.QMenu):
    def __init__(self, mw):
        QtGui.QMenu.__init__(self, "&File", mw)

        # Build the "Add" menu
        self.__menu_add = self.addMenu("Add")

        # TODO: Move the addImage action to the action package
        self.__menu_add.addAction(AddImageDialogAction(mw))

        # Add the rest of the actions
        self.addSeparator()
        self.__save = SaveAction(mw)
        self.addAction(self.__save)
        self.addAction(SaveAsDialogAction(mw))
        self.addSeparator()
        self.addAction(ExitAction(mw))


        # the "save" option is disabled if a) the project hasn't changed
        # or b) the save location isn't defined
        def updateCanSave():
            self.__save.setEnabled(mw.project.can_save)

        # So update the "greyed" state immediately before rendering
        self.aboutToShow.connect(updateCanSave)

