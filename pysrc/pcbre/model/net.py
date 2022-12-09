import re
from typing import Optional
from pcbre.model.serialization import PersistentID, PersistentIDClass

import pcbre.model.project


class Net:
    __net_class_match = re.compile(r"N\$\d+")

    def __init__(self, unique_id: PersistentID, name: Optional[str] = None, net_class: str = "")  -> None:
        self._name = name
        self.__unique_id : PersistentID = unique_id
        self.net_class = net_class

        # Assigned during add
        self._id = -1
        self._project: Optional['pcbre.model.project.Project'] = None

    @property
    def unique_id(self) -> PersistentID:
        return self.__unique_id

    @property
    def name(self) -> str:
        if self._name:
            return self._name
        else:
            return "N$%d" % self._id

    @name.setter
    def name(self, value: Optional[str]) -> None:
        if value is None:
            self._name = None
        elif value.strip() == "":
            self._name = None
        else:
            self._name = value

    @property
    def has_assigned_name(self):
        return self._name is not None

    def __repr__(self) -> str:
        return "<Net %s %s %s>" % (self._id, self.name, ("(%s)" % self.net_class) if self.net_class else "")
