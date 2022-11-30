from collections import defaultdict
from pcbre.matrix import translate, rotate, cflip, Vec2
from pcbre.model.const import SIDE, TFF

from typing import Dict, Optional, Sequence, TYPE_CHECKING
if TYPE_CHECKING:
    from pcbre.model.net import Net
    from pcbre.model.pad import Pad
    from pcbre.model.project import Project
    import numpy
    from pcbre.matrix import Rect
    import numpy.typing as npt


class Component:
    TYPE_FLAGS = TFF.HAS_INST_INFO

    def __init__(self, 
                 project: 'Project',
                 center: Vec2, 
                 theta: float, side: SIDE, 
                 name_mapping: Optional[Dict[str, str]] = None,
                 refdes: str = "",
                 partno: str = "",
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
