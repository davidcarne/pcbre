__author__ = 'davidc'

from qtpy import QtWidgets
from pcbre.model.project import StorageType

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pcbre.ui.main_gui import MainWindow

pcbre_filter = "PCBRE Project Files (*.pcbre)"

pcbre_dir_filter = "PCBRE VCS Dir"

class SaveAction(QtWidgets.QAction):
    def __init__(self, window: 'MainWindow') -> None:
        self.window = window
        QtWidgets.QAction.__init__(self, "Save", self.window)
        self.setShortcut("Ctrl+S")
        self.triggered.connect(self.__action)

    def __action(self) -> None:
        self.window.project.save(self.window.filepath, self.window.storage_type)


class SaveAsDialogAction(QtWidgets.QAction):
    def __init__(self, window: 'MainWindow', st: StorageType) -> None:
        self.window = window
        QtWidgets.QAction.__init__(self, "%s" % st.name, self.window)
        self.triggered.connect(self.__action)

        self.storage_type = st

    def __action(self) -> None:
        if self.storage_type == StorageType.Packed:
            filter = pcbre_filter
        else:
            filter = pcbre_dir_filter

        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(self.window, "Save project as....", filter=filter)

        if filepath:
            self.window.project.save(filepath, self.storage_type)
            self.window.storage_type = self.storage_type
            self.window.filepath = filepath


def checkCloseSave(window: 'MainWindow') -> bool:
    # TODO: Add needs save
    needs_save = True

    if not needs_save:
        return True

    reply = QtWidgets.QMessageBox.question(window, "Unsaved Project",
                                           "Project is unsaved, are you sure you want to quit? (You will lose work!)",
                                           QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

    return reply == QtWidgets.QMessageBox.Yes


class ExitAction(QtWidgets.QAction):

    def __init__(self, window: 'MainWindow') -> None:
        self.window = window
        QtWidgets.QAction.__init__(self, "E&xit", self.window)
        self.setShortcut("Ctrl+Q")
        self.triggered.connect(self.__action)

    def __action(self) -> None:
        # Note - the save check is done in the window closeEvent handler
        self.window.close()
