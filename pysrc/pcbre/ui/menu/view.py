from qtpy import QtWidgets

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pcbre.ui.main_gui as MG

class ViewMenu(QtWidgets.QMenu):
    def __init__(self, mw: 'MG.MainWindow') -> None:
        QtWidgets.QMenu.__init__(self, "&View", mw)

        self.subWindowMenu = self.addMenu("Sub-Windows")
        self.addSeparator()
        self.addAction(mw.pcbre_actions.view_rotate_l)
        self.addAction(mw.pcbre_actions.view_rotate_r)
        self.addAction(mw.pcbre_actions.view_flip_x)
        self.addAction(mw.pcbre_actions.view_flip_y)
        self.addAction(mw.pcbre_actions.view_cycle_draw_order)

        self.addSeparator()

        self.addAction(mw.pcbre_actions.view_set_mode_trace)
        self.addAction(mw.pcbre_actions.view_set_mode_cad)

        def update_sub():
            mw.pcbre_actions.view_set_mode_trace.update_from_prop()
            mw.pcbre_actions.view_set_mode_cad.update_from_prop()

        self.aboutToShow.connect(update_sub)



