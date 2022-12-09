__author__ = 'davidc'

from qtpy import QtWidgets

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pcbre.ui.main_gui import MainWindow


class FileMenu(QtWidgets.QMenu):
    def __init__(self, mw: 'MainWindow') -> None:
        QtWidgets.QMenu.__init__(self, "&File", mw)

        # Build the "Add" menu
        self.__menu_add = self.addMenu("Add")

        # TODO: Move the addImage action to the action package
        self.__menu_add.addAction(mw.pcbre_actions.file_add_image)

        # Add the rest of the actions
        self.addSeparator()
        self.addAction(mw.pcbre_actions.file_save)

        self.__menu_save_as = self.addMenu("Save As")
        self.__menu_save_as.addAction(mw.pcbre_actions.file_save_as_packed)
        self.__menu_save_as.addAction(mw.pcbre_actions.file_save_as_dir)
        self.addSeparator()
        self.addAction(mw.pcbre_actions.file_exit)


        # the "save" option is disabled if a) the project hasn't changed
        # or b) the save location isn't defined
        def updateCanSave() -> None:
            mw.pcbre_actions.file_save.setEnabled(mw.can_save)

        # So update the "greyed" state immediately before rendering
        self.aboutToShow.connect(updateCanSave)

