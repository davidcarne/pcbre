from pcbre.matrix import Rect, Point2
from pcbre.model.const import IntersectionClass, TFF

# Shapely library is used for polygon operations
from shapely.geometry import Polygon as ShapelyPolygon, Point as ShapelyPoint, LineString as ShapelyLineString
import shapely.speedups
import p2t

if shapely.speedups.available:
    shapely.speedups.enable()
else:
    print("Shapely was compiled without GEOS development headers available; therefore, speedups are not available!")
    print("Please install GEOS development headers and reinstall Shapely for improved performance.")

__author__ = 'davidc'


class Geom:
    pass


class Polygon(Geom):
    ISC = IntersectionClass.POLYGON
    TYPE_FLAGS = TFF.HAS_NET | TFF.HAS_GEOM

    def __init__(self, layer, exterior, interiors=[], net=None):
        # Buffer 0 forces geom cleanup
        self.__geometry = ShapelyPolygon(exterior, interiors).buffer(0)

        minx, miny, maxx, maxy = self.__geometry.bounds

        self.bbox = Rect.fromPoints(Point2(minx, miny), Point2(maxx, maxy))

        self.net = net
        self.layer = layer
        self._project = None

        self.__triangulation = None

    def get_poly_repr(self):
        return self.__geometry

    def get_tris_repr(self):
        if self.__triangulation is None:
            cdt = p2t.CDT([Point2(*i) for i in self.__geometry.exterior.coords[:-1]])
            for interior in self.__geometry.interiors:
                cdt.add_hole([Point2(*i) for i in interior.coords[:-1]])

            self.__triangulation = cdt.triangulate()

        return self.__triangulation


class Trace(Geom):
    ISC = IntersectionClass.TRACE
    TYPE_FLAGS = TFF.HAS_GEOM | TFF.HAS_NET

    def __init__(self, p0, p1, thickness, layer, net=None):
        self.p0 = p0
        self.p1 = p1

        self.thickness = thickness

        self.net = net
        self.layer = layer

        self._project = None

        self.bbox = Rect.fromPoints(self.p0, self.p1)
        self.bbox.feather(self.thickness, self.thickness)

        self.__poly_repr = ShapelyLineString([self.p0, self.p1]).buffer(self.thickness/2)

    def get_poly_repr(self):
        return self.__poly_repr

    def __repr__(self):
        netname = self.net.name if self.net is not None else "none"
        return "<Trace %s %s r=%f, layer=%s, net=%s>" % (self.p0, self.p1, self.thickness, self.layer.name, netname)


class Airwire(Geom):
    TYPE_FLAGS = TFF.HAS_NET
    ISC = IntersectionClass.VIRTUAL_LINE

    def __init__(self, p0, p1, p0_layer, p1_layer, net):
        self.p0 = p0
        self.p1 = p1
        self.p0_layer = p0_layer
        self.p1_layer = p1_layer
        self.net = net

        self.bbox = Rect.fromPoints(self.p0, self.p1)

        self._project = None


class Via(Geom):
    ISC = IntersectionClass.VIA
    TYPE_FLAGS = TFF.HAS_GEOM | TFF.HAS_NET

    def __init__(self, pt, viapair, r, net=None):
        self.pt = pt
        self.r = r
        self.viapair = viapair
        self.net = net

        self.bbox = Rect.fromCenterSize(pt, r*2, r*2)

        self._project = None

        self.__poly_repr = ShapelyPoint(pt).buffer(self.r)

    def get_poly_repr(self):
        return self.__poly_repr

    def __repr__(self):
        return "<Via %s r:%f ly=(%s:%s) net=%s>" % (
            self.pt, self.r,
            self.viapair.layers[0].name, self.viapair.layers[1].name,
            self.net.name if self.net is not None else "none")
