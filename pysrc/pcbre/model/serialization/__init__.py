import capnp

from .schema_capnp import Project, Stackup, ViaPair, Layer, Color3f, Artwork, Imagery, \
        Net, Nets, Image, ImageTransform, Matrix3x3, Matrix4x4, Point2, Point2f, Keypoint, ImageTransform

import pcbre.matrix
import contextlib
import numpy

def serialize_color3f(*arg):
    msg = Color3f.new_message()

    if len(arg) == 1 and len(arg[0]) == 3:
        arg = arg[0]
    elif len(arg) == 3:
        pass
    else:
        raise TypeError("Unknown argtype to serialize_color3f %s" % arg)

    msg.r, msg.g, msg.b = map(float, arg)

    return msg

def float_lim(v):
    v = float(v)
    if v < 0:
        return 0
    if v > 1:
        return 1
    return v

def deserialize_color3f(msg):
    return float_lim(msg.r), float_lim(msg.g), float_lim(msg.b)

def __serialize_matrix(msg, mat, nterms):
    m_r = mat.flatten()

    for n, i in enumerate(m_r):
        setattr(msg, "t%d" % n, float(i))

def serialize_matrix(mat):
    if mat.shape == (3,3):
        m = Matrix3x3.new_message()
        c = 9

    elif mat.shape == (4,4):
        m = Matrix4x4.new_message()
        c = 16
    else:
        raise TypeError("Cannot serialize matrix of shape %s" % mat.shape)
    __serialize_matrix(m, mat, c)
    return m

def __deserialize_matrix_n(msg, nterms):
    ar = numpy.array([getattr(msg, "t%d" % i) for i in range(nterms)], dtype=numpy.float)
    return ar

def deserialize_matrix(msg):
    if isinstance(msg, (Matrix3x3.Builder, Matrix3x3.Reader)):
        ar = __deserialize_matrix_n(msg, 9)
        return ar.reshape(3,3)

    elif isinstance(msg, (Matrix4x4.Builder, Matrix4x4.Reader)):
        ar = __deserialize_matrix_n(msg, 16)
        return ar.reshape(4,4)
    else:
        raise TypeError("Can't deserialize matrix type %s" % msg)

def serialize_point2(pt2):
    msg = Point2.new_message()
    msg.x = int(round(pt2.x))
    msg.y = int(round(pt2.y))
    return msg

def deserialize_point2(msg):
    return pcbre.matrix.Point2(msg.x, msg.y)

def serialize_point2f(pt2):
    msg = Point2f.new_message()
    msg.x = float(pt2.x)
    msg.y = float(pt2.y)
    return msg

def deserialize_point2f(msg):
    return pcbre.matrix.Point2(msg.x, msg.y)

class StateError(Exception):
    pass

class SContext:
    def __init__(self):
        self.obj_to_sid = {}
        self.sid_to_obj = {}
        self._id_n = 0

        self.__restoring = False

    def new_sid(self):
        if self.__restoring:
            raise StateError("Can't create SID while restoring")

        self._id_n += 1
        return self._id_n

    def add_deser_fini(self, m):
        assert self.__restoring
        self.__deser_fini.append(m)

    def start_restore(self):
        self.__restoring = True
        self.__deser_fini = []

    def end_restoring(self):
        # Call all finalizers
        for __finalizer in self.__deser_fini:
            __finalizer()

        del self.__deser_fini
        self.__restoring = False
        self._id_n = max([self._id_n] + list(self.sid_to_obj.keys()))

    @contextlib.contextmanager
    def restoring(self):
        self.start_restore()
        yield
        self.end_restoring()

    def key(self, m):
        return id(m)

    def set_sid(self, sid, m):
        if not self.__restoring:
            raise StateError("Must be in restore mode to create objects with SID")
        assert not sid in self.sid_to_obj
        self.sid_to_obj[sid] = m

        self.obj_to_sid[self.key(m)] = sid

    def sid_for(self, m):
        k = self.key(m)
        try:
            return self.obj_to_sid[k]
        except KeyError:
            sid = self.obj_to_sid[k] = self.new_sid()
            self.sid_to_obj[sid] = m
            return sid

    def get(self, sid):
        return self.sid_to_obj[sid]
