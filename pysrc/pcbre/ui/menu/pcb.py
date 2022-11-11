from typing import TYPE_CHECKING

from qtpy import QtWidgets

from pcbre.ui.menu.imageselectionmenu import ImageSelectionMenu

if TYPE_CHECKING:
    from pcbre.ui.main_gui import MainWindow


class PCBMenu(QtWidgets.QMenu):
    def __init__(self, pw: 'MainWindow') -> None:
        super(PCBMenu, self).__init__("&PCB", pw)

        self.addAction(pw.pcbre_actions.pcb_stackup_setup_dialog)
        self.addAction(pw.pcbre_actions.pcb_layer_view_setup_dialog)
        self.addSeparator()

        self.ism = ImageSelectionMenu(pw)
        self.addMenu(self.ism)
        self.addSeparator()
        self.addAction(pw.pcbre_actions.pcb_rebuild_connectivity)
