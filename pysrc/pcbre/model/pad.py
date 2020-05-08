from pcbre.model.artwork_geom import Trace
from pcbre.model.const import IntersectionClass, TFF
from pcbre.matrix import rotate, translate, Point2, Rect, projectPoint
import numpy.linalg

__author__ = 'davidc'


def lazyprop(fn):
    attr_name = '_lazy_' + fn.__name__
    @property
    def _lazyprop(self):
        try:
            return getattr(self, attr_name)
        except AttributeError:
            pass

        val = fn(self)
        setattr(self, attr_name, val)
        return val

    return _lazyprop


# Pads aren't serialized to the DB; Ephemeral
class Pad(object):
    """ Pads are sub
    """
    ISC = IntersectionClass.PAD
    TYPE_FLAGS = TFF.HAS_GEOM | TFF.HAS_NET

    def __init__(self, parent, pad_no, rel_center, theta, width, length, th_diam=0, side=None):
        """
        :param parent: Parent
        :param rel_center:
        :type rel_center: Point2
        :param theta:
        :param w:
        :param l:
        :param r:
        :return:
        """
        self.parent = parent

        self.__rel_center = rel_center

        # Cached translation-only location matrix
        self.__translate_mat = translate(self.__rel_center.x, self.__rel_center.y)
        self.__theta = theta

        self.width = width
        self.length = length

        self.side = side

        # Throughhole diameter, 0 if not T/H
        self.th_diam = th_diam

        self.pad_no = pad_no

        if self.parent is not None:
            pmat = self.parent.matrix
        else:
            pmat = numpy.identity(3, dtype=numpy.float32)

        self.__pmat = pmat

        self.center = projectPoint(pmat, self.__rel_center)

        self.layer = self.parent._side_layer_oracle.stackup.layer_for_side(self.side)

    @lazyprop
    def __p2p_mat(self):
        return rotate(-self.theta).dot(translate(-self.rel_center.x, -self.rel_center.y))

    @lazyprop
    def __inv_p2p_mat(self):
        return translate(self.rel_center.x, self.rel_center.y).dot(rotate(self.theta))

    @lazyprop
    def pad_to_world_matrix(self):
        return self.__pmat.dot(self.__inv_p2p_mat)

    @lazyprop
    def world_to_pad_matrix(self):
        return self.__p2p_mat.dot(numpy.linalg.inv(self.__pmat))

    @lazyprop
    def trace_repr(self):
        return self.__get_trace_repr()

    @lazyprop
    def trace_rel_repr(self):
        return self.__get_rel_trace_repr()

    @lazyprop
    def bbox(self):
        longest_dim = max(self.w, self.l)
        return Rect.fromCenterSize(self.center, longest_dim, longest_dim)

    def get_poly_repr(self):
        return self.trace_repr.get_poly_repr()

    @property
    def net(self):
        return self.parent.net_for_pad_no(self.pad_no)

    @net.setter
    def net(self, value):
        self.parent.set_net_for_pad_no(self.pad_no, value)

    @property
    def pad_name(self):
        return self.parent.pin_name_for_no("%s" % self.pad_no)

    @pad_name.setter
    def pad_name(self, value):
        self.parent.set_pin_name_for_no("%s" % self.pad_no, value)

    @property
    def rel_center(self):
        return self.__rel_center

    @property
    # numpy mat creation is expensive. Use cached
    def translate_mat(self):
        return self.__translate_mat

    @property
    def theta(self):
        return self.__theta

    def __get_unrot_trace_points(self):
        if self.l > self.w:
            length = self.l - self.w
            width = self.w
            p0 = Point2(length/2, 0)
            p1 = Point2(-length/2, 0)
        else:
            length = self.w - self.l
            width = self.l
            p0 = Point2(0, length/2)
            p1 = Point2(0, -length/2)

        return width, p0, p1

    def __get_rel_trace_repr(self):
        w, p0, p1 = self.__get_unrot_trace_points()

        p0 = Point2.fromHomol(self.__inv_p2p_mat.dot(p0.homol()))
        p1 = Point2.fromHomol(self.__inv_p2p_mat.dot(p1.homol()))
        return Trace(p0, p1, w, self.layer)

    def __get_trace_repr(self):
        w, p0, p1 = self.__get_unrot_trace_points()

        p0 = Point2.fromHomol(self.pad_to_world_matrix.dot(p0.homol()))
        p1 = Point2.fromHomol(self.pad_to_world_matrix.dot(p1.homol()))
        return Trace(p0, p1, w, self.layer)

    def pad_to_world(self, pt):
        return Point2.fromHomol(self.pad_to_world_matrix.dot(pt.homol()))

    def world_to_pad(self, pt):
        pt = Point2(pt)
        return Point2.fromHomol(self.world_to_pad_matrix.dot(pt.homol()))

    def is_through(self):
        return self.th_diam > 0
