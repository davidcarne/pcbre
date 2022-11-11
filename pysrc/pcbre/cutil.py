# Console utilities
from pcbre.ui.boardviewwidget import BoardViewWidget


def get_selected_one(view: BoardViewWidget):
    l = list(view.selectionList)
    if len(l) == 1:
        return l[0]
    return None

def get_selected(view: BoardViewWidget):
    l = list(view.selectionList)
    return l

