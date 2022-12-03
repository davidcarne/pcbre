from pcbre import units
from pcbre.matrix import Point2, Rect
from pcbre.model.const import OnSide, IntersectionClass, SIDE
from pcbre.model.pad import Pad
from pcbre.model.component import Component
from pcbre.matrix import Vec2

from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from pcbre.model.project import Project

__author__ = 'davidc'


class SIPComponent(Component):
    ISC = IntersectionClass.NONE

    def __init__(self, project: 'Project',
                 center: Vec2, theta: float, side: SIDE, 
                 side_layer_oracle: 'Project',
                 pin_count: int, 
                 pin_space: int, pad_size: int) -> None:

        Component.__init__(self, project, center, theta, side,
                           side_layer_oracle=side_layer_oracle)
        self._my_init(pin_count, pin_space, pad_size)

    def _my_init(self, pin_count: int, pin_space: float, pad_size: float) -> None:
        self.__pin_count = pin_count
        self.__pin_space = pin_space
        self.__pad_size = pad_size
        self.__pins_cache : List[Pad] = []

    @property
    def on_sides(self) -> OnSide:
        return OnSide.Both

    def __update(self) -> None:
        if self.__pins_cache:
            return

        edge_count = self.__pin_count

        pin_edge = self.__pin_space * (edge_count - 1)
        pin_edge_center_delta = pin_edge / 2

        for i in range(self.__pin_count):
            dx = (i % edge_count) * self.__pin_space

            x = 0
            y = pin_edge_center_delta - dx

            center = Point2(x, y)
            newpad = Pad(self, "%s" % (i + 1), center, 0, self.__pad_size, self.__pad_size, th_diam=500)
            self.__pins_cache.append(newpad)

    @property
    def pin_count(self) -> int:
        return self.__pin_count

    @property
    def pin_space(self) -> float:
        return self.__pin_space

    @property
    def pad_size(self) -> float:
        return self.__pad_size

    def get_pads(self) -> List[Pad]:
        self.__update()
        return self.__pins_cache

    def body_width(self) -> float:
        return self.pad_size + 0.158 * units.IN

    def body_length(self) -> float:
        return (self.pin_count - 1) * self.pin_space + 0.158 * units.IN

    @property
    def theta_bbox(self) -> Rect:
        return Rect.from_center_size(Point2(0, 0), self.body_width(), self.body_length())



class DIPComponent(Component):
    ISC = IntersectionClass.NONE

    def __init__(self, 
        project: 'Project', center: 'Vec2', theta: float,
        side: SIDE, side_layer_oracle: 'Project', pin_count: int, 
        pin_space: float, pin_width:float, pad_size: float=units.MM):

        Component.__init__(self, project, center, theta, side, side_layer_oracle=side_layer_oracle)
        self._my_init(pin_count, pin_space, pin_width, pad_size, side_layer_oracle)

    def _my_init(self, pin_count: int, pin_space: float,
        pin_width: float, pad_size: float, side_layer_oracle: 'Project') -> None:

        # Center and theta don't affect the pin settings

        self.__pin_count = pin_count
        self.__pin_space = pin_space
        self.__pin_width = pin_width
        self.__pad_size = pad_size


        self.__pins_cache : List[Pad] = []

    @property
    def on_sides(self) -> OnSide:
        return OnSide.Both

    def __update(self) -> None:
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

            center = Point2(x, y)
            newpad = Pad(self, "%s" % (i + 1), center, 0, self.__pad_size, self.__pad_size, th_diam=500)
            self.__pins_cache.append(newpad)

    def __invalidate(self) -> None:
        self.__pins_cache = []

    @property
    def pin_count(self) -> int:
        return self.__pin_count

    @pin_count.setter
    def pin_count(self, value: int) -> None:
        assert value % 2 == 0
        self.__invalidate()
        self.__pin_count = value

    @property
    def pin_space(self) -> float:
        return self.__pin_space

    @pin_space.setter
    def pin_space(self, value: float) -> None:
        self.__invalidate()
        self.__pin_space = value

    @property
    def pin_width(self) -> float:
        return self.__pin_width

    @pin_width.setter
    def pin_width(self, value: float) -> None:
        self.__invalidate()
        self.__pin_width = value

    @property
    def pad_size(self) -> float:
        return self.__pad_size

    def get_pads(self) -> List[Pad]:
        self.__update()
        return self.__pins_cache

    def body_width(self) -> float:
        return self.pin_width - 0.055 * units.IN

    def body_length(self) -> float:
        return (self.pin_count // 2 - 1) * self.pin_space + 0.158 * units.IN

    @property
    def theta_bbox(self) -> Rect:
        return Rect.from_center_size(Point2(0, 0), self.body_width(), self.body_length())

