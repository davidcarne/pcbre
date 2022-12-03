from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from pcbre.matrix import Vec2, Rect, Point2
from pcbre.model.const import OnSide, IntersectionClass
from pcbre.model.pad import Pad

if TYPE_CHECKING:
    from pcbre.model.project import Project
    from pcbre.model.const import SIDE

__author__ = 'davidc'

from .component import Component


# Not just passives
# Also LEDs, Diodes,
# Pretty much any 2 terminal device
class PassiveSymType(Enum):
    TYPE_RES = 0
    TYPE_CAP = 1
    TYPE_CAP_POL = 2
    TYPE_IND = 3
    TYPE_DIODE = 4


class Passive2BodyType(Enum):
    CHIP = 0
    SMD_CAP = 3  # SMD Electrolytic capacitor (pana?)

    TH_AXIAL = 1
    TH_RADIAL = 2
    TH_FLIPPED_CAP = 4  # radial capacitor laid down on its side, with


class Passive2Component(Component):
    ISC = IntersectionClass.NONE

    def __init__(self,
                 project: 'Project',
                 center: Vec2, theta: float, side: 'SIDE',
                 sym_type: PassiveSymType,
                 body_type: Passive2BodyType,
                 pin_d: int, body_corner_vec: Vec2, pin_corner_vec: Vec2,
                 side_layer_oracle: Optional['Project'] = None):
        super(Passive2Component, self).__init__(project, center, theta, side, side_layer_oracle=side_layer_oracle)

        self.sym_type: PassiveSymType = sym_type
        self.body_type: Passive2BodyType = body_type

        # Distance from center to pin
        self.pin_d: int = pin_d

        self.body_corner_vec: Vec2 = body_corner_vec
        self.pin_corner_vec: Vec2 = pin_corner_vec

        self._pads: List[Pad] = []

    def __update_pads(self) -> None:
        if self._pads:
            return

        v = Vec2.from_polar(0, self.pin_d)
        td = 0.1 if self.body_type in (Passive2BodyType.TH_AXIAL, Passive2BodyType.TH_RADIAL) else 0

        if td:
            y = x = self.pin_corner_vec.x * 2
        else:
            y = self.pin_corner_vec.y * 2
            x = self.pin_corner_vec.x * 2

        self._pads = [
            Pad(self, "1", v, 0, y, x, td, self.side),
            Pad(self, "2", -v, 0, y, x, td, self.side),
        ]

    def get_pads(self) -> List[Pad]:
        self.__update_pads()
        return self._pads

    def on_sides(self) -> OnSide:
        return OnSide.One if self.body_type == Passive2BodyType.CHIP else OnSide.Both

    @property
    def theta_bbox(self) -> Rect:
        length = max(self.pin_d + self.pin_corner_vec.x, self.body_corner_vec.x)
        width = max(self.pin_corner_vec.y, self.body_corner_vec.y)
        return Rect.from_center_size(Point2(0, 0), length * 2, width * 2)
