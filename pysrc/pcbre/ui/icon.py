from qtpy import QtCore, QtGui

import pkg_resources

class Icon(QtGui.QIcon):
    def __init__(self, icon_name: str) -> None:
        super(Icon, self).__init__()
        filename = pkg_resources.resource_filename('pcbre.resources', '%s.svg' % icon_name)
        self.addFile(filename)
