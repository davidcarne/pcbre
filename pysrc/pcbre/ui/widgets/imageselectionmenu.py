from pcbre.model.imagelayer import ImageLayer

__author__ = 'davidc'


from PySide import QtCore, QtGui

class ImageSelectionMenu(QtGui.QMenu):
    def __init__(self, model):
        """

        :type model: pcbre.model.project.Project
        :param model:
        :return:
        """
        
        super(ImageSelectionMenu, self).__init__()

        self.model = model
        self.aboutToShow.connect(self.recreate)

    def recreate(self):
        self.clear()

        def __wrap(ly):
            return lambda: self.__changed(ly)

        for ly in self.model.imagery.imagelayers:
            a = self.addAction(ly.name)
            a.setData(ly)
