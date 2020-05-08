import math
from pcbre.matrix import rotate, Vec2, Point2, Rect, projectPoint
from pcbre.model.component import Component
from pcbre.model.const import OnSide, IntersectionClass
from pcbre.model.pad import Pad


__author__ = 'davidc'


class SMD4Component(Component):
    ISC = IntersectionClass.NONE

    def __init__(self,
                 center, theta, side, side_layer_oracle,
                 side1_pins, side2_pins, side3_pins, side4_pins,
                 dim_1_body, dim_1_pincenter, dim_2_body, dim_2_pincenter,
                 pin_contact_length, pin_contact_width, pin_spacing):

        Component.__init__(self, center, theta, side, side_layer_oracle=side_layer_oracle)
        self.side_pins = [side1_pins, side2_pins, side3_pins, side4_pins]

        # Y Dimensions (along pin 1 edge
        self.dim_1_body = dim_1_body
        self.dim_1_pincenter = dim_1_pincenter

        # X dimensions
        self.dim_2_body = dim_2_body
        self.dim_2_pincenter = dim_2_pincenter

        self.pin_contact_length = pin_contact_length
        self.pin_contact_width = pin_contact_width
        self.pin_spacing = pin_spacing

        self.__pins_cache = []

        self._project = None

    @property
    def on_sides(self):
        return OnSide.One

    @property
    def pin_count(self):
        return sum(self.side_pins)

    def __update(self):
        if self.__pins_cache:
            return

        pads = []

        d_2_pc = self.dim_2_pincenter / 2
        d_1_pc = self.dim_1_pincenter / 2
        overall_pin_no = 0

        for i, side_pin_count in enumerate(self.side_pins):
            offset = (side_pin_count - 1) / 2 * self.pin_spacing
            pad_theta = math.pi/2 * i
            if i == 0:
                start = Point2(-d_2_pc, offset)
                step = Vec2(0, -self.pin_spacing)
            elif i == 1:
                start = Point2(-offset, -d_1_pc)
                step = Vec2(self.pin_spacing, 0)
            elif i == 2:
                start = Point2(d_2_pc, -offset)
                step = Vec2(0, self.pin_spacing)
            elif i == 3:
                start = Point2(offset, d_1_pc)
                step = Vec2(-self.pin_spacing, 0)

            for pin_no in range(side_pin_count):
                pin_center = start + step * pin_no
                pads.append(
                    Pad(self, "%s" % (overall_pin_no + 1), pin_center, pad_theta, self.pin_spacing / 2, self.pin_contact_length,
                        side=self.side))
                overall_pin_no += 1

        self.__pins_cache = pads

    @property
    def theta_bbox(self):
        if self.side_pins[0] or self.side_pins[2]:
            x_axis = self.dim_2_pincenter + self.pin_contact_length + self.pin_contact_width * 2
        else:
            x_axis = self.dim_2_body

        if self.side_pins[1] or self.side_pins[3]:
            y_axis = self.dim_1_pincenter + self.pin_contact_length + self.pin_contact_width * 2
        else:
            y_axis = self.dim_1_body

        return Rect.fromCenterSize(Point2(0, 0), x_axis, y_axis)

    def point_inside(self, pt):
        v = pt - self.center
        v_in_cmp = projectPoint(rotate(-self.theta), v)
        return self.theta_bbox.point_test(v_in_cmp)

    def get_pads(self):
        self.__update()
        return self.__pins_cache

    def serializeTo(self, cmp_msg):
        self._serializeTo(cmp_msg.common)
        cmp_msg.init("smd4")
        t = cmp_msg.smd4
        t.dim1Body = int(self.dim_1_body)
        t.dim1PinEdge = int(self.dim_1_pincenter)

        t.dim2Body = int(self.dim_2_body)
        t.dim2PinEdge = int(self.dim_2_pincenter)

        t.pinContactLength = int(self.pin_contact_length)
        t.pinContactWidth = int(self.pin_contact_width)
        t.pinSpacing = int(self.pin_spacing)

        t.side1Pins = self.side_pins[0]
        t.side2Pins = self.side_pins[1]
        t.side3Pins = self.side_pins[2]
        t.side4Pins = self.side_pins[3]

    @staticmethod
    def deserialize(project, msg):
        t = msg.smd4
        cmp = SMD4Component(
                None, None, None, project,
                t.side1Pins, t.side2Pins, t.side3Pins, t.side4Pins,
                t.dim1Body, t.dim1PinEdge, t.dim2Body, t.dim2PinEdge,
                t.pinContactLength, t.pinContactWidth, t.pinSpacing)

        Component.deserializeTo(project, msg.common, cmp)
        return cmp
