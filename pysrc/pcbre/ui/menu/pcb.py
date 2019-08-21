__author__ = 'davidc'

from PySide2 import QtWidgets
from pcbre.ui.menu.imageselectionmenu import ImageSelectionMenu

class PCBMenu(QtWidgets.QMenu):

    def __init__(self, pw):
        QtWidgets.QMenu.__init__(self, "&PCB")
        self.addAction(pw.actions.pcb_stackup_setup_dialog)
        self.addAction(pw.actions.pcb_layer_view_setup_dialog)
        self.addMenu(ImageSelectionMenu(pw))
        self.addSeparator()
        self.addAction(pw.actions.pcb_rebuild_connectivity)
