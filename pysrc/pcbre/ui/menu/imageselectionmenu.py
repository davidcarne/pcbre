from pcbre.model.imagelayer import ImageLayer
from pcbre.ui.dialogs.layeralignmentdialog.dialog import LayerAlignmentDialog

__author__ = 'davidc'


from qtpy import QtCore, QtWidgets

class ImageSelectionMenu(QtWidgets.QMenu):
    def __init__(self, window):
        """

        :type model: pcbre.model.project.Project
        :param model:
        :return:
        """
        
        super(ImageSelectionMenu, self).__init__()

        self.window = window

        self.aboutToShow.connect(self.recreate)

        self.setTitle("Edit image alignment")

        self.triggered.connect(self.__triggered)

    def __triggered(self, action):
        ly = action.data()
        dlg = LayerAlignmentDialog(self.window, self.window.project, ly)
        dlg.exec_()

    def recreate(self):
        self.clear()

        def __wrap(ly):
            return lambda: self.__changed(ly)

        for ly in self.window.project.imagery.imagelayers:
            a = self.addAction(ly.name)
            a.setData(ly)
