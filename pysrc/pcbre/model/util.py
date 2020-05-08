__author__ = 'davidc'


class ImmutableSetProxy:
    def __init__(self, parent):
        self.parent = parent

    def __iter__(self):
        return self.parent.__iter__()

    def __len__(self):
        return self.parent.__len__()


class ImmutableListProxy:
    def __init__(self, parent):
        self.parent = parent

    def __getitem__(self, item):
        return self.parent.__getitem__(item)

    def __iter__(self):
        return self.parent.__iter__()

    def __len__(self):
        return self.parent.__len__()

    def index(self, k):
        return self.parent.index(k)
