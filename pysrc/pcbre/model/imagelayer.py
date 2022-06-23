import cv2  # type: ignore
import os.path
import pcbre.model.serialization as ser
from pcbre.model.serialization import deserialize_matrix, serialize_matrix, serialize_point2, deserialize_point2, \
    serialize_point2f, deserialize_point2f
from pcbre.model.util import ImmutableSetProxy
from pcbre.matrix import project_point, Vec2, Rect
import numpy

from typing import List, Tuple, Set, Optional, Union, TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from pcbre.model.project import Project
    import pcbre.model.serialization as ser
    import numpy.typing as npt


class KeyPoint:
    def __init__(self, project: 'Project', worldpos: Vec2) -> None:
        self.world_position = worldpos
        self._project : Optional['Project'] = project

    @property
    def name(self) -> str:
        return "Keypoint %d" % (self.index + 1)

    @property
    def index(self) -> int:
        assert self._project is not None
        return self._project.imagery.get_keypoint_index(self)

    def serialize(self) -> ser.Keypoint:
        msg = ser.Keypoint.new_message()
        assert self._project is not None
        msg.sid = self._project.scontext.sid_for(self)
        msg.worldPosition = serialize_point2(self.world_position)
        return msg

    @staticmethod
    def deserialize(project: 'Project', msg: ser.Keypoint) -> "KeyPoint":
        worldpos = deserialize_point2(msg.worldPosition)
        obj = KeyPoint(project, worldpos)

        project.scontext.set_sid(msg.sid, obj)
        obj._project = project
        return obj

    @property
    def layer_positions(self) -> List[Tuple['ImageLayer', Vec2]]:
        """
        :return:
        :rtype: list[(ImageLayer, Point2f)]
        """
        layer_positions = []
        # TODO - this should be cached
        assert self._project is not None

        for imagelayer in self._project.imagery.imagelayers:
            if isinstance(imagelayer.alignment, KeyPointAlignment):
                for pos in imagelayer.alignment.keypoint_positions:
                    if pos.key_point is self:
                        layer_positions.append((imagelayer, pos.image_pos))

        return layer_positions


class KeyPointPosition:
    def __init__(self, key_point: KeyPoint, position: Vec2) -> None:
        """
        Represents a point on an image thats tied to a world-position keypoint

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
        self.__keypoint_positions : Set[KeyPointPosition] = set()
        """:type: set[KeyPointPosition]"""

        self.keypoint_positions = ImmutableSetProxy(self.__keypoint_positions)

        self._project : Optional['Project'] = None

    def set_keypoint_position(self, keypoint: KeyPoint, position: Vec2) -> None:
        """
        :param keypoint: Keypoint Position to add
        :return:
        """

        kpp = KeyPointPosition(keypoint, position)

        for old_kpp in self.__keypoint_positions:
            if keypoint == old_kpp.key_point:
                raise ValueError("Error, adding a duplicate keypoint position assignment")

        self.__keypoint_positions.add(kpp)

    def remove_keypoint(self, keypoint: KeyPoint) -> None:
        for old_kpp in list(self.__keypoint_positions):
            if keypoint == old_kpp.key_point:
                self.__keypoint_positions.remove(old_kpp)

    def serialize(self, project: 'Project') -> ser.ImageTransform.KeypointTransformMeta:
        msg = ser.ImageTransform.KeypointTransformMeta.new_message()
        msg.init("keypoints", len(self.__keypoint_positions))
        for n, i in enumerate(self.__keypoint_positions):
            msg.keypoints[n].kpSid = project.scontext.sid_for(i.key_point)
            msg.keypoints[n].position = serialize_point2f(i.image_pos)

        return msg

    @staticmethod
    def deserialize(project: 'Project',
            msg: ser.ImageTransform.KeypointTransformMeta) -> 'KeyPointAlignment':
        obj = KeyPointAlignment()
        for i in msg.keypoints:
            obj.set_keypoint_position(project.scontext.get(i.kpSid), deserialize_point2f(i.position))
        return obj


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

    def serialize(self) -> ser.ImageTransform.RectTransformMeta.Builder:
        msg = ser.ImageTransform.RectTransformMeta.new_message()
        msg.init("handles", 12)
        msg.init("dimHandles", 4)
        msg.init("dims", 2)

        for n, i in enumerate(self.dims):
            msg.dims[n] = i

        msg.lockedToDim = self.dims_locked
        msg.originCorner = {
            0: "lowerLeft",
            1: "lowerRight",
            2: "upperLeft",
            3: "upperRight"}[self.origin_corner]

        msg.originCenter = serialize_point2f(self.origin_center)

        for n, i_a in enumerate(self.handles):
            self.__serialize_handle(i_a, msg.handles[n])

        for n, i_b in enumerate(self.dim_handles):
            self.__serialize_handle(i_b, msg.dimHandles[n])

        msg.flipX = self.flip_x
        msg.flipY = self.flip_y

        return msg

    @staticmethod
    def __serialize_handle(m: Optional[Vec2], to: ser.Handle.Builder) -> None:
        if m is None:
            to.none = None
        else:
            to.point = serialize_point2f(m)

    @staticmethod
    def __deserialize_handle(msg: ser.Handle.Reader) -> Optional[Vec2]:
        if msg.which() == "none":
            return None
        else:
            return deserialize_point2f(msg.point)

    @staticmethod
    def deserialize(msg: ser.ImageTransform.RectTransformMeta.Reader) -> 'RectAlignment':
        handles = [RectAlignment.__deserialize_handle(i) for i in msg.handles]
        dimHandles = [RectAlignment.__deserialize_handle(i) for i in msg.dimHandles]
        dims = [i for i in msg.dims]

        assert len(handles) == 12
        assert len(dimHandles) == 4
        assert len(dims) == 2
        originCorner = {
            "lowerLeft": 0,
            "lowerRight": 1,
            "upperLeft": 2,
            "upperRight": 3}[str(msg.originCorner)]

        originCenter = deserialize_point2f(msg.originCenter)

        return RectAlignment(handles, dimHandles, dims, msg.lockedToDim,
                             originCenter, originCorner, msg.flipX, msg.flipY)


class ImageLayer:
    def __init__(self, project: 'Project',
            name: str, data: bytes, transform_matrix: 'numpy.typing.ArrayLike' =numpy.identity(3)):
        self.__cached_decode : Optional['numpy.typing.NDArray[numpy.uint8]'] = None
        self._project = project
        self.name = name
        self.__data = data
        self.transform_matrix = numpy.array(transform_matrix)
        self.__alignment : Optional[Union[RectAlignment,KeyPointAlignment]] = None
        self.__updated_transform = True

        self.__cached_p2norm = numpy.identity(3)
        self.__cached_norm2p = numpy.identity(3)

    @property
    def alignment(self) -> Optional[Union[RectAlignment,KeyPointAlignment]]:
        return self.__alignment

    def set_alignment(self, align: Optional[Union[RectAlignment,KeyPointAlignment]]) -> None:
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
            buf = numpy.frombuffer(self.data, dtype=numpy.uint8) # type: ignore
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

        self.__cached_norm2p = numpy.linalg.inv(tmat) # type: ignore
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
    def fromFile(project: 'Project', filename: str) -> 'ImageLayer':
        assert os.path.exists(filename)

        basename = os.path.basename(filename)
        return ImageLayer(project, name=basename, data=open(filename, "rb").read())

    def serialize(self) -> 'ser.Image.Builder':
        msg = ser.Image.new_message()
        msg.sid = self._project.scontext.sid_for(self)
        msg.data = self.data
        msg.name = self.name
        m = serialize_matrix(self.transform_matrix)
        msg.transform.matrix = m

        if self.alignment is None:
            # Assign "no-metadata-for-transform"
            msg.transform.meta.noMeta = None
        elif isinstance(self.alignment, KeyPointAlignment):
            msg.transform.meta.init("keypointTransformMeta")
            msg.transform.meta.keypointTransformMeta = self.alignment.serialize(self._project)
        elif isinstance(self.alignment, RectAlignment):
            msg.transform.meta.init("rectTransformMeta")
            msg.transform.meta.rectTransformMeta = self.alignment.serialize()
        else:
            raise NotImplementedError("Don't know how to serialize %s" % self.alignment)

        return msg

    @staticmethod
    def deserialize(project: 'Project', msg: 'ser.Image.Reader') -> 'ImageLayer':
        transform = deserialize_matrix(msg.transform.matrix)
        obj = ImageLayer(project, msg.name, msg.data, transform)

        project.scontext.set_sid(msg.sid, obj)
        obj._project = project

        meta_which = msg.transform.meta.which()
        if meta_which == "noMeta":
            obj.set_alignment(None)
        elif meta_which == "keypointTransformMeta":
            obj.set_alignment(KeyPointAlignment.deserialize(project, msg.transform.meta.keypointTransformMeta))
        elif meta_which == "rectTransformMeta":
            obj.set_alignment(RectAlignment.deserialize(msg.transform.meta.rectTransformMeta))
        else:
            raise NotImplementedError()

        return obj

    def __repr__(self) -> str:
        return "<ImageLayer: %s>" % self.name

    def set_decoded_data(self, ar: 'npt.NDArray[numpy.uint8]') -> None:
        self.__cached_decode = ar
