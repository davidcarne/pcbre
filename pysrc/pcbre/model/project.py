import os
from typing import List, Tuple, Sequence, Optional, BinaryIO

import pcbre.model.serialization as ser
from pcbre.model.artwork import Artwork
from pcbre.model.const import SIDE
from pcbre.model.imagelayer import ImageLayer, KeyPoint
from pcbre.model.net import Net
from pcbre.model.serialization import SContext
from pcbre.model.stackup import Layer, ViaPair
from pcbre.model.util import ImmutableListProxy

MAGIC = b"PCBRE\x00"
VERSION_MAGIC = b"\x01\x00"


class ProjectIsBadException(Exception):
    def __init__(self, reason: str) -> None:
        self.__reason = reason

    def __str__(self) -> str:
        return self.__reason


class Stackup:
    def __init__(self, project: 'Project') -> None:
        super(Stackup, self).__init__()

        self.__project = project
        self.__layers: List[Layer] = []
        self.__via_pairs: List[ViaPair] = []

        self.layers = ImmutableListProxy(self.__layers)
        self.via_pairs = ImmutableListProxy(self.__via_pairs)

    def add_via_pair(self, via_pair: ViaPair) -> None:
        self.__via_pairs.append(via_pair)

    def remove_via_pair(self, via_pair: ViaPair) -> None:
        raise NotImplementedError("Via Pair removal not finished")
        # TODO, check for vias

        self.__via_pairs.erase(via_pair)

    def via_pair_has_geom(self, via_pair: ViaPair) -> None:
        raise NotImplementedError("Via Pair geom check not finished")

    def via_pair_for_layers(self, layers: Sequence[Layer]) -> Optional[ViaPair]:
        for vp in self.via_pairs:
            first_layer, second_layer = vp.layers
            if all(first_layer.order <= l.order <= second_layer.order for l in layers):
                return vp
        return None

    def __renumber_layers(self) -> None:
        for n, i in enumerate(self.__layers):
            i.number = n

    def add_layer(self, layer: Layer) -> None:
        self.__layers.append(layer)
        self.__renumber_layers()

    def remove_layer(self, layer: Layer) -> None:
        self.__layers.remove(layer)
        self.__renumber_layers()

    def check_layer_has_geom(self, layer: Layer) -> None:
        raise NotImplementedError("Check Layer Geom not finished")

    def _order_for_layer(self, layer: Layer) -> int:
        return self.__layers.index(layer)

    def set_layer_order(self, layer: Layer, n: int) -> None:
        self.__layers.remove(layer)
        self.__layers.insert(n, layer)

    @property
    def top_layer(self) -> Layer:
        return self.__layers[0]

    @property
    def bottom_layer(self) -> Layer:
        return self.__layers[-1]

    @property
    def both_sides(self) -> Tuple[Layer, Layer]:
        return self.__layers[0], self.__layers[-1]

    def layer_for_side(self, side: SIDE) -> Layer:
        if side == SIDE.Bottom:
            return self.bottom_layer
        else:
            return self.top_layer

    def side_for_layer(self, layer: Layer) -> Optional[SIDE]:
        if layer == self.bottom_layer:
            return SIDE.Bottom
        elif layer == self.top_layer:
            return SIDE.Top

        return None

    def serialize(self) -> ser.Stackup:
        _stackup = ser.Stackup.new_message()
        _stackup.init("layers", len(self.__layers))

        for n, i_l in enumerate(self.__layers):
            _stackup.layers[n] = i_l.serialize()

        _stackup.init("viapairs", len(self.__via_pairs))
        for n, i_vp in enumerate(self.__via_pairs):
            _stackup.viapairs[n] = i_vp.serialize()

        return _stackup

    def deserialize(self, msg: ser.Stackup) -> None:
        self.__layers.clear()
        for i in msg.layers:
            self.__layers.append(Layer.deserialize(self.__project, i))

        self.__via_pairs.clear()
        for i in msg.viapairs:
            self.__via_pairs.append(ViaPair.deserialize(self.__project, i))

        self.__renumber_layers()


class Imagery:
    def __init__(self, project: 'Project') -> None:
        self.__project = project

        self.__imagelayers: List[ImageLayer] = []
        self.__keypoints: List[KeyPoint] = []

        self.imagelayers = ImmutableListProxy(self.__imagelayers)
        self.keypoints = ImmutableListProxy(self.__keypoints)

    def add_imagelayer(self, imagelayer: ImageLayer) -> None:
        print(imagelayer._project, self)
        assert imagelayer._project is None or imagelayer._project is self.__project
        imagelayer._project = self.__project

        if imagelayer.alignment is not None:
            imagelayer.alignment._project = self.__project

        self.__imagelayers.append(imagelayer)

    def _order_for_layer(self, imagelayer: ImageLayer) -> int:
        return self.__imagelayers.index(imagelayer)

    def _set_layer_order(self, imagelayer: ImageLayer, n: int) -> None:
        self.__imagelayers.remove(imagelayer)
        self.__imagelayers.insert(n, imagelayer)

    def add_keypoint(self, kp: KeyPoint) -> None:
        assert kp._project is None or kp._project is self.__project
        kp._project = self.__project
        self.__keypoints.append(kp)

    def del_keypoint(self, kp: KeyPoint) -> None:
        """
        Remove a keypoint from the project
        :param kp: Keypoint to remove from the project
        :type kp: KeyPoint
        :return:
        """

        assert kp._project is self.__project
        # Verify that no layers use the keypoint
        assert len(kp.layer_positions) == 0

        kp._project = None

        self.__keypoints.remove(kp)

    def get_keypoint_index(self, kp: KeyPoint) -> int:
        return self.keypoints.index(kp)

    def serialize(self) -> ser.Imagery:
        imagery = ser.Imagery.new_message()

        imagery.init("imagelayers", len(self.imagelayers))
        for n, i in enumerate(self.imagelayers):
            imagery.imagelayers[n] = i.serialize()

        imagery.init("keypoints", len(self.keypoints))

        for n, i_ in enumerate(self.keypoints):
            imagery.keypoints[n] = i_.serialize()

        return imagery

    def deserialize(self, msg: ser.Imagery) -> None:
        # Keypoints may be used by the imagelayers during deserialize
        # Deserialize first to avoid a finalizer
        for i in msg.keypoints:
            self.__keypoints.append(KeyPoint.deserialize(self.__project, i))

        for i in msg.imagelayers:
            self.__imagelayers.append(ImageLayer.deserialize(self.__project, i))


class Nets:
    def __init__(self, project: 'Project') -> None:
        super(Nets, self).__init__()

        self.__project: Optional[Project] = project

        self.__nets: List[Net] = list()
        self.__max_id = 0

        self.nets = ImmutableListProxy(self.__nets)

    def new(self) -> Net:
        n = Net()
        self.add_net(n)
        return n

    def add_net(self, net: Net) -> None:
        """
        Add a net to the project. Sets a transient unused net ID
        :param net: net to be added
        :return:
        """
        assert net._project is None or net._project is self.__project

        net._project = self.__project
        self.__max_id += 1
        net._id = self.__max_id

        self.__nets.append(net)

    def remove_net(self, net: Net) -> None:
        assert net._project == self.__project

        # TODO, strip net from all artwork that has it / verify
        self.__nets.remove(net)

    def serialize(self) -> ser.Nets:
        assert self.__project is not None

        _nets = ser.Nets.new_message()
        _nets.init("netList", len(self.nets))
        for n, i in enumerate(self.nets):
            _nets.netList[n].sid = self.__project.scontext.sid_for(i)
            _nets.netList[n].name = i.name
            _nets.netList[n].nclass = i.net_class

        return _nets

    def deserialize(self, msg: ser.Nets) -> None:
        assert self.__project is not None

        for i in msg.netList:
            n = Net(name=i.name, net_class=i.nclass)
            self.__project.scontext.set_sid(i.sid, n)
            self.add_net(n)


class Project:

    def __init__(self) -> None:
        self.scontext = SContext()

        self.filepath: Optional[str] = None

        self.imagery = Imagery(self)

        self.stackup = Stackup(self)
        self.artwork = Artwork(self)

        self.nets = Nets(self)

    @property
    def can_save(self) -> bool:
        return self.filepath is not None

    @staticmethod
    def create() -> 'Project':
        return Project()

    def _serialize(self) -> ser.Project:
        project = ser.Project.new_message()
        project.stackup = self.stackup.serialize()
        project.imagery = self.imagery.serialize()
        project.nets = self.nets.serialize()
        project.artwork = self.artwork.serialize()

        return project

    @staticmethod
    def _deserialize(msg: ser.Project) -> 'Project':
        p = Project()
        with p.scontext.restoring():
            p.stackup.deserialize(msg.stackup)
            p.imagery.deserialize(msg.imagery)
            p.nets.deserialize(msg.nets)
            p.artwork.deserialize(msg.artwork)
        return p

    @staticmethod
    def open(path: str) -> 'Project':
        f = open(path, "rb", buffering=0)
        self = Project.open_fd(f)
        self.filepath = path

        return self

    @staticmethod
    def open_fd(fd: BinaryIO) -> 'Project':
        magic = fd.read(8)
        if magic[:6] != MAGIC:
            raise ValueError("Unknown File Type")

        vers = magic[6:8]
        if vers != VERSION_MAGIC:
            raise ValueError("Unknown File Version")

        _project = ser.Project.read(fd)
        self = Project._deserialize(_project)
        return self

    def save_fd(self, fd: BinaryIO) -> None:
        fd.write(MAGIC + VERSION_MAGIC)

        message = self._serialize()
        message.write(fd)

    def save(self, path: Optional[str] = None, update_path: bool = False) -> None:
        if path is None:
            path = self.filepath

        if path is None:
            raise ValueError("Must have either a filename, or a save-as path")

        bakname = path + ".bak"
        try:
            bakname = path + ".bak"

            if os.path.exists(bakname):
                os.unlink(bakname)

            if os.path.exists(path):
                os.rename(path, bakname)
        except (IOError, OSError):
            raise IOError("Couldn't manipulate backup file")

        f = open(path, "w+b", buffering=0)
        try:
            self.save_fd(f)
        except Exception as e:
            os.unlink(path)
            os.rename(bakname, path)
            raise e

        if update_path:
            self.filepath = path

        f.flush()
        f.close()

    def close(self) -> None:
        pass
