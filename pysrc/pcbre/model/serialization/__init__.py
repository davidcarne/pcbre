# DO NOT REMOVE FOLLOWING IMPORT
# side effect sets up capnp class loader
import capnp  # type: ignore

# The classes imported here are used elsewhere
import pcbre.model.serialization.pcbre_capnp  # type: ignore

from .pcbre_capnp import Project, Stackup, ViaPair, Layer, Color3f, Artwork, Imagery, \
    Net, Nets, Image, ImageTransform, Matrix3x3, Matrix4x4, Point2, Point2f, Keypoint, ImageTransform, Component, Handle
from typing import Tuple, Any, Union, Callable, Dict, List, Generator, TYPE_CHECKING

import pcbre.matrix
import contextlib
import numpy


if TYPE_CHECKING:
    import numpy.typing as npt


def serialize_color3f(color: Tuple[float, float, float]) -> Color3f:
    msg = Color3f.new_message()

    msg.r, msg.g, msg.b = map(float, color)

    return msg


def float_lim(v: float) -> float:
    v = float(v)
    if v < 0:
        return 0
    if v > 1:
        return 1
    return v


def deserialize_color3f(msg: Color3f) -> Tuple[float, float, float]:
    return float_lim(msg.r), float_lim(msg.g), float_lim(msg.b)


def __serialize_matrix(msg: Matrix3x3.Builder, mat: 'npt.NDArray[numpy.float64]') -> None:
    m_r = mat.flatten()

    for n, i in enumerate(m_r):
        setattr(msg, "t%d" % n, float(i))


def serialize_matrix(mat: 'npt.NDArray[numpy.float64]') -> Union[Matrix3x3.Builder, Matrix4x4.Builder]:
    if mat.shape == (3, 3):
        m = Matrix3x3.new_message()

    elif mat.shape == (4, 4):
        m = Matrix4x4.new_message()
    else:
        raise TypeError("Cannot serialize matrix of shape %s" % mat.shape)
    __serialize_matrix(m, mat)
    return m


def __deserialize_matrix_n(msg: Union[Matrix3x3.Reader, Matrix4x4.Reader], nterms: int) -> 'npt.NDArray[numpy.float64]':
    ar = numpy.array([getattr(msg, "t%d" % i) for i in range(nterms)], dtype=numpy.float64)
    return ar


def deserialize_matrix(msg: Union[Matrix3x3.Reader, Matrix4x4.Reader]) -> 'npt.NDArray[numpy.float64]':
    if isinstance(msg, (Matrix3x3.Builder, Matrix3x3.Reader)):
        ar = __deserialize_matrix_n(msg, 9)
        return ar.reshape(3, 3)

    elif isinstance(msg, (Matrix4x4.Builder, Matrix4x4.Reader)):
        ar = __deserialize_matrix_n(msg, 16)
        return ar.reshape(4, 4)
    else:
        raise TypeError("Can't deserialize matrix type %s" % msg)


def serialize_point2(pt2: pcbre.matrix.Vec2) -> Point2:
    msg = Point2.new_message()
    msg.x = int(round(pt2.x))
    msg.y = int(round(pt2.y))
    return msg

def deserialize_point2(msg: Point2) -> pcbre.matrix.Vec2:
    return pcbre.matrix.Point2(msg.x, msg.y)


def serialize_point2f(pt2: pcbre.matrix.Vec2) -> Point2f:
    msg = Point2f.new_message()
    msg.x = float(pt2.x)
    msg.y = float(pt2.y)
    return msg


def deserialize_point2f(msg: Point2f) -> pcbre.matrix.Point2:
    return pcbre.matrix.Point2(msg.x, msg.y)


class StateError(Exception):
    pass


class SContext:
    def __init__(self) -> None:
        self.obj_to_sid : Dict[Any, int] = {}
        self.sid_to_obj : Dict[int, Any] = {}
        self._id_n = 0

        self.__restoring = False

    def new_sid(self) -> int:
        if self.__restoring:
            raise StateError("Can't create SID while restoring")

        self._id_n += 1
        return self._id_n

    def add_deser_fini(self, m: Callable[[], None]) -> None:
        assert self.__restoring
        self.__deser_fini.append(m)

    def start_restore(self) -> None:
        self.__restoring = True
        self.__deser_fini : List[Callable[[], None]] = []

    def end_restoring(self) -> None:
        # Call all finalizers
        for __finalizer in self.__deser_fini:
            __finalizer()

        del self.__deser_fini
        self.__restoring = False
        self._id_n = max([self._id_n] + list(self.sid_to_obj.keys()))

    @contextlib.contextmanager
    def restoring(self) -> Generator[None, None, None]:
        self.start_restore()
        yield
        self.end_restoring()

    def key(self, m: Any) -> int:
        return id(m)

    def set_sid(self, sid: int, m: Any) -> None:
        if not self.__restoring:
            raise StateError("Must be in restore mode to create objects with SID")
        assert sid not in self.sid_to_obj
        self.sid_to_obj[sid] = m

        self.obj_to_sid[self.key(m)] = sid

    def sid_for(self, m: Any) -> int:
        k = self.key(m)
        try:
            return self.obj_to_sid[k]
        except KeyError:
            sid = self.obj_to_sid[k] = self.new_sid()
            self.sid_to_obj[sid] = m
            return sid

    def get(self, sid: int) -> Any:
        return self.sid_to_obj[sid]
