from pcbre.ui.dialogs.layeralignmentdialog.dialog import LayerAlignmentDialog

__author__ = 'davidc'

from qtpy import QtWidgets

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pcbre.ui.main_gui import MainWindow


class ImageSelectionMenu(QtWidgets.QMenu):
    def __init__(self, window: 'MainWindow') -> None:
        super(ImageSelectionMenu, self).__init__()

        self._window = window

        self.aboutToShow.connect(self.recreate)

        self.setTitle("Edit image alignment")

        self.triggered.connect(self.__triggered)

    def __triggered(self, action: QtWidgets.QAction) -> None:
        ly = action.data()
        dlg = LayerAlignmentDialog(self._window, self._window.project, ly)
        dlg.exec_()

    def recreate(self) -> None:
        self.clear()

        for ly in self._window.project.imagery.imagelayers:
            a = self.addAction(ly.name)
            a.setData(ly)
