#!/usr/bin/python

from qtpy import QtCore, QtGui, QtWidgets

import pcbre.model.project as P
from pcbre.ui.actions.add import AddImageDialogAction
from pcbre.ui.actions.debug import ToggleDrawBBoxAction, ToggleDrawDebugAction
from pcbre.ui.actions.misc import NudgeUpAction, NudgeLeftAction, NudgeDownAction, NudgeRightAction, \
    ShowToolSettingsAction
from pcbre.ui.actions.pcb import RebuildConnectivityAction, LayerViewSetupDialogAction, StackupSetupDialogAction
from pcbre.ui.actions.save import checkCloseSave
from pcbre.ui.actions.view import LayerJumpAction, FlipXAction, FlipYAction, RotateLAction, CycleDrawOrderAction, \
    RotateRAction, SetModeTraceAction, SetModeCADAction, CycleModeAction
from pcbre.ui.boardviewwidget import BoardViewWidget
from pcbre.ui.panes.info import InfoWidget
from pcbre.ui.panes.layerlist import LayerListWidget
from pcbre.ui.panes.undostack import UndoDock
from pcbre.ui.tools.all import TOOLS
from pcbre.ui.widgets.glprobe import probe
from pcbre.ui.actions.save import SaveAction, SaveAsDialogAction, ExitAction


class DebugActions:
    def __init__(self, window):
        self.debug_draw = ToggleDrawDebugAction(window, window.viewArea)
        self.debug_draw_bbox = ToggleDrawBBoxAction(window, window.viewArea)

class MainWindowActions:
    def __init__(self, window):
        # File actions
        self.file_add_image = AddImageDialogAction(window)
        self.file_save = SaveAction(window)
        self.file_save_as = SaveAsDialogAction(window)
        self.file_exit = ExitAction(window)

        # View actions
        self.view_flip_x = FlipXAction(window)
        self.view_flip_y = FlipYAction(window)
        self.view_rotate_l = RotateLAction(window)
        self.view_rotate_r = RotateRAction(window)
        self.view_cycle_draw_order = CycleDrawOrderAction(window)

        self.view_set_mode_trace = SetModeTraceAction(window, window.viewArea)
        self.view_set_mode_cad = SetModeCADAction(window, window.viewArea)

        self.undo = window.undo_stack.createUndoAction(window)
        self.undo.setShortcut(QtGui.QKeySequence.Undo)
        self.redo = window.undo_stack.createRedoAction(window)
        self.redo.setShortcut(QtGui.QKeySequence.Redo)


        # PCB Actions
        self.pcb_stackup_setup_dialog = StackupSetupDialogAction(window)
        self.pcb_layer_view_setup_dialog = LayerViewSetupDialogAction(window)
        self.pcb_rebuild_connectivity = RebuildConnectivityAction(window)

        # Invisible actions - don't need to save these
        for i in range(0, 9):
            window.addAction(LayerJumpAction(window, i))

        window.addAction(ShowToolSettingsAction(window))

        window.addAction(NudgeUpAction(window))
        window.addAction(NudgeDownAction(window))
        window.addAction(NudgeLeftAction(window))
        window.addAction(NudgeRightAction(window))

        window.addAction(CycleModeAction(window, window.viewArea))

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, p):
        super(MainWindow, self).__init__()

        self.project = p

        self.viewArea = BoardViewWidget(self.project)
        self.installEventFilter(self.viewArea)

        self.undo_stack = QtWidgets.QUndoStack()

        self.undo_stack.indexChanged.connect(self.viewArea.update)

        self.actions = MainWindowActions(self)
        self.debug_actions = DebugActions(self)

        self.setCentralWidget(self.viewArea)

        self.createToolbars()
        self.createMenubar()
        self.createDockWidgets()

        self.setWindowTitle("PCB Reversing Suite")


        self.current_tool = None
        self.current_controller = None


    def submitCommand(self, cmd):
        self.undo_stack.push(cmd)

    def toolBarChanged(self, bid):
        self.current_tool = self.tool_map[bid]
        controller = self.current_tool.getToolController(self.viewArea, self.submitCommand)
        self.current_controller = controller
        self.viewArea.setInteractionDelegate(controller)
        self.viewArea.setFocus()

    def createToolbars(self):
        self.createViewToolbar()
        self.bg = QtWidgets.QButtonGroup()
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


        dock = UndoDock(self.undo_stack)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        
        dock = InfoWidget(self.project)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        #self.subWindowMenu.addAction(dock.toggleViewAction())

    def createDockWidgets(self):
        self.createLayerSelectionWidget()


    def createViewToolbar(self):
        tb = self.addToolBar("View")
        tb.addAction(self.actions.view_flip_x)
        tb.addAction(self.actions.view_flip_y)
        tb.addAction(self.actions.view_rotate_l)
        tb.addAction(self.actions.view_rotate_r)
        tb.addAction(self.actions.view_cycle_draw_order)

    def closeEvent(self, evt):
        if checkCloseSave(self):
            evt.accept()
        else:
            evt.ignore()


    def createMenubar(self):
        from pcbre.ui.menu.file import FileMenu
        from pcbre.ui.menu.edit import EditMenu
        from pcbre.ui.menu.view import ViewMenu
        from pcbre.ui.menu.pcb import PCBMenu

        from pcbre.ui.menu.debug import DebugMenu

        self.menuBar().addMenu(FileMenu(self))
        self.menuBar().addMenu(EditMenu(self))
        self.menuBar().addMenu(ViewMenu(self))
        self.menuBar().addMenu(PCBMenu(self))

        # TODO: Only show menu if started in debug mode
        self.menuBar().addMenu(DebugMenu(self))

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

    app = QtWidgets.QApplication(sys.argv)

    gl_version = probe()

    window = MainWindow(p)
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
