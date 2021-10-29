import itertools

from qtpy import QtWidgets

from pcbre.model.imagelayer import ImageLayer
from pcbre.ui.dialogs.layeralignmentdialog.dialog import LayerAlignmentDialog

__author__ = 'davidc'


class AddImageDialogAction(QtWidgets.QAction):
    """
    This action shows a QT file selection dialog; and then adds an image to the project
    """

    def __init__(self, window):
        self.window = window
        QtWidgets.QAction.__init__(self, "Image", self.window)
        self.triggered.connect(self.__action)

    def __action(self):

        # Build a filter string
        known_image_types = [('Windows Bitmaps', ['*.bmp', '*.dib']),
                             ('JPEG files', ['*.jpg', '*.jpeg']),
                             ('JPEG2K files', ['*.jp2']),
                             ('PNG Files', ['*.png']),
                             ('Portable Image Format files', ['*.pbm', '*.pgm', '*.ppm']),
                             ('TIFF files', ['*.tiff', '*.tif'])
                             ]

        known_image_types.insert(0, ('All Images',
                                     list(itertools.chain.from_iterable(i[1] for i in known_image_types))))

        filter_string = ";;".join("%s (%s)" % (i[0], " ".join(i[1])) for i in known_image_types)

        fname, _ = QtWidgets.QFileDialog.getOpenFileName(self.window, "Open Image", filter=filter_string, options=QtWidgets.QFileDialog.Options())

        if not fname:
            return

        il = ImageLayer.fromFile(self.window.project, fname)

        # Allow the user to align the image
        dlg = LayerAlignmentDialog(self.window, self.window.project, il)
        res = dlg.exec_()
        if res == QtWidgets.QDialog.Accepted:
            self.window.project.imagery.add_imagelayer(il)
