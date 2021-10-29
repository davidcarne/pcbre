import time

from pcbre.ui.dialogs.layerviewsetup import LayerViewSetupDialog
from pcbre.ui.dialogs.stackupsetup import StackupSetupDialog

__author__ = 'davidc'

from qtpy import QtWidgets

from typing import Optional


class StackupSetupDialogAction(QtWidgets.QAction):
    def __init__(self, window: QtWidgets.QMainWindow) -> None:
        self.__window = window
        QtWidgets.QAction.__init__(self, "Edit Stackup", window)
        self.triggered.connect(self.__action)

    def __action(self) -> None:
        dlg = StackupSetupDialog(self.__window, self.__window.project)
        dlg.exec_()


class RebuildConnectivityAction(QtWidgets.QAction):
    def __init__(self, window: QtWidgets.QMainWindow) -> None:
        self.__window = window

        QtWidgets.QAction.__init__(self, "Rebuild Connectivity", window)
        self.triggered.connect(self.__action)

    class CancelException(Exception):
        pass

    def __action(self) -> None:
        self.__pd : Optional[QtWidgets.QProgressDialog]= None

        try:
            self.__window.project.artwork.rebuild_connectivity(progress_cb=self.__progress)
        except RebuildConnectivityAction.CancelException:
            pass

        if self.__pd is not None:
            self.__pd.close()

    def __progress(self, now_v: int, prg_max: int) -> None:
        now = time.time()

        if self.__pd is None:
            self.__pd_last_evt = now
            self.__pd = QtWidgets.QProgressDialog("Rebuilding Connectivity....", "Cancel", 0, prg_max, self.__window)
            self.__pd.show()

        elif now - self.__pd_last_evt > 0.05:
            self.__pd_last_evt = now
            QtWidgets.QApplication.processEvents()

        if self.__pd.wasCanceled():
            raise RebuildConnectivityAction.CancelException()

        self.__pd.setValue(now_v)


class LayerViewSetupDialogAction(QtWidgets.QAction):
    def __init__(self, window: QtWidgets.QMainWindow) -> None:
        self.__window = window
        QtWidgets.QAction.__init__(self, "Edit Stackup/Imagery pairing", self.__window)
        self.triggered.connect(self.__action)

    def __action(self) -> None:
        dlg = LayerViewSetupDialog(self.__window, self.__window.project)
        dlg.exec_()
