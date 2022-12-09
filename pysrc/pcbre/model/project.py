import os
from enum import Enum
from typing import List, Tuple, Sequence, Optional

import pcbre.model.serialization_capnp as ser_capnp
import pcbre.model.serialization_dirtext as ser_dirtext
from pcbre.model.artwork import Artwork
from pcbre.model.const import SIDE
from pcbre.model.imagelayer import ImageLayer, KeyPoint
from pcbre.model.net import Net
from pcbre.model.serialization import PersistentIDRegistry, PersistentIDClass
from pcbre.model.stackup import Layer, ViaPair
from pcbre.model.util import ImmutableListProxy
from pcbre.ui.uimodel import TinySignal


class StorageType(Enum):
    Packed = 0
    Dir = 1




class ProjectIsBadException(Exception):
    def __init__(self, reason: str) -> None:
        self.__reason = reason

    def __str__(self) -> str:
        return self.__reason


class Stackup:

    def __init__(self, project: 'Project') -> None:
        super(Stackup, self).__init__()

        # the serialization code needs to interact with
        # the class internals, so they aren't scoped completely internally
        self._project = project

        # All la
        self._layers: List[Layer] = []
        self._via_pairs: List[ViaPair] = []

        self.layers = ImmutableListProxy(self._layers)
        self.via_pairs = ImmutableListProxy(self._via_pairs)

        self.changed = TinySignal()

    def add_via_pair(self, start_layer: Layer, end_layer: Layer):
        vp = ViaPair(self._project,
                     self._project.unique_id_registry.generate(PersistentIDClass.ViaPair),
                     start_layer,
                     end_layer)

        self._add_via_pair_existing(vp)
        return vp

    def _add_via_pair_existing(self, via_pair: ViaPair) -> None:
        self._via_pairs.append(via_pair)
        self.changed.emit()

    def remove_via_pair(self, via_pair: ViaPair) -> None:
        to_remove = []
        for i in self._project.artwork.vias:
            if i.viapair == via_pair:
                to_remove.append(i)

        for i in to_remove:
            self._project.artwork.remove(i)

        self._via_pairs.remove(via_pair)
        self.changed.emit()

    def via_pair_has_geom(self, via_pair: ViaPair) -> bool:
        for i in self._project.artwork.vias:
            if i.viapair == via_pair:
                return True
        return False

    def via_pair_for_layers(self, layers: Sequence[Layer]) -> Optional[ViaPair]:
        for vp in self.via_pairs:
            first_layer, second_layer = vp.layers
            if all(first_layer.order <= layer.order <= second_layer.order for layer in layers):
                return vp
        return None

    def _renumber_layers(self) -> None:
        for n, i in enumerate(self._layers):
            i.number = n

    def add_layer(self, name: str, color: Tuple[float, float, float]) -> Layer:
        layer = Layer(self._project, self._project.unique_id_registry.generate(PersistentIDClass.Layer), name, color)
        self._add_layer_existing(layer)
        return layer

    def _add_layer_existing(self, layer: Layer) -> None:
        self._layers.append(layer)
        self._renumber_layers()
        self.changed.emit()

    def remove_layer(self, layer: Layer) -> None:
        self._layers.remove(layer)
        self._renumber_layers()
        self.changed.emit()

    def check_layer_has_geom(self, layer: Layer) -> bool:
        for i in self._project.artwork.get_all_artwork():
            if i.layer == layer:
                return True

        return False

    def _order_for_layer(self, layer: Layer) -> int:
        return self._layers.index(layer)

    def set_layer_order(self, layer: Layer, n: int) -> None:
        self._layers.remove(layer)
        self._layers.insert(n, layer)
        self.changed.emit()

    @property
    def top_layer(self) -> Layer:
        return self._layers[0]

    @property
    def bottom_layer(self) -> Layer:
        return self._layers[-1]

    @property
    def both_sides(self) -> Tuple[Layer, Layer]:
        return self._layers[0], self._layers[-1]

    def layer_for_side(self, side: SIDE) -> Layer:
        if side == SIDE.Bottom:
            return self.bottom_layer
        else:
            return self.top_layer

    def side_for_layer(self, layer: Layer) -> Optional[SIDE]:
        if len(self._layers) == 0:
            return None

        if layer == self.bottom_layer:
            return SIDE.Bottom
        elif layer == self.top_layer:
            return SIDE.Top

        return None


class Imagery:
    def __init__(self, project: 'Project') -> None:
        self._project = project

        self._imagelayers: List[ImageLayer] = []
        self._keypoints: List[KeyPoint] = []

        self.imagelayers = ImmutableListProxy(self._imagelayers)
        self.keypoints = ImmutableListProxy(self._keypoints)

    def add_imagelayer(self, imagelayer: ImageLayer) -> None:
        assert imagelayer._project is None or imagelayer._project is self._project
        imagelayer._project = self._project

        if imagelayer.alignment is not None:
            imagelayer.alignment._project = self._project

        self._imagelayers.append(imagelayer)

    def _order_for_layer(self, imagelayer: ImageLayer) -> int:
        return self._imagelayers.index(imagelayer)

    def _set_layer_order(self, imagelayer: ImageLayer, n: int) -> None:
        self._imagelayers.remove(imagelayer)
        self._imagelayers.insert(n, imagelayer)

    def add_keypoint(self, kp: KeyPoint) -> None:
        assert kp._project is None or kp._project is self._project
        kp._project = self._project
        self._keypoints.append(kp)

    def del_keypoint(self, kp: KeyPoint) -> None:
        """
        Remove a keypoint from the project
        :param kp: Keypoint to remove from the project
        :type kp: KeyPoint
        :return:
        """

        assert kp._project is self._project
        # Verify that no layers use the keypoint
        assert len(kp.layer_positions) == 0

        kp._project = None

        self._keypoints.remove(kp)

    def get_keypoint_index(self, kp: KeyPoint) -> int:
        return self.keypoints.index(kp)


class Nets:
    def __init__(self, project: 'Project') -> None:
        super(Nets, self).__init__()

        self._project: Optional[Project] = project

        self._nets: List[Net] = list()
        self.__max_id = 0

        self.nets = ImmutableListProxy(self._nets)

    def new(self) -> Net:
        n = Net(self._project.unique_id_registry.generate(PersistentIDClass.Net))
        self._add_net(n)
        return n

    def _add_net(self, net: Net) -> None:
        """
        Add a net to the project. Sets a transient unused net ID
        :param net: net to be added
        :return:
        """
        assert net._project is None or net._project is self._project

        net._project = self._project
        self.__max_id += 1
        net._id = self.__max_id

        self._nets.append(net)

    def remove_net(self, net: Net) -> None:
        assert net._project == self._project

        # TODO, strip net from all artwork that has it / verify
        self._nets.remove(net)


class Project:

    def __init__(self) -> None:
        self.unique_id_registry = PersistentIDRegistry()

        self.imagery = Imagery(self)

        self.stackup = Stackup(self)
        self.artwork = Artwork(self)

        self.nets = Nets(self)

    @staticmethod
    def create() -> 'Project':
        return Project()

    @staticmethod
    def open(path: os.PathLike, filetype: StorageType) -> 'Project':
        if filetype == StorageType.Packed:
            self = ser_capnp.CapnpIO.open_path(path)
        elif filetype == StorageType.Dir:
            self = ser_dirtext.DirTextIO.open_path(path)
        else:
            raise ValueError("Unknown serialization file type %s" % repr(filetype))
        return self

    @staticmethod
    def open_detect(path: os.PathLike) -> 'Tuple[Project, StorageType]':
        if not os.path.exists(path):
            raise IOError("Path not found")

        if os.path.isdir(path):
            storage_type = StorageType.Dir
        else:
            storage_type = StorageType.Packed

        return Project.open(path, storage_type), storage_type


    def save(self, path: str, filetype: StorageType) -> None:
        if path is None:
            raise ValueError("Must have either a filename, or a save-as path")

        if filetype == StorageType.Packed:
            ser_capnp.CapnpIO.save_path(self, path)
        elif filetype == StorageType.Dir:
            ser_dirtext.DirTextIO.save_path(path, self)
        else:
            raise ValueError("Storage Type not supported")

    def close(self) -> None:
        pass
