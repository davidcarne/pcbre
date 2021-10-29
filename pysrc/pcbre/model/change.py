from enum import Enum
from typing import Any


class ChangeType(Enum):
    ADD = 1
    CHANGE = 2
    REMOVE = 3


class ModelChange:
    # TODO - need to make this more specific
    def __init__(self, container: Any, what: Any, reason: ChangeType):
        """

        :param container: The object that contains the changed object
        :param what: The changed object
        :param reason: What happened (Object added/removed, object changed)
        :return:
        """
        self.container = container
        self.what = what
        self.reason = reason
