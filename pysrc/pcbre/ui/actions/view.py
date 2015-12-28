__author__ = 'davidc'

from PySide import QtGui

class LayerJumpAction(QtGui.QAction):
    def __init__(self, window, layer_no):
        self.__layer = layer_no
        self.window = window

        QtGui.QAction.__init__(self, "layer %d" % layer_no, window, triggered=self.__action)
        self.setShortcut(QtGui.QKeySequence("%d" % (layer_no+1)))

    def __action(self):
        if self.__layer >= len(self.window.project.stackup.layers):
            return

        self.window.viewArea.viewState.current_layer = self.window.project.stackup.layers[self.__layer]
