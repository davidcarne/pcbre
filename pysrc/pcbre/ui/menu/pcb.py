__author__ = 'davidc'

from qtpy import QtWidgets
from pcbre.ui.menu.imageselectionmenu import ImageSelectionMenu

class PCBMenu(QtWidgets.QMenu):

    def __init__(self, pw):
        super(PCBMenu, self).__init__("&PCB", pw)

        self.addAction(pw.actions.pcb_stackup_setup_dialog)
        self.addAction(pw.actions.pcb_layer_view_setup_dialog)
        self.addMenu(ImageSelectionMenu(pw))
        self.addSeparator()
        self.addAction(pw.actions.pcb_rebuild_connectivity)
