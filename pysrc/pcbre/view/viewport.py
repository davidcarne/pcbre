import numpy
from pcbre.matrix import project_point, Vec2, Point2
import pcbre.matrix as M
from typing import TYPE_CHECKING, cast
from qtpy import QtCore
import math

if TYPE_CHECKING:
    import numpy.typing as npt

# We use 3 types of coordinates:
# V - Viewport Coordinates - coords in the on-screen viewport. QT-style.
#    Used for mouse-picking, rendering handles/controls
#    0,0 = top-left
#    size.width(), size.height() = bottom-right
#

# N - Natural Device Coordinates - OpenGL style coordinates
#    Pretty useless, but we need to deal with them
#    0,0 = bottom-left
#    1,1 = top-right
#
# W - World coords. World coordinates are in um
#

class ViewPort(QtCore.QObject):
    changed = QtCore.Signal()

    def __init__(self, x: int, y: int) -> None:
        super().__init__()

        # _transform defines the mapping from physical (world) coordinates to the projection area
        self.__transform = numpy.identity(3, dtype=numpy.float64)
        self.__scale_factor : float = 1

        # Initializations for mypy
        self.__w2v = numpy.identity(3, dtype=numpy.float64)
        self.__v2w = numpy.identity(3, dtype=numpy.float64)
        self.__v2n = numpy.identity(3, dtype=numpy.float64)
        self.__n2v = numpy.identity(3, dtype=numpy.float64)

        self.resize(x, y)
        self.transform = numpy.identity(3, dtype=numpy.float64)
        self.__update()

    def rotate(self, angle: float) -> None:
        self.transform = M.rotate(math.radians(angle)) @ self.transform

    # Flip the viewport 
    def flip(self, axis: int) -> None:
        self.transform = M.flip(axis) @ self.transform

    def zoom_at(self, around_point: Point2, factor: float) -> None:
        world_center = self.tfV2W(around_point)

        ndc_orig_center = project_point(self.transform, world_center)
        new_transform = M.scale(factor) @ self.transform
        ndc_new_center = project_point(new_transform, world_center)

        ndc_dx = ndc_new_center[0] - ndc_orig_center[0]
        ndc_dy = ndc_new_center[1] - ndc_orig_center[1]

        self.transform =  M.translate(-ndc_dx, -ndc_dy) @ new_transform

    #def fit_bbox(

    @property
    def transform(self) -> 'npt.NDArray[numpy.float64]':
        mat = self.__transform.copy()
        mat.flags.writeable = False
        return mat

    @transform.setter
    def transform(self, value: 'npt.NDArray[numpy.float64]') -> None:
        if (self.__transform == value).all():
            return

        self.__transform = value
        self.__update()
        self.changed.emit()

    @property
    def scale_factor(self) -> float:
        return self.__scale_factor

    # Forward Matrix (world to viewport)
    @property
    def fwdMatrix(self) -> 'npt.NDArray[numpy.float64]':
        return self.__w2v

    # GL Matrix - world to natural device coordinates
    @property
    def glMatrix(self) -> 'npt.NDArray[numpy.float64]':
        return self.transform

    # GLWMatrix - transform from viewport space to normalized device space
    @property
    def glWMatrix(self) -> 'npt.NDArray[numpy.float64]':
        return self.__v2n

    @property
    def revMatrix(self) -> 'npt.NDArray[numpy.float64]':
        return self.__v2w

    @property
    def width(self) -> int:
        return self.__width

    @property
    def height(self) -> int:
        return self.__height

    def tfW2V(self, pt: Vec2) -> Vec2:
        return project_point(self.fwdMatrix, pt)

    def tfV2W(self, pt: Vec2) -> Vec2:
        return project_point(self.revMatrix, pt)

    def __update(self) -> None:
        self.__w2v = self.__n2v @ self.transform
        self.__v2w = numpy.linalg.inv(self.__w2v) # type:ignore

        # mypy safe
        self.__scale_factor = max(map(abs, [self.fwdMatrix[0][0], self.fwdMatrix[0][1], self.fwdMatrix[1][0], self.fwdMatrix[1][1]]))  # type: ignore

    def resize(self, newwidth: int, newheight: int) -> None:
        self.__width = newwidth
        self.__height = newheight

        # Natural device coordinates to viewport matrix
        rs = max(self.__width, self.__height)/2
        self.__n2v = numpy.array([
            [rs, 0, self.__width/2],
            [0, -rs, self.__height/2],
            [0, 0, 1],
            ])

        self.__v2n = numpy.linalg.inv(self.__n2v) # type:ignore

        self.__update()
