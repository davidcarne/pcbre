from collections import defaultdict
from pcbre.matrix import translate, rotate, cflip, Vec2
from pcbre.model.const import SIDE, TFF
from pcbre.model.serialization import deserialize_point2, serialize_point2

from typing import Dict, Optional, Sequence, TYPE_CHECKING
if TYPE_CHECKING:
    from pcbre.model.net import Net
    from pcbre.model.pad import Pad
    from pcbre.model.project import Project
    import numpy
    import pcbre.model.serialization as ser
    from pcbre.matrix import Rect
    import numpy.typing as npt


class Component:
    TYPE_FLAGS = TFF.HAS_INST_INFO

    def __init__(self, 
                 project: 'Project',
                 center: Vec2, 
                 theta: float, side: SIDE, 
                 name_mapping: Optional[Dict[str, str]] = None,
                 refdes: str ="", 
                 partno: str ="",
                 side_layer_oracle: Optional['Project']=None) -> None:

        self.side = side
        self.theta = theta
        self.center = center

        self.refdes: str = refdes
        self.partno: str = partno

        self.name_mapping: Dict[str, str] = dict() if name_mapping is None else name_mapping
        self.net_mapping: Dict[str, Optional['Net']] = defaultdict(lambda: None)

        self.__side_layer_oracle = side_layer_oracle
        self._project: 'Project' = project

    @property
    def _side_layer_oracle(self) -> 'Project':
        if self._project is not None:
            return self._project

        return self.__side_layer_oracle

    @property
    def matrix(self) -> 'npt.NDArray[numpy.float64]':
        return translate(self.center.x, self.center.y) @ (rotate(self.theta) @ (cflip(self.side == SIDE.Bottom)))

    def get_pads(self) -> Sequence['Pad']:
        raise NotImplementedError()

    def pin_name_for_no(self, pinno: str) -> str:
        """

        :param pinno: String "pin number". The pin number is a unique identifier for the pin/ball/land of the IC
                      can be numeric or alnum. Must be unique
        :type pinno: str
        :return:
        """
        assert isinstance(pinno, str)
        if pinno not in self.name_mapping:
            return ""
        return self.name_mapping[pinno]

    def set_pin_name_for_no(self, pinno: str, value: str) -> None:
        assert isinstance(pinno, str)
        self.name_mapping[pinno] = value

    def net_for_pad_no(self, pinno: str) -> Optional['Net']:
        return self.net_mapping[pinno]

    def set_net_for_pad_no(self, pinno: str, value: Optional['Net']) -> None:
        self.net_mapping[pinno] = value

    def _serializeTo(self, cmp_msg: 'ser.Component.Builder') -> None:
        if self.side == SIDE.Top:
            cmp_msg.side = "top"
        elif self.side == SIDE.Bottom:
            cmp_msg.side = "bottom"
        else:
            raise NotImplementedError()

        cmp_msg.refdes = self.refdes
        cmp_msg.partno = self.partno

        cmp_msg.center = serialize_point2(self.center)
        cmp_msg.theta = float(self.theta)
        cmp_msg.sid = self._project.scontext.sid_for(self)

        cmp_msg.init("pininfo", len(self.get_pads()))
        for n, p in enumerate(self.get_pads()):
            k = p.pad_no
            t = cmp_msg.pininfo[n]

            t.identifier = k
            if k in self.name_mapping:
                t.name = self.name_mapping[k]

            t.net = self._project.scontext.sid_for(self.net_mapping[k])

    @staticmethod
    def deserializeTo(project: 'Project', msg: 'ser.Component.Reader', target: 'Component') -> None:

        if msg.side == "top":
            target.side = SIDE.Top
        elif msg.side == "bottom":
            target.side = SIDE.Bottom
        else:
            raise NotImplementedError()

        target.theta = msg.theta
        target.center = deserialize_point2(msg.center)
        target.refdes = msg.refdes
        target.partno = msg.partno

        project.scontext.set_sid(msg.sid, target)

        target.name_mapping = {}
        target.net_mapping = defaultdict(lambda: None)

        for i in msg.pininfo:
            ident = i.identifier
            target.name_mapping[ident] = i.name
            assert i.net is not None
            try:
                target.net_mapping[ident] = project.scontext.get(i.net)
            except KeyError:
                print("Warning: No net for SID %d during component load" % i.net)
                target.net_mapping[ident] = project.nets.new()

    def point_inside(self, pt: Vec2) -> int:
        return self.bbox.point_test(pt)

    @property
    def theta_bbox(self) -> 'Rect':
        raise NotImplementedError("theta bbox must be implemented by subclass")

    @property
    def bbox(self) -> 'Rect':
        r = self.theta_bbox.rotated_bbox(self.theta)
        r.translate(self.center)
        return r
