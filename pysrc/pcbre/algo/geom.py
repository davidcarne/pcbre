from typing import Any, TYPE_CHECKING, TypeVar, Callable, Dict, Tuple, Optional, Union

from shapely.geometry import Point as ShapelyPoint  # type: ignore

from pcbre.matrix import line_distance_segment, Vec2, dist_point_off_line_seg
from pcbre.model.artwork_geom import Trace, Via, Polygon, Airwire, Geom
from pcbre.model.const import IntersectionClass

if TYPE_CHECKING:
    from pcbre.model.pad import Pad
    from pcbre.model.stackup import Layer


def dist_pt_trace(pt: Vec2, trace: Trace) -> float:
    return dist_pt_line_seg(pt, trace.p0, trace.p1) - trace.thickness / 2


def dist_pt_line_seg(pt: Vec2, s_pt1: Vec2, s_pt2: Vec2) -> float:
    return dist_point_off_line_seg(pt, s_pt1, s_pt2)


def dist_trace_trace(trace_1: Trace, trace_2: Trace) -> float:
    if trace_1.layer != trace_2.layer:
        return float("inf")
    d = line_distance_segment(trace_1.p0, trace_1.p1, trace_2.p0, trace_2.p1)
    return d - trace_1.thickness / 2 - trace_2.thickness / 2


def dist_via_trace(via: Via, trace: Trace) -> float:
    if trace.layer not in via.viapair.all_layers:
        return float("inf")
    return (dist_pt_line_seg(via.pt, trace.p0, trace.p1) -
            trace.thickness / 2 - via.r)


def dist_via_via(via_1: Via, via_2: Via) -> float:
    if not set(via_1.viapair.all_layers) \
            .intersection(via_2.viapair.all_layers):
        return float("inf")
    d = (via_1.pt - via_2.pt).mag()
    return d - via_1.r - via_2.r


def dist_pad_pad(p1: 'Pad', p2: 'Pad') -> float:
    """
    :type p1: Pad
    :type p2: Pad
    :param p1:
    :param p2:
    :return:
    """
    if not p1.is_through():
        if p1.layer != p2.layer:
            return float("inf")

    # Fast degenerate case
    if p1.width == p1.length and p2.width == p2.length:
        d = (p1.center - p2.center).mag()
        return d - p1.width / 2 - p2.width / 2

    else:
        t1 = p1.trace_repr
        t2 = p2.trace_repr
        return dist_trace_trace(t1, t2)


def dist_via_pad(v1: Via, p1: 'Pad') -> float:
    d = (v1.pt - p1.center).mag()
    return d - p1.width / 2 - v1.r


def dist_trace_pad(trace: Trace, p1: 'Pad') -> float:
    # inf distance if on other layers
    if not p1.is_through():
        if p1.layer != trace.layer:
            return float("inf")

    # Degenerate case where pad is a circle
    if p1.width == p1.length:
        return (dist_pt_line_seg(p1.center, trace.p0, trace.p1) -
                trace.thickness / 2 - p1.width / 2)
    else:
        ptr = p1.trace_repr
        return dist_trace_trace(ptr, trace)


def dist_polygon_polygon(p1: Polygon, p2: Polygon) -> float:
    if p1.layer != p2.layer:
        return float("inf")

    # ignoring typing here since we don't have stubs for the polygon lib
    return p1.get_poly_repr().distance(p2.get_poly_repr())  # type: ignore


# Trace is the same, has a layer and a poly repr
dist_polygon_trace = dist_polygon_polygon


def dist_polygon_via(p: Polygon, v: Via) -> float:
    if p.layer not in v.viapair.all_layers:
        return float("inf")

    # ignoring typing here since we don't have stubs for the polygon lib
    return p.get_poly_repr().distance(v.get_poly_repr())  # type: ignore


def dist_polygon_pad(poly: Polygon, pad: 'Pad') -> float:
    if not pad.is_through():
        if pad.layer != poly.layer:
            return float("inf")

    # ignoring typing here since we don't have stubs for the polygon lib
    return poly.get_poly_repr().distance(pad.get_poly_repr())  # type: ignore


def dist_virtual_line_XX(airwire: Airwire, other: Any) -> float:
    if airwire.p0_layer == other.layer and point_inside(other, airwire.p0):
        return 0
    elif airwire.p1_layer == other.layer and point_inside(other, airwire.p1):
        return 0
    return float("inf")


dist_virtual_line_trace = dist_virtual_line_XX
dist_virtual_line_polygon = dist_virtual_line_XX


def dist_virtual_line_via(airwire: Airwire, via: Via) -> float:
    layers = via.viapair.all_layers
    if airwire.p0_layer in layers and point_inside(via, airwire.p0):
        return 0
    elif airwire.p1_layer in layers and point_inside(via, airwire.p1):
        return 0

    return float("inf")


def dist_virtual_line_pad(airwire: Airwire, pad: 'Pad') -> float:
    if pad.is_through():
        if point_inside(pad, airwire.p0) or point_inside(pad, airwire.p1):
            return 0
        else:
            return float("inf")

    return dist_virtual_line_XX(airwire, pad)


def dist_virtual_line_virtual_line(_: Any, __: Any) -> float:
    return float("inf")


T = TypeVar('T')
U = TypeVar('U')


def swapped(fn: Callable[[U, T], float]) -> Callable[[T, U], float]:
    def _(a: T, b: U) -> float:
        return fn(b, a)

    return _


def pt_inside_pad(pad: 'Pad', pt: Vec2) -> bool:
    """

    :param pt:
    :return:
    """
    delta = pad.world_to_pad(pt)

    if pad.width == pad.length:
        return delta.mag() < pad.length / 2
    else:
        return pt_inside_trace(pad.trace_repr, pt)


def pt_inside_trace(trace: Trace, pt: Vec2) -> bool:
    return dist_pt_trace(pt, trace) < 0


def pt_inside_via(via: Via, pt: Vec2) -> bool:
    return (pt - via.pt).mag2() <= via.r ** 2


def pt_inside_polygon(poly: Polygon, pt: Vec2) -> bool:
    pt = ShapelyPoint(pt)
    # ignoring typing because there's no stubs for polygon
    return poly.get_poly_repr().intersects(pt)  # type: ignore


def pt_inside_virtual_line(airwire: Airwire, pt: Vec2) -> bool:
    return dist_pt_line_seg(pt, airwire.p0, airwire.p1) <= 0


# ********** Build comparison functions for geom types *****************
_geom_types = [i for i in IntersectionClass if i is not IntersectionClass.NONE]
_geom_ops: Dict[Tuple[IntersectionClass, IntersectionClass], Callable[[Geom, Geom], float]] = {}


def _dist_name(a: IntersectionClass, b: IntersectionClass) -> str:
    return "dist_%s_%s" % (a.name.lower(), b.name.lower())


for n, a in enumerate(_geom_types):
    for b in _geom_types[n:]:
        fwd_name = _dist_name(a, b)
        rev_name = _dist_name(b, a)
        if fwd_name in globals():
            fn = globals()[fwd_name]
            _geom_ops[(a, b)] = fn
            _geom_ops[(b, a)] = swapped(fn)
        elif rev_name in globals():
            fn = globals()[rev_name]
            _geom_ops[(a, b)] = swapped(fn)
            _geom_ops[(b, a)] = fn
        else:
            raise NotImplementedError("Geom distance op for %s %s" % (a, b))


def distance(a: Geom, b: Geom) -> float:
    return _geom_ops[a.ISC, b.ISC](a, b)


def intersect(a: Geom, b: Geom) -> bool:
    return distance(a, b) <= 0


_pt_inside_ops: Dict[IntersectionClass, Callable[[Geom, Vec2], bool]] = {}
for i in _geom_types:
    _pt_inside_ops[i] = globals()["pt_inside_%s" % i.name.lower()]


def point_inside(geom: Geom, pt: Vec2) -> bool:
    if not geom.bbox.point_test(pt):
        return False

    return _pt_inside_ops[geom.ISC](geom, pt)


def can_self_intersect(geom: Geom) -> bool:
    return geom.ISC not in [
        IntersectionClass.NONE,
        IntersectionClass.VIRTUAL_LINE]


# layer_for finds a layer (or None) for the geometry queried.
def _layer_for_XX(geom: Union[Polygon, Trace, 'Pad']) -> Optional['Layer']:
    return geom.layer


_layer_for_polygon = _layer_for_trace = _layer_for_pad = _layer_for_XX


def _layer_for_via(via: Via) -> 'Layer':
    return via.viapair.layers[0]


def _layer_for_virtual_line(vl: Airwire) -> None:
    return None


_layer_for_ops: Dict[int, Callable[[Geom], Optional['Layer']]] = {}
for i in _geom_types:
    _layer_for_ops[i.value] = globals()["_layer_for_%s" % i.name.lower()]


def layer_for(geom: Geom) -> Optional['Layer']:
    return _layer_for_ops[geom.ISC.value](geom)
