from qtpy import QtWidgets

class ViewMenu(QtWidgets.QMenu):
    def __init__(self, mw):
        QtWidgets.QMenu.__init__(self, "&View", mw)

        self.subWindowMenu = self.addMenu("Sub-Windows")
        self.addSeparator()
        self.addAction(mw.actions.view_rotate_l)
        self.addAction(mw.actions.view_rotate_r)
        self.addAction(mw.actions.view_flip_x)
        self.addAction(mw.actions.view_flip_y)
        self.addAction(mw.actions.view_cycle_draw_order)

        self.addSeparator()

        self.addAction(mw.actions.view_toggle_show_imagery)
        self.addAction(mw.actions.view_toggle_draw_other_layers)

        def update_sub():
            mw.actions.view_toggle_show_imagery.update_from_prop()
            mw.actions.view_toggle_draw_other_layers.update_from_prop()

        self.aboutToShow.connect(update_sub)


