#!/usr/bin/python

from PySide import QtCore, QtGui

from pcbre.model.imagelayer import ImageLayer
import pcbre.model.project as P
from pcbre.ui.dialogs.layeralignmentdialog.dialog import LayerAlignmentDialog
import pcbre.ui.dialogs.stackupsetup
import pcbre.ui.dialogs.layerviewsetup
from pcbre.ui.boardviewwidget import BoardViewWidget
from pcbre.ui.panes.info import InfoWidget
from pcbre.ui.panes.layerlist import LayerListWidget
from pcbre.ui.tools.all import TOOLS
from pcbre.ui.widgets.glprobe import probe
from pcbre.ui.widgets.imageselectionmenu import ImageSelectionMenu


class MainWindow(QtGui.QMainWindow):
    def __init__(self, p):
        super(MainWindow, self).__init__()

        self.project = p

        self.viewArea = BoardViewWidget(self.project)
        self.installEventFilter(self.viewArea)

        self.setCentralWidget(self.viewArea)

        self.createActions()
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
        self.subWindowMenu.addAction(dock.toggleViewAction())

    def createDockWidgets(self):
        self.createLayerSelectionWidget()

    def save(self):
        self.project.save()

    def saveAs(self):
        filename, _ =QtGui.QFileDialog.getSaveFileName(self, "Save project as....", filter="PCBRE Project Files (*.pcbre)")
        if filename is not None:
            print("Saving to %s" % filename)
            self.project.save(filename, update_path=True)


    def createActions(self):


        self.exitAct = QtGui.QAction("E&xit", self, shortcut="Ctrl+Q",
                triggered=self.close)

        self.saveAction = QtGui.QAction("Save", self, shortcut="Ctrl+S",
                triggered=self.save)

        self.saveAsAction = QtGui.QAction("Save-As", self, shortcut="Ctrl+Shift+S",
                                        triggered=self.saveAs)

        self.editStackup = QtGui.QAction("Edit Stackup", self,
                triggered=self.doStackupSetup)

        self.rebuildConnectivity = QtGui.QAction("Rebuild Connectivity", self,
                                         triggered=self.project.artwork.rebuild_connectivity)

        self.editLayerViews = QtGui.QAction("Edit Stackup/Imagery pairing", self,
                                         triggered=self.doLayerviewSetup)


    def setupInvisibleActions(self):
        self.setupLayerSelection()

        def showToolSettings():
            if self.current_controller:
                self.current_controller.showSettingsDialog()

        a = QtGui.QAction("raise controls", self, triggered=showToolSettings)
        a.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Tab))
        self.addAction(a)

        def nudge(dx, dy):
            pos = QtGui.QCursor.pos()
            QtGui.QCursor.setPos(pos.x() + dx, pos.y() + dy)

        a = QtGui.QAction("nudge left", self, triggered=lambda: nudge(-1, 0))
        a.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Left))
        self.addAction(a)

        a = QtGui.QAction("nudge right", self, triggered=lambda: nudge(1, 0))
        a.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Right))
        self.addAction(a)

        a = QtGui.QAction("nudge up", self, triggered=lambda: nudge(0, -1))
        a.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Up))
        self.addAction(a)

        a = QtGui.QAction("nudge down", self, triggered=lambda: nudge(0, 1))
        a.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Down))
        self.addAction(a)



    def setupLayerSelection(self):
        def _act(arg):
            selected_layer = arg - 1
            if selected_layer >= len(self.project.stackup.layers):
                return

            self.viewArea.viewState.current_layer = self.project.stackup.layers[selected_layer]

        for i in range(0, 10):
            # Closure
            def fn(i):
                a = QtGui.QAction("layer %d" % i, self, triggered=lambda: _act(i))
                a.setShortcut(QtGui.QKeySequence("%d" % i))
                self.addAction(a)
            fn(i)


    def createViewToolbar(self):
        flipX = QtGui.QAction("Flip X", self, triggered=lambda: self.viewArea.viewState.flip(0))
        flipX.setShortcut(QtGui.QKeySequence("f"))

        flipY = QtGui.QAction("Flip Y", self, triggered=lambda: self.viewArea.viewState.flip(1))
        flipY.setShortcut(QtGui.QKeySequence("shift+f"))

        def rotater(deg):
            def _():
                self.viewArea.viewState.rotate(deg)
            return _

        self.rotate90L = QtGui.QAction("Rotate 90 (CCW)", self, triggered=rotater(-90))
        self.rotate90L.setShortcut(QtGui.QKeySequence("ctlr+shift+r"))

        self.rotate90R = QtGui.QAction("Rotate 90 (CW)", self, triggered=rotater(90))
        self.rotate90R.setShortcut(QtGui.QKeySequence("ctrl+r"))

        tb = self.addToolBar("View")
        tb.addAction(flipX)
        tb.addAction(flipY)
        tb.addAction(self.rotate90L)
        tb.addAction(self.rotate90R)

        self.flipX = flipX
        self.flipY = flipY



    def doStackupSetup(self):
        dlg = pcbre.ui.dialogs.stackupsetup.StackupSetupDialog(self, self.project)
        dlg.exec_()

    def doLayerviewSetup(self):
        dlg = pcbre.ui.dialogs.layerviewsetup.LayerViewSetupDialog(self, self.project)
        dlg.exec_()


    def addImage(self):
        fname, _ = QtGui.QFileDialog.getOpenFileName(self, "Open Image")

        if not fname:
            return

        il = ImageLayer.fromFile(self.project, fname)

        # Allow the user to align the image
        dlg = LayerAlignmentDialog(self, self.project, il)
        res = dlg.exec_()
        if res == QtGui.QDialog.Accepted:
            self.project.imagery.add_imagelayer(il)


    def createMenus(self):


        fileMenu = QtGui.QMenu("&File", self)
        subMenuAdd = fileMenu.addMenu("Add")
        act = QtGui.QAction("Image", self, triggered=self.addImage)
        subMenuAdd.addAction(act)

        fileMenu.addSeparator()
        fileMenu.addAction(self.saveAction)
        fileMenu.addAction(self.saveAsAction)
        fileMenu.addSeparator()
        fileMenu.addAction(self.exitAct)

        def updateCanSave():
            self.saveAction.setEnabled(self.project.can_save)

        fileMenu.aboutToShow.connect(updateCanSave)

        helpMenu = QtGui.QMenu("&Help", self)

        self.viewMenu = QtGui.QMenu("&View", self)
        self.subWindowMenu = self.viewMenu.addMenu("Sub-Windows")
        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.rotate90L)
        self.viewMenu.addAction(self.rotate90R)
        self.viewMenu.addAction(self.flipX)
        self.viewMenu.addAction(self.flipY)

        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.rotate90L)

        # Show Imagery Checkbox
        show_images = QtGui.QAction("Show Imagery", self)

        def change_show_images():
            self.viewArea.viewState.show_images = show_images.isChecked()

        show_images.setCheckable(True)
        show_images.setChecked(True)
        show_images.triggered.connect(change_show_images)
        self.viewMenu.addAction(show_images)

        # Show Other Images Checkbox
        other_layers = QtGui.QAction("Show Other Layers artwork", self)

        def change_other_layers():
            self.viewArea.viewState.draw_other_layers = other_layers.isChecked()

        other_layers.setCheckable(True)
        other_layers.setChecked(True)
        other_layers.triggered.connect(change_other_layers)
        self.viewMenu.addAction(other_layers)

        pcbMenu = QtGui.QMenu("&PCB")
        pcbMenu.addAction(self.editStackup)
        pcbMenu.addAction(self.editLayerViews)

        lsm = ImageSelectionMenu(self.project)
        lsm.setTitle("Edit image alignment")
        def m(action):
            ly = action.data()
            dlg = LayerAlignmentDialog(self, self.project, ly)
            dlg.exec_()
        lsm.triggered.connect(m)
        pcbMenu.addMenu(lsm)
        pcbMenu.addSeparator()


        pcbMenu.addAction(self.rebuildConnectivity)



        self.menuBar().addMenu(fileMenu)
        self.menuBar().addMenu(helpMenu)
        self.menuBar().addMenu(self.viewMenu)

        self.menuBar().addMenu(pcbMenu)

def main():
    import sys
    import argparse
    import os.path

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
