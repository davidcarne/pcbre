import re


class Net:
    __net_class_match = re.compile(r"N\$\d+")

    def __init__(self, name=None, net_class=""):
        self._name = name
        self.net_class = net_class

        # Assigned during add
        self._id = -1
        self._project = None

    @property
    def name(self):
        if self._name:
            return self._name
        else:
            return "N$%d" % self._id

    @name.setter
    def name(self, value):
        if Net.__net_class_match.match(value) or value.strip() == "":
            self._name = None
        else:
            self._name = value

    def __repr__(self):
        return "<Net %s %s %s>" % (self._id, self.name, ("(%s)" % self.net_class) if self.net_class else "")
