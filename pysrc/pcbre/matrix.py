import numpy
import math
from PySide import QtCore

class RectSize(object):
    def __init__(self, *args, **kwargs):
        if len(args) == 2:
            self.width, self.height = args
        elif len(args) == 1 and isinstance(args[0], (QtCore.QRect, QtCore.QRectF)):
            self.width = args[0].width()
            self.width = args[0].height()
        elif len(args) == 1 and len(args[0]) == 2:
            self.width, self.height = args[0]
        elif len(kwargs) == 2 and "width" in kwargs and "height" in kwargs:
            self.width = kwargs["width"]
            self.height = kwards["height"]
        else:
            raise TypeError


def clip_point_to_rect(pt, rect):
    pt = Point2(pt)

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
    @staticmethod
    def fromCenterSize(pt1, width=0, height=0):
        width = abs(width)
        height = abs(height)
        r = Rect()
        r.left = pt1.x - width/2.
        r.bottom = pt1.y - height/2.
        r.right = pt1.x + width/2.
        r.top = pt1.y + height/2.
        return r

    @staticmethod
    def fromPoints(pt1, pt2):
        return Rect.fromXY(pt1.x, pt1.y, pt2.x, pt2.y)

    @staticmethod
    def fromXY(x0, y0, x1, y1):
        r = Rect()
        r.left = min(x0, x1)
        r.right = max(x0, x1)
        r.bottom = min(y0, y1)
        r.top = max(y0, y1)
        return r

    def __init__(self):
        """
        defined by bottom-left, width, height
        :param x:
        :param y:
        :param w:
        :param h:
        :return:
        """
        self.left = 0.
        self.right = 0.
        self.top = 0.
        self.bottom = 0.

    def feather(self, width=0, height=0):
        px = width / 2.
        py = height / 2.

        self.left -= px
        self.right += px
        self.bottom -= py
        self.top += py

    def translate(self, vec):
        self.left += vec.x
        self.right += vec.x
        self.top += vec.y
        self.bottom += vec.y

    @property
    def center(self):
        return Point2(self.right/2. + self.left/2., self.bottom/2. + self.top/2.)

    @property
    def tl(self):
        return Point2(self.left, self.top)

    @property
    def tr(self):
        return Point2(self.right, self.top)

    @property
    def bl(self):
        return Point2(self.left, self.bottom)

    @property
    def br(self):
        return Point2(self.right, self.bottom)

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.top - self.bottom

    def bbox_merge(self, other):
        self.left = min(self.left, other.left)
        self.bottom = min(self.bottom, other.bottom)
        self.right = max(self.right, other.right)
        self.top = max(self.top, other.top)

    def point_test(self, pt):
        """
        :param pt:
        :return: 2 for point-in-rect, 1 for point on/in rect, 0 for point outside rect
        """
        if self.left <= pt.x <= self.right and self.bottom <= pt.y <= self.top:
            if self.left < pt.x < self.right and self.bottom < pt.y < self.top:
                return 2
            return 1
        return 0

    def __repr__(self):
        return "<Rect l=%f b=%f r=%f t=%f>" % (self.left, self.bottom, self.right, self.top)

    def intersects(self, other):
        return not (other.left > self.right or
                    other.right < self.left or
                    other.bottom > self.top or
                    other.top < self.bottom)

    @staticmethod
    def fromRect(r):
        n = Rect()
        n.left = r.left
        n.right = r.right
        n.top = r.top
        n.bottom = r.bottom
        return n

    def rotated_bbox(self, theta):
        corners = [Point2(self.left, self.bottom),
                   Point2(self.right, self.bottom),
                   Point2(self.left, self.top),
                   Point2(self.right, self.top)]
        rot_corners = projectPoints(rotate(theta), corners)

        n = Rect()
        n.left = min(i.x for i in rot_corners)
        n.right = max(i.x for i in rot_corners)
        n.top = max(i.y for i in rot_corners)
        n.bottom = min(i.y for i in rot_corners)

        return n



class Vec2:
    @staticmethod
    def fromHomol(*args):
        if len(args) == 3:
            x,y,w = args
        elif len(args) == 1 and len(args[0]) == 3:
            x,y,w = args[0]
        else:
            raise TypeError

        return Vec2(x/w,y/w)

    @staticmethod
    def fromPolar(theta, mag):
        return Vec2(math.cos(theta) * mag, math.sin(theta) * mag)

    def __init__(self, *args, **kwargs):
        if len(args) == 0:
            self.x = kwargs['x']
            self.y = kwargs['y']

        elif len(args) == 1:
            try:
                x = args[0].x
                y = args[0].y

            except AttributeError:
                pass
            else:

                # Some of the QT objects we want to convert from have .x / .y
                if callable(x) and callable(y):
                    self.x = x()
                    self.y = y()
                else:
                    self.x = x
                    self.y = y

                return

            # Handles Point2(tuple)
            if len(args) == 1 and len(args[0]) == 2:
                self.x, self.y = args[0]

        # Handles Point2(x, y)
        elif len(args) == 2:
            self.x, self.y = args
        else:
            raise TypeError



    def __getitem__(self, index):
        if index == 0:
            return self.x
        elif index == 1:
            return self.y
        else:
            raise IndexError()

    def cmpeq(self, other, eps=0.001):
        d = numpy.abs(self - other).max()
        return d < eps

    #@property
    #def x(self):
    #    return self[0]

    #@x.setter
    #def x(self, value):
    #    self[0] = value

    #@property
    #def y(self):
    #    return self[1]

    #@y.setter
    #def y(self, value):
    #    self[1] = value

    def mag2(self):
        return self.x ** 2 + self.y ** 2

    def mag(self):
        return math.sqrt(self.mag2())

    def norm(self):
        return self/self.mag()

    def homol(self):
        """
            return homologous coordinate equivalent of Vec2 ([vec2.x, vec2.y, 1])
        """
        return numpy.append(self, [1])

    def floatTuple(self):
        return (self.x, self.y)

    def intTuple(self):
        return int(round(self.x)), int(round(self.y))

    def __add__(self, other):
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vec2(self.x - other.x, self.y - other.y)

    def dot(self, other):
        return self.x * other.x + self.y * other.y


    def angle(self):
        return math.atan2(self.y, self.x)

    def __mul__(self, scalar):
        return Vec2(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar):
        return Vec2(self.x / scalar, self.y / scalar)

    def __len__(self):
        return 2

    def __iter__(self):
        return iter([self.x, self.y])

    def __repr__(self):
        return "V(%f %f)" % (self.x, self.y)

    def __neg__(self):
        return Point2(-self.x, -self.y)




class Point2(Vec2):
    def __repr__(self):
        return "P(%f %f)" % (self.x, self.y)

def project_point_line(point, lp1, lp2, segment=True, off_end=False):
    """

    :param point:
    :type point: Vec2
    :type line: Vec2
    :param line:
    :return: (u, d), where u is nearest point along line, and d is distance from line to point
    """

    lp1 = Vec2(lp1)
    lp2 = Vec2(lp2)
    point = Vec2(point)

    v = Vec2(lp2 - lp1)
    length_square = v.mag2()

    # Length of line is zero, so collapses to distance-to-point
    if length_square == 0:
        return lp1, Vec2(point - lp1).mag()

    t = (point - lp1).dot(v) / length_square

    if (t < 0 or t > 1.0) and segment:
        if off_end:
            if t < 0:
                return lp1, (point - lp1).mag()
            else:
                return lp2, (point - lp2).mag()

        return None, None

    proj = lp1 + float(t) * v

    return proj, (point - proj).mag()

INTERSECT_COLINEAR = 0
INTERSECT_PARALLEL = 1
INTERSECT_NORMAL = 2

def line_intersect(lp1, lp2, lp3, lp4):
    p = Vec2(lp1)
    q = Vec2(lp3)
    r = Vec2(lp2) - Vec2(lp1)
    s = Vec2(lp4) - Vec2(lp3)
    u_num = numpy.cross(q - p, r)
    u_denom = numpy.cross(r, s)
    if u_num == 0 and u_denom == 0:
        return INTERSECT_COLINEAR, None
    elif u_num != 0 and u_denom == 0:
        return INTERSECT_PARALLEL, None
    else:
        u = u_num / u_denom
        return INTERSECT_NORMAL, q + s * u


def cross(a, b):
    return numpy.cross(numpy.array([a.x, a.y]), numpy.array([b.x, b.y]))

def line_distance_segment(lp1, lp2, lp3, lp4):
    p = Vec2(lp1)
    q = Vec2(lp3)
    
    vec_1 = Vec2(lp2) - Vec2(lp1)
    
    vec_2 = Vec2(lp4) - Vec2(lp3)
    
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
    
    distances = []
    distances.append(project_point_line(lp1, lp3, lp4, True, True)[1])
    distances.append(project_point_line(lp2, lp3, lp4, True, True)[1])
    distances.append(project_point_line(lp3, lp1, lp2, True, True)[1])
    distances.append(project_point_line(lp4, lp1, lp2, True, True)[1])
    return min(distances)

def translate(x, y):
    return numpy.array([
        [1, 0, x],
        [0, 1, y],
        [0, 0, 1]
    ], dtype=numpy.float32)

def scale(xs, ys=None):
    if ys is None:
        ys = xs

    return numpy.array([
        [xs, 0, 0],
        [0, ys, 0],
        [0,  0, 1]
    ], dtype=numpy.float32)

def rotate(theta):
    _cos = math.cos(theta)
    _sin = math.sin(theta)
    return numpy.array([
        [_cos, -_sin, 0],
        [_sin,  _cos, 0],
        [              0,                0, 1]
    ], dtype=numpy.float32)

def flip(axis=0):
    if axis == 0:
        xs = -1
        ys = 1
    else:
        xs = 1
        ys = -1
    return scale(xs, ys)

def cflip(do_flip, axis=0):
    if do_flip:
        return flip(axis)
    return numpy.identity(3, dtype=numpy.float32)

def projectPoint(matrix, pt):
    return Point2.fromHomol(matrix.dot(pt.homol()))

def projectPoints(matrix, pts):
    return [projectPoint(matrix, pt) for pt in pts]