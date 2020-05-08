__author__ = 'davidc'

from enum import Enum


class ChangeType(Enum):
    ADD = 1
    CHANGE = 2
    REMOVE = 3


class ModelChange:
    def __init__(self, container, what, reason):
        """

        :param container: The object that contains the changed object
        :param what: The changed object
        :param reason: What happened (Object added/removed, object changed)
        :return:
        """
        self.container = container
        self.what = what
        self.reason = reason
