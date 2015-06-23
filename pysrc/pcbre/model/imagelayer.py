import cv2
from pcbre.matrix import projectPoint, Point2
import numpy
import os.path
import pcbre.model.serialization as ser
from pcbre.model.serialization import deserialize_matrix, serialize_matrix, serialize_point2, deserialize_point2, \
    serialize_point2f, deserialize_point2f
from pcbre.model.util import ImmutableListProxy


class KeyPoint:
    def __init__(self, worldpos):
        self._project = None
        self.world_position = worldpos
        pass

    @property
    def name(self):
        return "Keypoint %d" % (self.index + 1)

    @property
    def index(self):
        return self._project.imagery.get_keypoint_index(self)

    def serialize(self):
        msg = ser.Keypoint.new_message()
        msg.sid = self._project.scontext.sid_for(self)
        msg.worldPosition = serialize_point2(self.world_position)
        return msg

    @staticmethod
    def deserialize(project, msg):
        worldpos = deserialize_point2(msg.worldPosition)
        obj = KeyPoint(worldpos)

        project.scontext.set_sid(msg.sid, obj)
        obj._project = project
        return obj

    @property
    def layer_positions(self):
        """
        :return:
        :rtype: list[(ImageLayer, Point2f)]
        """
        layer_positions = []
        # TODO - this should be cached
        for imagelayer in self._project.imagery.imagelayers:
            if isinstance(imagelayer.alignment, KeyPointAlignment):
                for pos in imagelayer.alignment.keypoint_positions:
                    if pos.key_point is self:
                        layer_positions.append((imagelayer, pos.image_pos))

        return layer_positions




class KeyPointPosition:
    def __init__(self, key_point, position):
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
    def __init__(self):
        self._project = None
        self.__keypoint_positions = set()
        """:type: set[KeyPointPosition]"""

        self.keypoint_positions = ImmutableListProxy(self.__keypoint_positions)

    def set_keypoint_position(self, keypoint, position):
        """
        :param kpp: Keypoint Position to add
        :type kpp: KeyPointPosition
        :return:
        """

        kpp = KeyPointPosition(keypoint, position)

        for old_kpp in self.__keypoint_positions:
            if keypoint == old_kpp.key_point:
                raise ValueError("Error, adding a duplicate keypoint position assignment")

        self.__keypoint_positions.add(kpp)

    def remove_keypoint(self, keypoint):
        for old_kpp in list(self.__keypoint_positions):
            if keypoint == old_kpp.key_point:
                self.__keypoint_positions.remove(old_kpp)

    def serialize(self):
        msg = ser.ImageTransform.KeypointTransformMeta.new_message()
        msg.init("keypoints", len(self.__keypoint_positions))
        for n, i in enumerate(self.__keypoint_positions):
            msg.keypoints[n].kpSid = self._project.scontext.sid_for(i.key_point)
            msg.keypoints[n].position = serialize_point2f(i.image_pos)

        return msg

    @staticmethod
    def deserialize(project, msg):
        obj = KeyPointAlignment()
        for i in msg.keypoints:
            obj.set_keypoint_position(project.scontext.get(i.kpSid), deserialize_point2f(i.position))
        return obj

class RectAlignment:
    def __init__(self, handles, dim_handles, dims, dims_locked, origin_center, origin_corner, flip_x, flip_y):
        self._project = None
        self.handles = handles
        self.dim_handles = dim_handles
        self.dims = dims
        self.dims_locked = dims_locked
        self.origin_center = origin_center
        self.origin_corner = origin_corner

        self.flip_x = flip_x
        self.flip_y = flip_y

    def serialize(self):
        msg = ser.ImageTransform.RectTransformMeta.new_message()
        msg.init("handles", 12)
        msg.init("dimHandles", 4)
        msg.init("dims", 2)

        for n, i in enumerate(self.dims):
            msg.dims[n] = i

        msg.lockedToDim = self.dims_locked
        msg.originCorner = {0:"lowerLeft", 1:"lowerRight", 2:"upperLeft", 3:"upperRight"}[self.origin_corner]
        msg.originCenter = serialize_point2f(self.origin_center)

        for n, i in enumerate(self.handles):
            self.__serialize_handle(i, msg.handles[n])

        for n, i in enumerate(self.dim_handles):
            self.__serialize_handle(i, msg.dimHandles[n])

        msg.flipX = self.flip_x
        msg.flipY = self.flip_y

        return msg

    @staticmethod
    def __serialize_handle(m, to):
        if m is None:
            to.none = None
        else:
            to.point = serialize_point2f(m)


    @staticmethod
    def __deserialize_handle(msg):
        if msg.which() == "none":
            return None
        else:
            return deserialize_point2f(msg.point)


    @staticmethod
    def deserialize(msg):
        handles = [ RectAlignment.__deserialize_handle(i) for i in msg.handles]
        dimHandles = [ RectAlignment.__deserialize_handle(i) for i in msg.dimHandles]
        dims = [i for i in msg.dims]

        assert len(handles) == 12
        assert len(dimHandles) == 4
        assert len(dims) == 2
        originCorner = {"lowerLeft": 0, "lowerRight": 1, "upperLeft" : 2, "upperRight": 3}[str(msg.originCorner)]
        originCenter = deserialize_point2f(msg.originCenter)

        return RectAlignment(handles, dimHandles, dims, msg.lockedToDim,
                             originCenter, originCorner, msg.flipX, msg.flipY)

class ImageLayer:
    def __init__(self, name, data, transform_matrix = numpy.identity(3)):
        self.__cached_decode = None
        self._project = None
        self.name = name
        self.__data = data
        self.transform_matrix = transform_matrix
        self.__alignment = None

    @property
    def alignment(self):
        return self.__alignment

    def set_alignment(self, align):
        """
        Sets information on how the imagelayer was aligned. The transformmatrix is still the precise transform
        that was calculated from the alignment data, but this info is kept around to allow for re-alignment
        :param align:
        :return:
        """

        # Remove any existing alignment
        if self.alignment:
            self.alignment._project = None
            self.__alignment = None

        # And set the new alignment
        if align is not None:
            assert align._project is None
            align._project = self._project
        self.__alignment = align

    @property
    def data(self):
        """
        :return: raw (compressed) image file
        """
        return self.__data

    @property
    def decoded_image(self):
        if self.__cached_decode is None:
            im = cv2.imdecode(numpy.frombuffer(self.data, dtype=numpy.uint8), 1)
            im.flags.writeable = False
            self.__cached_decode = im

        return self.__cached_decode


    def __calculate_transform_matrix(self):
        if hasattr(self, "__cached_p2norm"):
            return

        # Calculate a default transform matrix
        max_dim = float(max(self.__cached_decode.shape))
        sf = 2./max_dim
        tmat = numpy.array([
                               [sf, 0, -self.__cached_decode.shape[1]/max_dim],
                               [0, sf, -self.__cached_decode.shape[0]/max_dim],
                               [0,  0, 1]], dtype=numpy.float32)
        self.__cached_p2norm = tmat
        self.__cached_norm2p = numpy.linalg.inv(tmat)


    """ Transform matricies from pixel-space to normalized image space (-1..1) """
    @property
    def pixel_to_normalized(self):
        self.__calculate_transform_matrix()
        return self.__cached_p2norm

    @property
    def normalized_to_pixel(self):
        self.__calculate_transform_matrix()
        return self.__cached_norm2p

    def p2n(self, pt):
        return projectPoint(self.pixel_to_normalized, pt)

    def n2p(self, pt):
        return projectPoint(self.normalized_to_pixel, pt)

    @staticmethod
    def fromFile(project, filename):
        assert os.path.exists(filename)

        im = cv2.imdecode(numpy.fromfile(filename, dtype=numpy.uint8), 1)
        tmat = numpy.identity(3)
        basename = os.path.basename(filename)
        return ImageLayer(name=basename, data=open(filename, "rb").read())

    @property
    def keypoint_positions(self):
        return self._project.imagery.keypoint_positions_for_layer(self)

    def serialize(self):
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
            msg.transform.meta.keypointTransformMeta = self.alignment.serialize()
        elif isinstance(self.alignment, RectAlignment):
            msg.transform.meta.init("rectTransformMeta")
            msg.transform.meta.rectTransformMeta = self.alignment.serialize()
        else:
            raise NotImplementedError("Don't know how to serialize %s" % self.alignment)

        return msg

    @staticmethod
    def deserialize(project, msg):
        transform = deserialize_matrix(msg.transform.matrix)
        obj = ImageLayer(msg.name, msg.data, transform)

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

    def __repr__(self):
        return "<ImageLayer: %s>" % self.name

    def set_decoded_data(self, ar):
        self.__cached_decode = ar


