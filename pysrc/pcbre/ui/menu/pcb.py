__author__ = 'davidc'

from PySide import QtGui
from pcbre.ui.menu.imageselectionmenu import ImageSelectionMenu

class PCBMenu(QtGui.QMenu):

    def __init__(self, pw):
        QtGui.QMenu.__init__(self, "&PCB")
        self.addAction(pw.actions.pcb_stackup_setup_dialog)
        self.addAction(pw.actions.pcb_layer_view_setup_dialog)
        self.addMenu(ImageSelectionMenu(pw))
        self.addSeparator()
        self.addAction(pw.actions.pcb_rebuild_connectivity)