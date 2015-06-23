from enum import Enum
from pcbre.matrix import Vec2, Rect
from pcbre.model.const import OnSide
from pcbre.model.pad import Pad

__author__ = 'davidc'

from .component import Component

# Not just passives
# Also LEDs, Diodes,
# Pretty much any 2 terminal device
class PassiveSymType(Enum):
    TYPE_RES = 0
    TYPE_CAP = 1
    TYPE_CAP_POL = 2
    TYPE_IND  = 3
    TYPE_DIODE = 4

class PassiveBodyType(Enum):
    CHIP = 0
    TH_AXIAL = 1
    TH_RADIAL = 2

class PassiveComponent(Component):
    def __init__(self, center, theta, side,
                 sym_type, body_type, pin_d, body_corner_vec, pin_corner_vec,
                 side_layer_oracle=None):
        super(PassiveComponent, self).__init__(center, theta, side, side_layer_oracle=side_layer_oracle)

        self.sym_type = sym_type
        self.body_type = body_type

        # Distance from center to pin
        self.pin_d = pin_d

        self.body_corner_vec = body_corner_vec
        self.pin_corner_vec = pin_corner_vec

        self.__pads = []

    def __update_pads(self):
        if self.__pads:
            return

        v = Vec2.fromPolar(0, self.pin_d)
        td = 1 if self.body_type in (PassiveBodyType.TH_AXIAL, PassiveBodyType.TH_RADIAL) else 0

        if td:
            y = x = self.pin_corner_vec.x *2
        else:
            y = self.pin_corner_vec.y * 2
            x = self.pin_corner_vec.x * 2


        self.__pads = [
            Pad(self, 1, v, 0, y, x, td, self.side),
            Pad(self, 2, -v, 0, y, x, td, self.side),
        ]

    def get_pads(self):
        self.__update_pads()
        return self.__pads

    def on_sides(self):
        return OnSide.One if self.body_type == PassiveBodyType.CHIP else OnSide.Both

    @property
    def theta_bbox(self):
        l = max(self.pin_d + self.pin_corner_vec.x, self.body_corner_vec.x)
        w = max(self.pin_corner_vec.y, self.body_corner_vec.y)
        return Rect.fromCenterSize(self.center, l * 2, w * 2)

    def serializeTo(self, msg):
        pass



