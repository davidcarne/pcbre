__author__ = 'davidc'

from PySide2 import QtWidgets


class FileMenu(QtWidgets.QMenu):
    def __init__(self, mw):
        QtWidgets.QMenu.__init__(self, "&File", mw)

        # Build the "Add" menu
        self.__menu_add = self.addMenu("Add")

        # TODO: Move the addImage action to the action package
        self.__menu_add.addAction(mw.actions.file_add_image)

        # Add the rest of the actions
        self.addSeparator()
        self.addAction(mw.actions.file_save)
        self.addAction(mw.actions.file_save_as)
        self.addSeparator()
        self.addAction(mw.actions.file_exit)


        # the "save" option is disabled if a) the project hasn't changed
        # or b) the save location isn't defined
        def updateCanSave():
            mw.actions.file_save.setEnabled(mw.project.can_save)

        # So update the "greyed" state immediately before rendering
        self.aboutToShow.connect(updateCanSave)

