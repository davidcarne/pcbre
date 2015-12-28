__author__ = 'davidc'

from PySide import QtGui

pcbre_filter = "PCBRE Project Files (*.pcbre)"

#class OpenAction(QtGui.QAction):

class SaveAction(QtGui.QAction):
    def __init__(self, window):
        self.window = window
        QtGui.QAction.__init__(self, "Save", self.window, shortcut="Ctrl+S", triggered=self.__action)

    def __action(self):
        self.window.project.save()

class SaveAsDialogAction(QtGui.QAction):
    def __init__(self, window):
        self.window = window
        QtGui.QAction.__init__(self, "Save-As", self.window, shortcut="Ctrl+Shift+S", triggered=self.__action)

    def __action(self):
        filename, _ = QtGui.QFileDialog.getSaveFileName(self.window, "Save project as....", filter=pcbre_filter)

        if filename:
            self.window.project.save(filename, update_path=True)


def checkCloseSave(window):
    # TODO: Add needs save
    needs_save = True

    if needs_save:
        reply = QtGui.QMessageBox.question(window, "Unsaved Project",
                                           "Project is unsaved, are you sure you want to quit? (You will lose work!)",
                                           QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)

        if reply == QtGui.QMessageBox.Yes:
            return True
    else:
        return True

    return False

class ExitAction(QtGui.QAction):

    def __init__(self, window):
        self.window = window
        QtGui.QAction.__init__(self, "E&xit", self.window, shortcut="Ctrl+Q", triggered=self.__action)

    def __action(self):
        # Note - the save check is done in the window closeEvent handler
        self.window.close()


