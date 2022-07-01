import numpy
from pcbre.matrix import project_point, Vec2, Point2, Rect
import pcbre.matrix as M
from typing import TYPE_CHECKING, cast
from qtpy import QtCore
import math
from enum import Enum
from typing import List

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

# ViewPort (TODO: rename) maintains the center, scaling, mirroring and rotation state
#  and calculates all the necessary matricies for rendering and picking

class ViewPort(QtCore.QObject):
    changed = QtCore.Signal()

    def __init__(self, x: int, y: int) -> None:
        super().__init__()

        # _transform defines the mapping from physical (world) coordinates to the projection area
        self.__transform = numpy.identity(3, dtype=numpy.float64)
        
        # Order of operations
        #   Translate (position in world to center of view)
        #   Rotate/Flip
        #   Scale

        # Master variables
        self.__center_point = Point2(0, 0)
        self.__rotate_flip = numpy.identity(3, dtype=numpy.float64)
        self.__scale = 1

        # Initializations for mypy
        self.__w2v = numpy.identity(3, dtype=numpy.float64)
        self.__v2w = numpy.identity(3, dtype=numpy.float64)
        self.__v2n = numpy.identity(3, dtype=numpy.float64)
        self.__n2v = numpy.identity(3, dtype=numpy.float64)

        self.resize(x, y)
        self.__update()

    @staticmethod
    def build_state(center, scale):
        return (center, scale, numpy.identity(3, dtype=numpy.float64))

    # Save/restore
    def get_state(self):
        # Returns an opaque object representing the current view state
        return (self.__center_point.dup(), self.__scale, self.__rotate_flip.copy())

    def set_state(self, state):
        # restores an opaque object retrieved from get_state to the current view state
        self.__center_point, self.__scale, self.__rotate_flip = state

    # Directly set aspects of the viewport
    def set_center(self, center: Point2) -> None:
        self.__center_point = center
        self.__update()

    def set_scale(self, scale: float) -> None:
        self.__scale = scale
        self.__update()

    # Incremental update aspects of the viewport
    def translate(self, delta: Vec2) -> None:
        # Subtract delta because we're moving then center point
        self.__center_point = self.__center_point - delta
        self.__update()

    def rotate(self, angle: float) -> None:
        # Angle is in a clockwise direction
        self.__rotate_flip = M.rotate(math.radians(-angle)) @ self.__rotate_flip
        self.__update()

    def flip(self, axis: int) -> None:
        self.__rotate_flip = M.flip(axis) @ self.__rotate_flip
        self.__update()

    def zoom_at(self, around_point: Point2, factor: float) -> None:
        world_center = self.tfV2W(around_point)

        self.__scale *= factor
        self.__update(suppress=True)

        new_world_center = self.tfV2W(around_point)

        self.translate(new_world_center - world_center)

    def fit_point_cloud(self, points: List[Vec2]):
        new_points = [project_point(self.__rotate_flip, p) for p in points]
        if not new_points:
            return

        r = Rect.from_center_size(new_points.pop())
        for p in new_points:
            r.point_merge(p)

        self.__fit_postrotate_rect(r)

    def __fit_postrotate_rect(self, rect: Rect):
        self.__center_point = project_point(numpy.linalg.inv(self.__rotate_flip), rect.center)
        self.__scale = min(self.__normal_width / rect.width, self.__normal_height / rect.height)
        self.__update()

    @property
    def transform(self) -> 'npt.NDArray[numpy.float64]':
        mat = self.__transform.copy()
        mat.flags.writeable = False
        return mat

    @property
    def scale_factor(self) -> float:
        # TODO: rename - this is the scale to draw a 1px line at
        # Really, we shouldn't use this, and the line thickness should be configurable
        # (HIDPI, nonrectangular displays)
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

    def __update(self, suppress=False) -> None:
        # Elements of the world transform
        scale = M.scale(self.__scale)
        translate = M.translate(-self.__center_point.x, -self.__center_point.y)

        # Calculate the world transform

        self.__transform = scale @ self.__rotate_flip @ translate

        self.__w2v = self.__n2v @ self.transform
        self.__v2w = numpy.linalg.inv(self.__w2v) # type:ignore

        if not suppress:
            self.changed.emit()

    def resize(self, newwidth: int, newheight: int) -> None:
        self.__width = newwidth
        self.__height = newheight

        # Normal device coordinates to viewport matrix
        normal_to_pixels = max(self.__width, self.__height)/2

        self.__normal_width = self.__width / normal_to_pixels
        self.__normal_height = self.__height / normal_to_pixels

        self.__n2v = numpy.array([
            [normal_to_pixels, 0, self.__width/2],
            [0, -normal_to_pixels, self.__height/2],
            [0, 0, 1],
            ])

        self.__v2n = numpy.linalg.inv(self.__n2v) # type:ignore

        self.__update()
