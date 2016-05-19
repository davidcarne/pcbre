from pcbre import units
from pcbre.matrix import Point2, Rect
from pcbre.model.component import Component
from pcbre.model.const import OnSide, IntersectionClass
from pcbre.model.pad import Pad
from pcbre.model.component import Component

__author__ = 'davidc'

class DIPComponent(Component):
    ISC = IntersectionClass.NONE

    def __init__(self, center, theta, side, side_layer_oracle, pin_count, pin_space, pin_width, pad_size=units.MM):
        Component.__init__(self, center, theta, side, side_layer_oracle=side_layer_oracle)
        self.__my_init(pin_count, pin_space, pin_width, pad_size, side_layer_oracle)

    def __my_init(self, pin_count, pin_space, pin_width, pad_size, side_layer_oracle):
        # Center and theta don't affect the pin settings

        self.__pin_count = pin_count
        self.__pin_space = pin_space
        self.__pin_width = pin_width
        self.__pad_size = pad_size

        self._project = None

        self.__pins_cache = []

    @property
    def on_sides(self):
        return OnSide.Both

    def __update(self):
        if self.__pins_cache:
            return

        assert self.__pin_count % 2 == 0

        edge_count = self.__pin_count // 2

        pin_edge = self.__pin_space * (edge_count - 1)
        pin_edge_center_delta = pin_edge / 2

        for i in range(self.__pin_count):
            dx = (i % edge_count) * self.__pin_space

            if i < self.__pin_count / 2:
                x = -self.__pin_width/2
                y = pin_edge_center_delta - dx
            else:
                x = self.__pin_width/2
                y = -pin_edge_center_delta + dx

            center = Point2(x,y)
            newpad = Pad(self, "%s" % (i + 1), center, 0, self.__pad_size, self.__pad_size, th_diam=500)
            self.__pins_cache.append(newpad)

    @property
    def pin_count(self):
        return self.__pin_count

    @pin_count.setter
    def pin_count(self, value):
        assert value % 2 == 0
        self.__invalidate()
        self.__pin_count = value

    @property
    def pin_space(self):
        return self.__pin_space

    @pin_space.setter
    def pin_space(self, value):
        self.__invalidate()
        self.__pin_space = value

    @property
    def pin_width(self):
        return self.__pin_width

    @property
    def pad_size(self):
        return self.__pad_size

    @pin_width.setter
    def pin_width(self, value):
        self.__invalidate()
        self.__pin_width = value

    def get_pads(self):
        self.__update()
        return self.__pins_cache

    def body_width(self):
        return self.pin_width - 0.055 * units.IN

    def body_length(self):
        return (self.pin_count // 2 - 1) * self.pin_space + 0.158 * units.IN

    @property
    def theta_bbox(self):
        return Rect.fromCenterSize(Point2(0,0), self.body_width(), self.body_length())

    def serializeTo(self, dip_msg):
        self._serializeTo(dip_msg.common)

        m = dip_msg.dip

        m.pinCount = self.pin_count
        m.pinSpace = self.pin_space
        m.pinWidth = self.pin_width
        m.padSize = self.pad_size

    @staticmethod
    def deserialize(project, dip_msg):
        m = dip_msg.dip
        cmp = DIPComponent.__new__(DIPComponent)
        Component.deserializeTo(project, dip_msg.common, cmp)
        cmp.__my_init(m.pinCount, m.pinSpace, m.pinWidth, m.padSize, project)
        return cmp

