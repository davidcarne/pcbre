from abc import ABCMeta, abstractmethod
from typing import Sequence, Optional, TYPE_CHECKING

import p2t  # type: ignore
# Shapely library is used for polygon operations
import shapely.geometry  # type: ignore
import shapely.speedups  # type: ignore
from shapely.geometry import Polygon as ShapelyPolygon, \
    Point as ShapelyPoint, LineString as ShapelyLineString

from pcbre.matrix import Rect, Vec2, Point2
from pcbre.model.const import IntersectionClass, TFF

if TYPE_CHECKING:
    from pcbre.model.project import Project
    import pcbre.model.stackup
    from pcbre.model.net import Net
    from pcbre.model.stackup import Layer, ViaPair

if shapely.speedups.available:
    shapely.speedups.enable()
else:
    print("Shapely was compiled without GEOS development headers available;" +
          "therefore, speedups are not available!")
    print("Please install GEOS development headers and reinstall Shapely for" +
          "improved performance.")

__author__ = 'davidc'


class Geom(metaclass=ABCMeta):
    ISC: IntersectionClass = IntersectionClass.NONE
    TYPE_FLAGS: int = 0

    def __init__(self) -> None:
        self._project: Optional['Project'] = None

    @property
    @abstractmethod
    def net(self) -> Optional['Net']: pass

    @net.setter
    def net(self, value: Optional['Net']) -> None: pass

    @property
    @abstractmethod
    def bbox(self) -> Rect: pass

    # @property
    # @abstractmethod
    # def layer(self) -> Optional['Layer']: pass


class Polygon(Geom):
    ISC = IntersectionClass.POLYGON
    TYPE_FLAGS = TFF.HAS_NET | TFF.HAS_GEOM

    def __init__(self, layer: 'Layer',
                 exterior: Sequence[Vec2],
                 interiors: Sequence[Sequence[Vec2]],
                 net: Optional['Net'] = None) -> None:
        super(Polygon, self).__init__()

        # Buffer 0 forces geom cleanup
        self.__geometry = ShapelyPolygon(exterior, interiors).buffer(0)

        minx, miny, maxx, maxy = self.__geometry.bounds

        self._bbox = Rect.from_points(Point2(minx, miny), Point2(maxx, maxy))

        self._net = net
        self._layer = layer
        self._project: Optional['Project'] = None

        self.__triangulation = None

    @property
    def bbox(self) -> Rect:
        return self._bbox

    @property
    def net(self) -> Optional['Net']:
        return self._net

    @net.setter
    def net(self, net: Optional['Net']) -> None:
        self._net = net

    @property
    def layer(self) -> 'Layer':
        return self._layer

    def get_poly_repr(self) -> ShapelyPolygon:
        return self.__geometry

    def get_tris_repr(self) -> p2t.CDT:
        if self.__triangulation is None:
            cdt = p2t.CDT(
                [Point2(*i) for i in self.__geometry.exterior.coords[:-1]])
            for interior in self.__geometry.interiors:
                cdt.add_hole([Point2(*i) for i in interior.coords[:-1]])

            self.__triangulation = cdt.triangulate()

        return self.__triangulation


class Trace(Geom):
    ISC = IntersectionClass.TRACE
    TYPE_FLAGS = TFF.HAS_GEOM | TFF.HAS_NET

    def __init__(self, p0: Vec2, p1: Vec2, thickness: float,
                 layer: 'Layer', net: Optional['Net'] = None) -> None:
        super(Trace, self).__init__()
        self.p0 = p0
        self.p1 = p1

        self.thickness = thickness

        self._net = net
        self._layer = layer

        self._project = None

        self._bbox = Rect.from_points(self.p0, self.p1)
        self._bbox.feather(self.thickness, self.thickness)

        self.__poly_repr = ShapelyLineString(
            [self.p0, self.p1]).buffer(self.thickness / 2)

    @property
    def net(self) -> Optional['Net']:
        return self._net

    @net.setter
    def net(self, net: Optional['Net']) -> None:
        self._net = net

    @property
    def layer(self) -> 'Layer':
        return self._layer

    @property
    def bbox(self) -> 'Rect':
        return self._bbox

    def get_poly_repr(self) -> ShapelyPolygon:
        return self.__poly_repr

    def __repr__(self) -> str:
        netname = self.net.name if self.net is not None else "none"
        layername = self.layer.name if self.layer is not None else "none",
        return "<Trace %s %s r=%f, layer=%s, net=%s>" % (
            self.p0, self.p1, self.thickness, layername, netname)


class Airwire(Geom):
    TYPE_FLAGS = TFF.HAS_NET
    ISC = IntersectionClass.VIRTUAL_LINE

    def __init__(self, p0: Vec2, p1: Vec2,
                 p0_layer: 'Layer',
                 p1_layer: 'Layer',
                 net: Optional['pcbre.model.net.Net']) -> None:
        super(Airwire, self).__init__()
        self.p0 = p0
        self.p1 = p1
        self.p0_layer = p0_layer
        self.p1_layer = p1_layer
        self._net = net

        self._bbox = Rect.from_points(self.p0, self.p1)

        self._project = None

    @property
    def net(self) -> Optional['Net']:
        return self._net

    @net.setter
    def net(self, net: Optional['Net']) -> None:
        self._net = net

    @property
    def bbox(self) -> Rect:
        return self._bbox


class Via(Geom):
    ISC = IntersectionClass.VIA
    TYPE_FLAGS = TFF.HAS_GEOM | TFF.HAS_NET

    def __init__(self, pt: Vec2, viapair: 'ViaPair', r: float,
                 net: Optional['pcbre.model.net.Net'] = None) -> None:
        super(Via, self).__init__()
        self.pt = pt
        self.r = r
        self.viapair = viapair
        self._net = net

        self._bbox = Rect.from_center_size(pt, r * 2, r * 2)

        self._project = None

        self.__poly_repr = ShapelyPoint(pt).buffer(self.r)

    @property
    def net(self) -> Optional['Net']:
        return self._net

    @net.setter
    def net(self, net: Optional['Net']) -> None:
        self._net = net

    @property
    def bbox(self) -> 'Rect':
        return self._bbox

    def get_poly_repr(self) -> ShapelyPolygon:
        return self.__poly_repr

    def __repr__(self) -> str:
        return "<Via %s r:%f ly=(%s:%s) net=%s>" % (
            self.pt, self.r,
            self.viapair.layers[0].name, self.viapair.layers[1].name,
            self.net.name if self.net is not None else "none")
