import math
from enum import Enum
from typing import Tuple, List, Iterator, Optional, Sequence, Union, Any, TYPE_CHECKING

import numpy

if TYPE_CHECKING:
    import numpy.typing as npt


def clip_point_to_rect(pt: 'Vec2', rect: 'Rect') -> 'Vec2':
    if pt.x < rect.left:
        pt.x = rect.left
    elif pt.x > rect.right:
        pt.x = rect.right

    if pt.y < rect.bottom:
        pt.y = rect.bottom
    elif pt.y > rect.top:
        pt.y = rect.top

    return pt


class Rect(object):
    __slots__ = ["left", "bottom", "right", "top"]

    @staticmethod
    def from_center_size(pt1: 'Vec2', width: float = 0, height: float = 0) -> 'Rect':
        width = abs(width)
        height = abs(height)
        r = Rect()
        r.left = pt1.x - width / 2.
        r.bottom = pt1.y - height / 2.
        r.right = pt1.x + width / 2.
        r.top = pt1.y + height / 2.
        return r

    @staticmethod
    def from_points(pt1: 'Vec2', pt2: 'Vec2') -> 'Rect':
        return Rect.from_xy_coord(pt1.x, pt1.y, pt2.x, pt2.y)

    @staticmethod
    def from_xy_coord(x0: float, y0: float, x1: float, y1: float) -> 'Rect':
        r = Rect()
        r.left = min(x0, x1)
        r.right = max(x0, x1)
        r.bottom = min(y0, y1)
        r.top = max(y0, y1)
        return r

    def __init__(self) -> None:
        self.left = 0.
        self.right = 0.
        self.top = 0.
        self.bottom = 0.

    def feather(self, width: float = 0, height: float = 0) -> None:
        px = width / 2.
        py = height / 2.

        self.left -= px
        self.right += px
        self.bottom -= py
        self.top += py

    def translate(self, vec: 'Vec2') -> None:
        self.left += vec.x
        self.right += vec.x
        self.top += vec.y
        self.bottom += vec.y

    @property
    def center(self) -> 'Point2':
        return Point2(
            self.right / 2. + self.left / 2.,
            self.bottom / 2. + self.top / 2.)

    @property
    def tl(self) -> 'Point2':
        return Point2(self.left, self.top)

    @property
    def tr(self) -> 'Point2':
        return Point2(self.right, self.top)

    @property
    def bl(self) -> 'Point2':
        return Point2(self.left, self.bottom)

    @property
    def br(self) -> 'Point2':
        return Point2(self.right, self.bottom)

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.top - self.bottom

    def bbox_merge(self, other: 'Rect') -> None:
        self.left = min(self.left, other.left)
        self.bottom = min(self.bottom, other.bottom)
        self.right = max(self.right, other.right)
        self.top = max(self.top, other.top)

    def point_merge(self, other: 'Vec2') -> None:
        self.left = min(self.left, other.x)
        self.bottom = min(self.bottom, other.y)
        self.right = max(self.right, other.x)
        self.top = max(self.top, other.y)

    def point_test(self, pt: 'Vec2') -> int:
        """
        :param pt:
        :return:
            2 for point-in-rect,
            1 for point on/in rect,
            0 for point outside rect
        """
        if self.left <= pt.x <= self.right and self.bottom <= pt.y <= self.top:
            if self.left < pt.x < self.right and self.bottom < pt.y < self.top:
                return 2
            return 1
        return 0

    def __repr__(self) -> str:
        return "<Rect l=%f b=%f r=%f t=%f>" % (
            self.left, self.bottom, self.right, self.top)

    def intersects(self, other: 'Rect') -> bool:
        return not (other.left > self.right or
                    other.right < self.left or
                    other.bottom > self.top or
                    other.top < self.bottom)

    def copy(self) -> 'Rect':
        new = Rect()
        new.left = self.left
        new.right = self.right
        new.top = self.top
        new.bottom = self.bottom
        return new

    def rotated_bbox(self, theta: float) -> 'Rect':
        corners = [Point2(self.left, self.bottom),
                   Point2(self.right, self.bottom),
                   Point2(self.left, self.top),
                   Point2(self.right, self.top)]

        rot_corners = project_points(rotate(theta), corners)

        n = Rect()
        n.left = min(i.x for i in rot_corners)
        n.right = max(i.x for i in rot_corners)
        n.top = max(i.y for i in rot_corners)
        n.bottom = min(i.y for i in rot_corners)

        return n


class Vec2:
    @staticmethod
    def from_mat(m: Sequence[float]) -> 'Vec2':
        return Vec2(m[0], m[1])

    @staticmethod
    def from_homol_mat(m: 'Union[numpy.number[Any], Sequence[float], npt.NDArray[numpy.float64]]') -> 'Vec2':
        return Vec2.from_homol(m[0], m[1], m[2])

    @staticmethod
    def from_homol(x: float, y: float, w: float) -> 'Vec2':
        return Vec2(x / w, y / w)

    @staticmethod
    def from_polar(theta: float, mag: float) -> 'Vec2':
        return Vec2(math.cos(theta) * mag, math.sin(theta) * mag)

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def dup(self) -> 'Vec2':
        return Vec2(self.x, self.y)

    def __getitem__(self, index: int) -> float:
        if index == 0:
            return self.x
        elif index == 1:
            return self.y
        else:
            raise IndexError()

    def cmpeq(self, other: 'Vec2', eps: float = 0.001) -> bool:
        d = (self - other).maxcomp()
        return d < eps

    def maxcomp(self) -> float:
        # absolute of the vector components
        return max(abs(self.x), abs(self.y))

    def mag2(self) -> float:
        return self.x ** 2 + self.y ** 2

    def mag(self) -> float:
        return math.sqrt(self.mag2())

    def norm(self) -> 'Vec2':
        return self / self.mag()

    def mat(self) -> 'npt.NDArray[numpy.float64]':
        return numpy.array([self.x, self.y], dtype=numpy.float64)

    def homol(self) -> 'npt.NDArray[numpy.float64]':
        """
            return homologous coordinate equivalent
            of Vec2 ([vec2.x, vec2.y, 1])
        """
        return numpy.array([self.x, self.y, 1], dtype=numpy.float64)

    def to_float_tuple(self) -> Tuple[float, float]:
        return self.x, self.y

    def to_int_tuple(self) -> Tuple[int, int]:
        return int(round(self.x)), int(round(self.y))

    def __add__(self, other: 'Vec2') -> 'Vec2':
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: 'Vec2') -> 'Vec2':
        return Vec2(self.x - other.x, self.y - other.y)

    def dot(self, other: 'Vec2') -> float:
        return self.x * other.x + self.y * other.y

    def angle(self) -> float:
        return math.atan2(self.y, self.x)

    def __mul__(self, scalar: float) -> 'Vec2':
        return Vec2(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar: float) -> 'Vec2':
        return Vec2(self.x / scalar, self.y / scalar)

    def __len__(self) -> int:
        return 2

    def __iter__(self) -> Iterator[float]:
        return iter([self.x, self.y])

    def __repr__(self) -> 'str':
        return "V(%f %f)" % (self.x, self.y)

    def __neg__(self) -> 'Vec2':
        return Vec2(-self.x, -self.y)


class Point2(Vec2):
    def __repr__(self) -> str:
        return "P(%f %f)" % (self.x, self.y)


def project_point_line(point: Vec2,
                       lp1: Vec2,
                       lp2: Vec2,
                       segment: bool = True,
                       off_end: bool = False) -> Union[Tuple[None, None], Tuple[Vec2, float]]:
    v: Vec2 = lp2 - lp1
    length_square = v.mag2()

    # Length of line is zero, so collapses to distance-to-point
    if length_square == 0:
        return lp1, (point - lp1).mag()

    # t = distance along line (0 = start point, 1 = end)
    t = (point - lp1).dot(v) / length_square

    if (t < 0 or t > 1.0) and segment:
        if off_end:
            if t < 0:
                return lp1, (point - lp1).mag()
            else:
                return lp2, (point - lp2).mag()

        return None, None

    proj = lp1 + v * float(t)

    return proj, (point - proj).mag()


def dist_point_off_line_seg(point: Vec2, lp1: Vec2, lp2: Vec2) -> float:
    v = lp2 - lp1
    length_square = v.mag2()

    # Length of line is zero, so collapses to distance-to-point
    if length_square == 0:
        return (point - lp1).mag()

    # t = distance along line (0 = start point, 1 = end)
    t = (point - lp1).dot(v) / length_square

    if t < 0 or t > 1.0:
        if t < 0:
            return (point - lp1).mag()
        else:
            return (point - lp2).mag()

    proj = lp1 + v * t

    return (point - proj).mag()


class Intersect(Enum):
    COLINEAR = 0
    PARALLEL = 1
    NORMAL = 2


def line_intersect(lp1: Vec2, lp2: Vec2, lp3: Vec2, lp4: Vec2) -> Tuple[Intersect, Optional[Vec2]]:
    p = lp1
    q = lp3
    r = lp2 - lp1
    s = lp4 - lp3
    u_num = cross(q - p, r)
    u_denom = cross(r, s)
    if u_num == 0 and u_denom == 0:
        return Intersect.COLINEAR, None
    elif u_num != 0 and u_denom == 0:
        return Intersect.PARALLEL, None
    else:
        u = float(u_num / u_denom)
        return Intersect.NORMAL, q + s * u


def cross(a: Vec2, b: Vec2) -> float:
    return a.x * b.y - a.y * b.x


def line_distance_segment(lp1: Vec2, lp2: Vec2, lp3: Vec2, lp4: Vec2) -> float:
    p = lp1
    q = lp3

    vec_1 = lp2 - lp1
    vec_2 = lp4 - lp3

    u_num = cross(q - p, vec_1)
    v_num = cross(q - p, vec_2)
    denom = cross(vec_1, vec_2)

    if u_num == 0 and denom == 0:
        # Colinear, check overlap
        # TODO: Speedup here
        pass
    elif u_num != 0 and denom != 0:
        u = u_num / denom
        v = v_num / denom
        if 0 <= u <= 1 and 0 <= v <= 1:
            return 0

    distances = [dist_point_off_line_seg(lp1, lp3, lp4), dist_point_off_line_seg(lp2, lp3, lp4),
                 dist_point_off_line_seg(lp3, lp1, lp2), dist_point_off_line_seg(lp4, lp1, lp2)]
    return min(distances)


def translate(x: float, y: float) -> 'npt.NDArray[numpy.float64]':
    return numpy.array([
        [1, 0, x],
        [0, 1, y],
        [0, 0, 1]
    ], dtype=numpy.float64)


def scale(xs: float, ys: Optional[float] = None) -> 'npt.NDArray[numpy.float64]':
    if ys is None:
        ys = xs

    return numpy.array([
        [xs, 0, 0],
        [0, ys, 0],
        [0, 0, 1]
    ], dtype=numpy.float64)


def rotate(theta: float) -> 'npt.NDArray[numpy.float64]':
    _cos = math.cos(theta)
    _sin = math.sin(theta)
    return numpy.array([
        [_cos, -_sin, 0],
        [_sin, _cos, 0],
        [0, 0, 1]
    ], dtype=numpy.float64)


def flip(axis: int = 0) -> 'npt.NDArray[numpy.float64]':
    if axis == 0:
        xs = -1
        ys = 1
    else:
        xs = 1
        ys = -1
    return scale(xs, ys)


def cflip(do_flip: bool, axis: int = 0) -> 'npt.NDArray[numpy.float64]':
    if do_flip:
        return flip(axis)
    return numpy.identity(3, dtype=numpy.float64)


def project_point(matrix: 'npt.NDArray[numpy.float64]', pt: Vec2) -> Vec2:
    return Point2.from_homol_mat(matrix.dot(pt.homol()))


def project_points(matrix: 'npt.NDArray[numpy.float64]', pts: Sequence[Vec2]) -> List[Vec2]:
    return [project_point(matrix, pt) for pt in pts]
