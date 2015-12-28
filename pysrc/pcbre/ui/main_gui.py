#!/usr/bin/python

from PySide import QtCore, QtGui

import pcbre.model.project as P
from pcbre.ui.actions.misc import NudgeUpAction, NudgeLeftAction, NudgeDownAction, NudgeRightAction
from pcbre.ui.actions.pcb import StackupSetupDialogAction, LayerViewSetupDialogAction, RebuildConnectivityAction
from pcbre.ui.actions.save import checkCloseSave
from pcbre.ui.actions.view import LayerJumpAction
from pcbre.ui.dialogs.layeralignmentdialog.dialog import LayerAlignmentDialog
from pcbre.ui.boardviewwidget import BoardViewWidget
from pcbre.ui.panes.info import InfoWidget
from pcbre.ui.panes.layerlist import LayerListWidget
from pcbre.ui.tools.all import TOOLS
from pcbre.ui.widgets.glprobe import probe


class MainWindow(QtGui.QMainWindow):
    def __init__(self, p):
        super(MainWindow, self).__init__()

        self.project = p

        self.viewArea = BoardViewWidget(self.project)
        self.installEventFilter(self.viewArea)

        self.setCentralWidget(self.viewArea)

        #self.createActions()
        self.createToolbars()
        self.createMenus()
        self.createDockWidgets()

        self.setupInvisibleActions()
        self.setWindowTitle("PCB Reversing Suite")


        self.current_tool = None
        self.current_controller = None


    def toolBarChanged(self, bid):
        self.current_tool = self.tool_map[bid]
        controller = self.current_tool.getToolController(self.viewArea)
        self.current_controller = controller
        self.viewArea.setInteractionDelegate(controller)

    def createToolbars(self):
        self.createViewToolbar()
        self.bg = QtGui.QButtonGroup()
        self.bg.setExclusive(True)
        self.bg.buttonClicked.connect(self.toolBarChanged)

        toolbar = self.addToolBar("Tool Selection")

        self.tool_map = {}
        self.current_tool = None

        for n, tt in enumerate(TOOLS):
            tool = tt(self.project)
            toolbutton = tool.getToolButton()
            self.tool_map[toolbutton] = tool

            self.bg.addButton(toolbutton)

            toolbar.addWidget(toolbutton)
            toolbutton.setCheckable(True)

            if n == 0:
                toolbutton.setChecked(True)
                self.toolBarChanged(toolbutton)

    def createLayerSelectionWidget(self):
        dock = LayerListWidget(self.project, self.viewArea.viewState)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        
        dock = InfoWidget(self.project)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        #self.subWindowMenu.addAction(dock.toggleViewAction())

    def createDockWidgets(self):
        self.createLayerSelectionWidget()

    def setupInvisibleActions(self):
        for i in range(0, 9):
            self.addAction(LayerJumpAction(self, i))

        def showToolSettings():
            if self.current_controller:
                self.current_controller.showSettingsDialog()

        a = QtGui.QAction("raise controls", self, triggered=showToolSettings)
        a.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Tab))
        self.addAction(a)
        
        self.addAction(NudgeUpAction(self))
        self.addAction(NudgeDownAction(self))
        self.addAction(NudgeLeftAction(self))
        self.addAction(NudgeRightAction(self))

    def createViewToolbar(self):
        flipX = QtGui.QAction("Flip X", self, triggered=lambda: self.viewArea.viewState.flip(0))
        flipX.setShortcut(QtGui.QKeySequence("f"))
        flipX.setToolTip('f')

        flipY = QtGui.QAction("Flip Y", self, triggered=lambda: self.viewArea.viewState.flip(1))
        flipY.setShortcut(QtGui.QKeySequence("shift+f"))
        flipY.setToolTip('Shift+f')

        def rotater(deg):
            def _():
                self.viewArea.viewState.rotate(deg)
            return _

        self.rotate90L = QtGui.QAction("Rotate 90 (CCW)", self, triggered=rotater(-90))
        self.rotate90L.setShortcut(QtGui.QKeySequence("ctlr+shift+r"))
        self.rotate90L.setToolTip("Ctrl+Shift+r")

        self.rotate90R = QtGui.QAction("Rotate 90 (CW)", self, triggered=rotater(90))
        self.rotate90R.setShortcut(QtGui.QKeySequence("ctrl+r"))
        self.rotate90R.setToolTip("Ctrl+r")

        self.permute = QtGui.QAction("Cycle Image Draw Order", self, triggered=self.viewArea.viewState.permute_layer_order)
        self.permute.setShortcut(QtGui.QKeySequence("]"))
        self.permute.setToolTip("]")

        tb = self.addToolBar("View")
        tb.addAction(flipX)
        tb.addAction(flipY)
        tb.addAction(self.rotate90L)
        tb.addAction(self.rotate90R)
        tb.addAction(self.permute)

        self.flipX = flipX
        self.flipY = flipY






    def closeEvent(self, evt):
        return checkCloseSave(self)


    def createMenus(self):
        pcbMenu = QtGui.QMenu("&PCB")

        pcbMenu.addAction(StackupSetupDialogAction(self))

        pcbMenu.addAction(LayerViewSetupDialogAction(self))

        from pcbre.ui.menu.imageselectionmenu import ImageSelectionMenu

        pcbMenu.addMenu(ImageSelectionMenu(self))

        pcbMenu.addSeparator()

        pcbMenu.addAction(RebuildConnectivityAction(self))


        from pcbre.ui.menu.file import FileMenu
        from pcbre.ui.menu.view import ViewMenu

        self.menuBar().addMenu(FileMenu(self))
        self.menuBar().addMenu(ViewMenu(self))

        self.menuBar().addMenu(pcbMenu)

def main():
    import sys
    import argparse
    import os.path

    # Actually die on signal
    import signal

    import pcbre.version_checks
    pcbre.version_checks.check_pkg_versions()

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    ap = argparse.ArgumentParser()
    ap.add_argument("--create-if-not-exists", action="store_true")
    ap.add_argument("project", nargs='?')
    args = ap.parse_args()

    if args.project is None:
        p = P.Project.create()
    else:
        if os.path.exists(args.project):
            p = P.Project.open(args.project)
        elif args.create_if_not_exists:
            p = P.Project.create()
            p.filepath = args.project
        else:
            print("File not found")
            exit()

    app = QtGui.QApplication(sys.argv)

    version = probe()

    window = MainWindow(p)
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
