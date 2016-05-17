from PySide import QtCore
import os
from pcbre.model.const import SIDE

from pcbre.model.net import Net

import pcbre.model.serialization as ser
from pcbre.model.artwork import Artwork
from pcbre.model.change import ModelChange, ChangeType
from pcbre.model.imagelayer import ImageLayer, KeyPoint
from pcbre.model.serialization import SContext
from pcbre.model.stackup import Layer, ViaPair
from pcbre.model.util import ImmutableListProxy


MAGIC = b"PCBRE\x00"
VERSION_MAGIC = b"\x01\x00"

class ProjectConfig(dict):
    def serialize(self):
        pass

    def deserialize(self):
        pass

class ProjectIsBadException(Exception):
    def __init__(self, reason):
        self.__reason = reason

    def __str__(self):
        return self.__reason


class Stackup(QtCore.QObject):
    def __init__(self, project):
        super(Stackup, self).__init__()

        self.__project = project
        self.__layers = []
        self.__via_pairs = []

        self.layers = ImmutableListProxy(self.__layers)
        self.via_pairs = ImmutableListProxy(self.__via_pairs)

    changed = QtCore.Signal(ModelChange)

    def add_via_pair(self, via_pair):
        assert via_pair._project is None
        via_pair._project = self.__project
        self.__via_pairs.append(via_pair)
        self.changed.emit(ModelChange(self.via_pairs, ChangeType.ADD, via_pair))

    def remove_via_pair(self, via_pair):
        assert via_pair._project is self.__project

        raise NotImplementedError("Via Pair removal not finished")
        self.changed.emit(ModelChange(self.via_pairs, ChangeType.REMOVE, via_pair))
        # TODO, check for vias

        self.__via_pairs.erase(via_pair)

    def via_pair_has_geom(self, via_pair):
        raise NotImplementedError("Via Pair geom check not finished")

    def __renumber_layers(self):
        for n, i in enumerate(self.__layers):
            i.number = n

    def add_layer(self, layer):
        assert not layer._project
        layer._project = self.__project
        self.__layers.append(layer)
        self.__renumber_layers()
        self.changed.emit(ModelChange(self.layers, layer, ChangeType.ADD))

    def remove_layer(self, layer):
        assert layer._project == self.__project
        layer._project = None
        self.__layers.remove(layer)
        self.__renumber_layers()
        self.changed.emit(ModelChange(self.layers, layer, ChangeType.REMOVE))

    def check_layer_has_geom(self, layer):
        raise NotImplementedError("Check Layer Geom not finished")

    def _order_for_layer(self, layer):
        return self.__layers.index(layer)

    def set_layer_order(self, layer, n):
        self.__layers.remove(layer)
        self.__layers.insert(n, layer)

    @property
    def top_layer(self):
        return self.__layers[0]

    @property
    def bottom_layer(self):
        return self.__layers[-1]

    @property
    def both_sides(self):
        return self.__layers[0], self.__layers[-1]

    def layer_for_side(self, side):
        if side == SIDE.Bottom:
            return self.bottom_layer
        else:
            return self.top_layer


    def serialize(self):
        _stackup = ser.Stackup.new_message()
        _stackup.init("layers", len(self.__layers))

        for n, i in enumerate(self.__layers):
            _stackup.layers[n] = i.serialize()

        _stackup.init("viapairs", len(self.__via_pairs))
        for n, i in enumerate(self.__via_pairs):
            _stackup.viapairs[n] = i.serialize()

        return _stackup

    def deserialize(self, msg):
        self.__layers.clear()
        for i in msg.layers:
            self.__layers.append(Layer.deserialize(self.__project, i))

        self.__via_pairs.clear()
        for i in msg.viapairs:
            self.__via_pairs.append(ViaPair.deserialize(self.__project, i))

        self.__renumber_layers()


class Imagery:
    def __init__(self, project):
        self.__project = project

        self.__imagelayers = []
        self.__keypoints = []
        """ :type : list[KeyPointPosition] """

        self.imagelayers = ImmutableListProxy(self.__imagelayers)
        self.keypoints = ImmutableListProxy(self.__keypoints)

    def add_imagelayer(self, imagelayer):
        assert not imagelayer._project
        imagelayer._project = self.__project

        if imagelayer.alignment is not None:
            imagelayer.alignment._project = self.__project

        self.__imagelayers.append(imagelayer)

    def _order_for_layer(self, imagelayer):
        return self.__imagelayers.index(imagelayer)

    def _set_layer_order(self, imagelayer, n):
        self.__imagelayers.remove(imagelayer)
        self.__imagelayers.insert(n, imagelayer)

    def add_keypoint(self, kp):
        assert kp._project is None
        kp._project = self.__project
        self.__keypoints.append(kp)

    def del_keypoint(self, kp):
        """
        Remove a keypoint from the project
        :param kp: Keypoint to remove from the project
        :type kp: KeyPoint
        :return:
        """

        assert kp._project is self
        assert len(kp.layer_positions) == 0 # Verify that no layers use the keypoint

        kp._project = None

        self.__keypoints.remove(kp)

    def get_keypoint_index(self, kp):
        return self.keypoints.index(kp)


    def serialize(self):
        imagery = ser.Imagery.new_message()

        imagery.init("imagelayers", len(self.imagelayers))
        for n, i in enumerate(self.imagelayers):
            imagery.imagelayers[n] = i.serialize()

        imagery.init("keypoints", len(self.keypoints))

        for n, i in enumerate(self.keypoints):
            imagery.keypoints[n] = i.serialize()

        return imagery

    def deserialize(self, msg):
        # Keypoints may be used by the imagelayers during deserialize
        # Deserialize first to avoid a finalizer
        for i in msg.keypoints:
            self.__keypoints.append(KeyPoint.deserialize(self.__project, i))

        for i in msg.imagelayers:
            self.__imagelayers.append(ImageLayer.deserialize(self.__project, i))

class Nets(QtCore.QObject):
    changed = QtCore.Signal(ModelChange)

    def __init__(self, project):
        super(Nets, self).__init__()

        self.__project = project

        self.__nets = list()
        self.__max_id = 0

        self.nets = ImmutableListProxy(self.__nets)

    def new(self):
        n = Net()
        self.add_net(n)
        return n

    def add_net(self, net):
        """
        Add a net to the project. Sets a transient unused net ID
        :param net: net to be added
        :return:
        """
        assert net._project is None

        net._project = self.__project
        self.__max_id += 1
        net._id = self.__max_id

        self.__nets.append(net)

        self.changed.emit(ModelChange(self, net, ChangeType.ADD))

    def remove_net(self, net):
        assert net._project == self.__project

        # TODO, strip net from all artwork that has it / verify

        self.changed.emit(ModelChange(self, net, ChangeType.REMOVE))
        self.__nets.remove(net)

    def serialize(self):
        _nets = ser.Nets.new_message()
        _nets.init("netList", len(self.nets))
        for n, i in enumerate(self.nets):
            _nets.netList[n].sid = self.__project.scontext.sid_for(i)
            _nets.netList[n].name = i.name
            _nets.netList[n].nclass = i.net_class

        return _nets

    def deserialize(self, msg):
        for i in msg.netList:
            n = Net(name=i.name, net_class=i.nclass)
            self.__project.scontext.set_sid(i.sid, n)
            self.add_net(n)

class Project:

    def __init__(self):
        self.scontext = SContext()

        self.filepath = None

        self.imagery = Imagery(self)

        self.stackup = Stackup(self)
        self.artwork = Artwork(self)

        self.nets = Nets(self)

    @property
    def can_save(self):
        return self.filepath is not None

    @staticmethod
    def create():
        pass
        return Project()

    def _serialize(self):
        project = ser.Project.new_message()
        project.stackup = self.stackup.serialize()
        project.imagery = self.imagery.serialize()
        project.nets = self.nets.serialize()
        project.artwork = self.artwork.serialize()

        return project

    @staticmethod
    def _deserialize(msg):
        p = Project()
        with p.scontext.restoring():
            p.stackup.deserialize(msg.stackup)
            p.imagery.deserialize(msg.imagery)
            p.nets.deserialize(msg.nets)
            p.artwork.deserialize(msg.artwork)
        return p

    @staticmethod
    def open(path):
        f = open(path, "rb", buffering=0)
        self = Project.open_fd(f)
        self.filepath = path

        return self

    @staticmethod
    def open_fd(fd):
        magic = fd.read(8)
        if magic[:6] != MAGIC:
            raise ValueError("Unknown File Type")

        vers = magic[6:8]
        if vers != VERSION_MAGIC:
            raise ValueError("Unknown File Version")

        _project = ser.Project.read(fd)
        self = Project._deserialize(_project)
        return self

    def save_fd(self, fd):
        fd.write(MAGIC + VERSION_MAGIC)

        message = self._serialize()
        message.write(fd)

    def save(self, path=None, update_path=False):
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
            raise

        if update_path:
            self.filepath = path

        f.flush()
        f.close()


    def close(self):
        pass

def openProject():
    pass
