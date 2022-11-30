import cv2  # type: ignore
import os.path
from pcbre.model.util import ImmutableSetProxy
from pcbre.matrix import project_point, Vec2
import numpy

from typing import List, Tuple, Set, Optional, Union, TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from pcbre.model.project import Project
    import numpy.typing as npt


class KeyPoint:
    def __init__(self, project: 'Project', world_position: Vec2) -> None:
        self.world_position = world_position
        self._project: Optional['Project'] = project

    @property
    def name(self) -> str:
        return "Keypoint %d" % (self.index + 1)

    @property
    def index(self) -> int:
        assert self._project is not None
        return self._project.imagery.get_keypoint_index(self)

    @property
    def layer_positions(self) -> List[Tuple['ImageLayer', Vec2]]:
        """
        :return:
        :rtype: list[(ImageLayer, Point2f)]
        """
        layer_positions = []
        # TODO - this should be cached
        assert self._project is not None

        for image_layer in self._project.imagery.imagelayers:
            if isinstance(image_layer.alignment, KeyPointAlignment):
                for pos in image_layer.alignment.keypoint_positions:
                    if pos.key_point is self:
                        layer_positions.append((image_layer, pos.image_pos))

        return layer_positions


class KeyPointPosition:
    def __init__(self, key_point: KeyPoint, position: Vec2) -> None:
        """
        Represents a point on an image that's tied to a world-position keypoint
        :param key_point:
        :type key_point: KeyPoint
        :param position:
        :type position: Point2
        :return:
        """
        self.key_point = key_point
        self.image_pos = position


class KeyPointAlignment:
    def __init__(self) -> None:
        self._keypoint_positions: Set[KeyPointPosition] = set()
        """:type: set[KeyPointPosition]"""

        self.keypoint_positions = ImmutableSetProxy(self._keypoint_positions)

        self._project: Optional['Project'] = None

    def set_keypoint_position(self, keypoint: KeyPoint, position: Vec2) -> None:
        """
        :param keypoint: keypoint that is being modified
        :param position: target position in world space
        :return:
        """

        kpp = KeyPointPosition(keypoint, position)

        for old_kpp in self._keypoint_positions:
            if keypoint == old_kpp.key_point:
                raise ValueError("Error, adding a duplicate keypoint position assignment")

        self._keypoint_positions.add(kpp)

    def remove_keypoint(self, keypoint: KeyPoint) -> None:
        for old_kpp in list(self._keypoint_positions):
            if keypoint == old_kpp.key_point:
                self._keypoint_positions.remove(old_kpp)


class RectAlignment:
    def __init__(self,
                 handles: Iterable[Optional[Vec2]], dim_handles: Iterable[Optional[Vec2]],
                 dims: Iterable[float], dims_locked: bool,
                 origin_center: Vec2, origin_corner: int, flip_x: bool, flip_y: bool):

        self._project = None
        self.handles = list(handles)
        self.dim_handles = list(dim_handles)
        self.dims = list(dims)
        self.dims_locked = dims_locked
        self.origin_center = origin_center
        self.origin_corner = origin_corner

        self.flip_x = flip_x
        self.flip_y = flip_y


class ImageLayer:
    def __init__(self, project: 'Project',
                 name: str, data: bytes, transform_matrix: 'numpy.typing.ArrayLike' = numpy.identity(3)):

        self.__cached_decode: Optional['numpy.typing.NDArray[numpy.uint8]'] = None
        self._project = project
        self.name = name
        self.__data = data
        self.transform_matrix = numpy.array(transform_matrix)
        self.__alignment: Optional[Union[RectAlignment, KeyPointAlignment]] = None
        self.__updated_transform = True

        self.__cached_p2norm = numpy.identity(3)
        self.__cached_norm2p = numpy.identity(3)

    @property
    def alignment(self) -> Optional[Union[RectAlignment, KeyPointAlignment]]:
        return self.__alignment

    def set_alignment(self, align: Optional[Union[RectAlignment, KeyPointAlignment]]) -> None:
        """
        Sets information on how the imagelayer was aligned. The transformmatrix is still the precise transform
        that was calculated from the alignment data, but this info is kept around to allow for re-alignment
        :param align:
        :return:
        """
        # And set the new alignment
        self.__alignment = align

    @property
    def data(self) -> bytes:
        """
        :return: raw (compressed) image file
        """
        return self.__data

    @property
    # TODO: image decoded type
    def decoded_image(self) -> 'numpy.typing.NDArray[numpy.uint8]':
        if self.__cached_decode is None:
            buf = numpy.frombuffer(self.data, dtype=numpy.uint8)  # type: ignore
            im = cv2.imdecode(buf, 1)
            im.flags.writeable = False
            self.__cached_decode = im

        return self.__cached_decode

    def get_corner_points(self) -> List[Vec2]:
        # Normalized_dims
        max_dim = float(max(self.__cached_decode.shape))
        x = self.__cached_decode.shape[1]/max_dim
        y = self.__cached_decode.shape[0]/max_dim

        corners = (
                (-1, -1),
                (-1, 1),
                (1, 1),
                (1, -1))

        # Rectangle in pixel space
        corners_pixspace = [
                Vec2(mx * x, my * y) for mx, my in corners
                ]

        # Possibly non-rectangular corner points
        corners_norm = [
                project_point(self.transform_matrix, p) for p in corners_pixspace
                ]

        return corners_norm

    def __calculate_transform_matrix(self) -> None:
        if self.__updated_transform:
            return

        if self.__cached_decode is None:
            raise ValueError("transform matrix is not asserted")

        # Calculate a default transform matrix
        max_dim = float(max(self.__cached_decode.shape))
        sf = 2./max_dim
        tmat = numpy.array([
                               [sf, 0, -self.__cached_decode.shape[1]/max_dim],
                               [0, sf, -self.__cached_decode.shape[0]/max_dim],
                               [0,  0, 1]], dtype=numpy.float64)
        self.__cached_p2norm = tmat

        self.__cached_norm2p = numpy.linalg.inv(tmat)  # type: ignore
        self.__updated_transform = True

    """ Transform matricies from pixel-space to normalized image space (-1..1) """
    @property
    def pixel_to_normalized(self) -> 'npt.NDArray[numpy.float64]':
        self.__calculate_transform_matrix()
        return self.__cached_p2norm

    @property
    def normalized_to_pixel(self) -> 'npt.NDArray[numpy.float64]':
        self.__calculate_transform_matrix()
        return self.__cached_norm2p

    def p2n(self, pt: Vec2) -> Vec2:
        return project_point(self.pixel_to_normalized, pt)

    def n2p(self, pt: Vec2) -> Vec2:
        return project_point(self.normalized_to_pixel, pt)

    @staticmethod
    def from_file(project: 'Project', filename: str) -> 'ImageLayer':
        assert os.path.exists(filename)

        basename = os.path.basename(filename)
        return ImageLayer(project, name=basename, data=open(filename, "rb").read())

    def __repr__(self) -> str:
        return "<ImageLayer: %s>" % self.name

    def set_decoded_data(self, ar: 'npt.NDArray[numpy.uint8]') -> None:
        self.__cached_decode = ar
