#!/usr/bin/python

from typing import Dict, Optional
import tempfile

from qtpy import QtCore, QtGui, QtWidgets

import pcbre.model.project as P
from pcbre.model.project import Project
from pcbre.model.stackup import Layer
from pcbre.ui.actions.add import AddImageDialogAction
from pcbre.ui.actions.debug import ToggleDrawBBoxAction, ToggleDrawDebugAction, ToggleActionInformation
from pcbre.ui.actions.misc import NudgeUpAction, NudgeLeftAction, NudgeDownAction, NudgeRightAction, \
    ShowToolSettingsAction
from pcbre.ui.actions.pcb import RebuildConnectivityAction, LayerViewSetupDialogAction, StackupSetupDialogAction
from pcbre.ui.actions.save import SaveAction, SaveAsDialogAction, ExitAction
from pcbre.ui.actions.save import checkCloseSave
from pcbre.ui.actions.view import LayerJumpAction, FlipXAction, FlipYAction, RotateLAction, CycleDrawOrderAction, \
    RotateRAction, SetModeTraceAction, SetModeCADAction, CycleModeAction, ZoomFitAction, HideDrawnGeometry
from pcbre.ui.boardviewwidget import BoardViewWidget
from pcbre.ui.panes.console import ConsoleWidget
from pcbre.ui.panes.info import InfoWidget
from pcbre.ui.panes.layerlist import LayerListWidget
from pcbre.ui.panes.undostack import UndoDock
from pcbre.ui.tools.all import TOOLS
from pcbre.ui.tools.basetool import BaseTool, BaseToolController
from pcbre.ui.widgets.glprobe import probe


class DebugActions:
    def __init__(self, window: BoardViewWidget) -> None:
        self.debug_draw = ToggleDrawDebugAction(window, window.viewArea)
        self.debug_draw_bbox = ToggleDrawBBoxAction(window, window.viewArea)
        self.debug_log_action_history = ToggleActionInformation(window, window.viewArea)


class MainWindowActions:
    def __init__(self, window: BoardViewWidget) -> None:
        # File actions
        self.file_add_image = AddImageDialogAction(window)
        self.file_save = SaveAction(window)
        self.file_save_as = SaveAsDialogAction(window)
        self.file_exit = ExitAction(window)

        # View actions
        vs = window.viewArea.viewState
        self.view_flip_x = FlipXAction(window, vs)
        self.view_flip_y = FlipYAction(window, vs)
        self.view_rotate_l = RotateLAction(window, vs)
        self.view_rotate_r = RotateRAction(window, vs)
        self.view_cycle_draw_order = CycleDrawOrderAction(window)

        self.view_zoom_fit = ZoomFitAction(window, vs, window.viewArea.get_visible_point_cloud)
        self.view_hide_trace_geom = HideDrawnGeometry(window, window.viewArea.boardViewState)

        self.view_set_mode_trace = SetModeTraceAction(window, window.viewArea.boardViewState)
        self.view_set_mode_cad = SetModeCADAction(window, window.viewArea.boardViewState)

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

        window.addAction(CycleModeAction(window, window.viewArea.boardViewState))


class MainWindow(QtWidgets.QMainWindow):
    # Emitted when something changes the currently selected layer

    def __init__(self, p: Project) -> None:
        super(MainWindow, self).__init__()

        self.project: Project = p

        self.viewArea = BoardViewWidget(self.project)
        self.installEventFilter(self.viewArea)

        self.undo_stack = QtWidgets.QUndoStack()

        self.undo_stack.indexChanged.connect(self.viewArea.update)

        self.pcbre_actions = MainWindowActions(self)
        self.debug_actions = DebugActions(self)

        self.setCentralWidget(self.viewArea)

        self.createToolbars()
        self.createMenubar()
        self.createDockWidgets()

        self.setWindowTitle("PCB Reversing Suite")

        self.current_tool: Optional[BaseTool] = None
        self.current_controller: Optional[BaseToolController] = None

    @QtCore.Slot(object)
    def changeViewLayer(self, layer: Layer) -> None:
        """Change the selected view layer"""
        assert layer in self.project.stackup.layers

        self.viewArea.boardViewState.current_layer = layer

    def submitCommand(self, cmd: QtWidgets.QUndoCommand) -> None:
        self.undo_stack.push(cmd)

    def toolBarChanged(self, bid: int) -> None:
        self.current_tool = self.tool_map[bid]
        controller = self.current_tool.getToolController(self.viewArea, self.submitCommand)
        self.current_controller = controller
        self.viewArea.setInteractionDelegate(controller)
        self.viewArea.setFocus()

    def createToolbars(self) -> None:
        self.createViewToolbar()
        self.bg = QtWidgets.QButtonGroup()
        self.bg.setExclusive(True)
        self.bg.buttonClicked.connect(self.toolBarChanged)

        toolbar = self.addToolBar("Tool Selection")

        self.tool_map: Dict[int, BaseTool] = {}
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

    def createDockWidgets(self) -> None:
        # TODO: make this modular, remember view state

        dock = LayerListWidget(self, self.project, self.viewArea.boardViewState)
        # dock.hide()
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        self._view_menu.subWindowMenu.addAction(dock.toggleViewAction())

        dock = ConsoleWidget(self.project, self.viewArea)
        dock.hide()
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, dock)
        self._view_menu.subWindowMenu.addAction(dock.toggleViewAction())

        dock = UndoDock(self.undo_stack)
        # dock.hide()
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        self._view_menu.subWindowMenu.addAction(dock.toggleViewAction())

        dock = InfoWidget(self.project)
        dock.hide()
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        self._view_menu.subWindowMenu.addAction(dock.toggleViewAction())

    def createViewToolbar(self) -> None:
        tb = self.addToolBar("View")
        tb.addAction(self.pcbre_actions.view_flip_x)
        tb.addAction(self.pcbre_actions.view_flip_y)
        tb.addAction(self.pcbre_actions.view_rotate_l)
        tb.addAction(self.pcbre_actions.view_rotate_r)
        tb.addAction(self.pcbre_actions.view_cycle_draw_order)

    def closeEvent(self, evt: QtCore.QEvent) -> None:
        if checkCloseSave(self):
            evt.accept()
        else:
            evt.ignore()

    def createMenubar(self) -> None:
        from pcbre.ui.menu.file import FileMenu
        from pcbre.ui.menu.edit import EditMenu
        from pcbre.ui.menu.view import ViewMenu
        from pcbre.ui.menu.pcb import PCBMenu

        from pcbre.ui.menu.debug import DebugMenu

        self.menuBar().addMenu(FileMenu(self))
        self.menuBar().addMenu(EditMenu(self))
        self._view_menu = ViewMenu(self)
        self.menuBar().addMenu(self._view_menu)
        self.menuBar().addMenu(PCBMenu(self))

        # TODO: Only show menu if started in debug mode
        self.menuBar().addMenu(DebugMenu(self))

def main() -> None:
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

    old_excepthook = sys.excepthook
    def excepthook(type, value, traceback):
        print("Crashing. Attempting emergency save")
        emerge_save_path = None
        if p.filepath is not None:
            # Create an emergency save filepath based on existing path
            emerge_save_path = p.filepath
            if emerge_save_path.endswith(".pcbre"):
                emerge_save_path = emerge_save_path[:-6]
            emerge_save_path += ".emergency.pcbre"

            # If it doesn't exist, try and open it
            if not os.path.exists(emerge_save_path):
                try:
                    emerge_save_fd = open(emerge_save_path, "wb")
                except IOError:
                    emerge_save_path = None
            else:
                emerge_save_path = None

        # If none of the above worked, create a tempfile
        if emerge_save_path is None:
            emerge_save_fd = tempfile.NamedTemporaryFile("wb",
                suffix=".pcbre", prefix="pcbre_unnamed_emergency_save", delete=False)
            emerge_save_path = emerge_save_fd.name

        p.save_fd(emerge_save_fd)
        emerge_save_fd.close()
        print("Saved emergency save to %s" % emerge_save_path)
        old_excepthook(type, value, traceback)
        exit(1)

    sys.excepthook = excepthook

    app = QtWidgets.QApplication(sys.argv)

    f = app.font()

    gl_version = probe()

    window = MainWindow(p)
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
