from pcbre.model.artwork_geom import Trace
from pcbre.model.const import IntersectionClass, TFF, SIDE
from pcbre.matrix import rotate, translate, Point2, Rect, project_point, Vec2
from pcbre.model.artwork_geom import Geom

import numpy.linalg

from typing import Optional, Callable, Any, Tuple, TYPE_CHECKING
if TYPE_CHECKING:
    from pcbre.model.component import Component
    from pcbre.model.net import Net
    from pcbre.model.artwork_geom import ShapelyPolygon
    from pcbre.model.stackup import Layer
    import numpy
    import numpy.typing as npt

__author__ = 'davidc'



def lazyprop(fn: Callable[[Any], Any]) -> property:
    attr_name = '_lazy_' + fn.__name__

    def _lazyprop(self: Any) -> Any:
        try:
            return getattr(self, attr_name)
        except AttributeError:
            pass

        val = fn(self)
        setattr(self, attr_name, val)
        return val

    return property(_lazyprop)


# Pads aren't serialized to the DB; Ephemeral
class Pad(Geom):
    """ Pads are sub
    """
    ISC = IntersectionClass.PAD
    TYPE_FLAGS = TFF.HAS_GEOM | TFF.HAS_NET

    def __init__(self, 
                 parent: 'Component',
                 pad_no: str, 
                 rel_center: Vec2, 
                 theta: float,
                 width: float,
                 length: float,
                 th_diam: float = 0,
                 side: Optional[SIDE]=None):
        super(Pad, self).__init__()

        if side is None:
            side = SIDE.Top
        assert side is not None

        self.parent: 'Component' = parent

        self.__rel_center: Vec2 = rel_center

        # Cached translation-only location matrix
        self.__translate_mat = translate(self.__rel_center.x, self.__rel_center.y)
        self.__theta: float = theta

        self.width: float = width
        self.length: float = length

        self.side: SIDE = side

        # Throughhole diameter, 0 if not T/H
        self.th_diam : float = th_diam

        self.pad_no : str = pad_no

        if self.parent is not None:
            pmat : 'npt.NDArray[numpy.float64]' = self.parent.matrix
        else:
            pmat = numpy.identity(3, dtype=numpy.float32)

        self.__pmat : 'npt.NDArray[numpy.float64]' = pmat

        self.center = project_point(pmat, self.__rel_center)

        self.layer : 'Layer' = self.parent._side_layer_oracle.stackup.layer_for_side(self.side)

    @lazyprop
    def __p2p_mat(self) -> 'npt.NDArray[numpy.float64]':
        return rotate(-self.theta) @ translate(-self.rel_center.x, -self.rel_center.y)

    @lazyprop
    def __inv_p2p_mat(self) -> 'npt.NDArray[numpy.float64]':
        return translate(self.rel_center.x, self.rel_center.y) @ rotate(self.theta)

    @lazyprop
    def pad_to_world_matrix(self) -> 'npt.NDArray[numpy.float64]':
        return self.__pmat @ self.__inv_p2p_mat # type: ignore

    @lazyprop
    def world_to_pad_matrix(self) -> 'npt.NDArray[numpy.float64]':
        return self.__p2p_mat @ numpy.linalg.inv(self.__pmat) # type: ignore

    @lazyprop
    def trace_repr(self) -> Trace:
        return self.__get_trace_repr()

    @lazyprop
    def trace_rel_repr(self) -> Trace:
        return self.__get_rel_trace_repr()

    @property
    def bbox(self) -> Rect:
        longest_dim = max(self.width, self.length)
        return Rect.from_center_size(self.center, longest_dim, longest_dim)

    def get_poly_repr(self) -> 'ShapelyPolygon':
        return self.trace_repr.get_poly_repr()

    @property
    def net(self) -> Optional['Net']:
        return self.parent.net_for_pad_no(self.pad_no)

    @net.setter
    def net(self, value: 'Net') -> None:
        self.parent.set_net_for_pad_no(self.pad_no, value)

    @property
    def pad_name(self) -> str:
        return self.parent.pin_name_for_no("%s" % self.pad_no)

    @pad_name.setter
    def pad_name(self, value: str) -> None:
        self.parent.set_pin_name_for_no("%s" % self.pad_no, value)

    @property
    def rel_center(self) -> Vec2:
        return self.__rel_center

    @property
    # numpy mat creation is expensive. Use cached
    def translate_mat(self) -> 'npt.NDArray[numpy.float64]':
        return self.__translate_mat

    @property
    def theta(self) -> float:
        return self.__theta

    def __get_unrot_trace_points(self) -> Tuple[float, Vec2, Vec2]:
        if self.length > self.width:
            length = self.length - self.width
            width = self.width
            p0 = Point2(length/2, 0)
            p1 = Point2(-length/2, 0)
        else:
            length = self.width - self.length
            width = self.length
            p0 = Point2(0, length/2)
            p1 = Point2(0, -length/2)

        return width, p0, p1

    def __get_rel_trace_repr(self) -> Trace:
        w, p0, p1 = self.__get_unrot_trace_points()

        p0 = Point2.from_homol_mat(self.__inv_p2p_mat.dot(p0.homol()))
        p1 = Point2.from_homol_mat(self.__inv_p2p_mat.dot(p1.homol()))
        return Trace(p0, p1, w, self.layer)

    def __get_trace_repr(self) -> Trace:
        w, p0, p1 = self.__get_unrot_trace_points()

        p0 = Point2.from_homol_mat(self.pad_to_world_matrix.dot(p0.homol()))
        p1 = Point2.from_homol_mat(self.pad_to_world_matrix.dot(p1.homol()))
        return Trace(p0, p1, w, self.layer)

    def pad_to_world(self, pt: Vec2) -> Vec2:
        return Point2.from_homol_mat(self.pad_to_world_matrix.dot(pt.homol()))

    def world_to_pad(self, pt: Vec2) -> Vec2:
        return Point2.from_homol_mat(self.world_to_pad_matrix.dot(pt.homol()))

    def is_through(self) -> bool:
        return self.th_diam > 0
