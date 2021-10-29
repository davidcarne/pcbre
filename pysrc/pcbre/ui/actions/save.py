__author__ = 'davidc'

from qtpy import QtWidgets

pcbre_filter = "PCBRE Project Files (*.pcbre)"


class SaveAction(QtWidgets.QAction):
    def __init__(self, window: QtWidgets.QMainWindow) -> None:
        self.window = window
        QtWidgets.QAction.__init__(self, "Save", self.window)
        self.setShortcut("Ctrl+S")
        self.triggered.connect(self.__action)

    def __action(self) -> None:
        self.window.project.save()


class SaveAsDialogAction(QtWidgets.QAction):
    def __init__(self, window: QtWidgets.QMainWindow) -> None:
        self.window = window
        QtWidgets.QAction.__init__(self, "Save-As", self.window)
        self.triggered.connect(self.__action)
        self.setShortcut("Ctrl+Shift+S")

    def __action(self) -> None:
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.window, "Save project as....", filter=pcbre_filter)

        if filename:
            self.window.project.save(filename, update_path=True)


def checkCloseSave(window: QtWidgets.QMainWindow) -> bool:
    # TODO: Add needs save
    needs_save = True

    if not needs_save:
        return True

    reply = QtWidgets.QMessageBox.question(window, "Unsaved Project",
                                           "Project is unsaved, are you sure you want to quit? (You will lose work!)",
                                           QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

    return reply == QtWidgets.QMessageBox.Yes


class ExitAction(QtWidgets.QAction):

    def __init__(self, window: QtWidgets.QMainWindow) -> None:
        self.window = window
        QtWidgets.QAction.__init__(self, "E&xit", self.window)
        self.setShortcut("Ctrl+Q")
        self.triggered.connect(self.__action)

    def __action(self) -> None:
        # Note - the save check is done in the window closeEvent handler
        self.window.close()
