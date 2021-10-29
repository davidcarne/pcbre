from pcbre.model.const import SIDE
import pcbre.model.serialization as ser
import pcbre.model.imagelayer
import pcbre.model.project

from typing import Tuple, List, Sequence


class Layer:

    def __init__(self, project : 'pcbre.model.project.Project',
            name: str, color: Tuple[float,float,float]):
        self.project = project
        self.name = name
        self.color = color
        self.imagelayers : List[pcbre.model.imagelayer.ImageLayer] = []

        # Nonpersistent layer number. All layers are renumbered by project
        # Varies upredictably with database mutations
        self.number = 0

    def __repr__(self) -> str:
        return "<Layer name:'%s' order:%s color:%s>" % (self.name,
                                                        self.order,
                                                        self.color)

    def serialize(self) -> ser.Layer:
        m = ser.Layer.new_message()
        m.sid = self.project.scontext.sid_for(self)
        m.name = self.name
        m.color = ser.serialize_color3f(self.color)
        m.init("imagelayerSids", len(self.imagelayers))
        for n, i in enumerate(self.imagelayers):
            m.imagelayerSids[n] = self.project.scontext.sid_for(i)
        return m

    @staticmethod
    def deserialize(project: 'pcbre.model.project.Project', msg: ser.Layer) -> 'Layer':
        obj = Layer(project, msg.name, ser.deserialize_color3f(msg.color))
        project.scontext.set_sid(msg.sid, obj)

        def finalize() -> None:
            for i in msg.imagelayerSids:
                obj.imagelayers.append(project.scontext.get(i))

        project.scontext.add_deser_fini(finalize)

        return obj

    @property
    def order(self) -> int:
        return self.project.stackup._order_for_layer(self)

    @property
    def side(self) ->  SIDE:
        return SIDE.Bottom if self.order > 0 else SIDE.Top


class ViaPair:
    def __init__(self, project: 'pcbre.model.project.Project', first_layer: Layer, second_layer: Layer) -> None:
        if first_layer == second_layer:
            raise ValueError("Can't have single layer layerpair")

        self.__layers : Tuple[Layer, Layer] = (first_layer, second_layer)
        self.project = project

    @property
    def layers(self) -> Sequence[Layer]:
        return tuple(sorted(self.__layers, key=lambda x: x.order))

    @layers.setter
    def layers(self, val: Sequence[Layer]) -> None:
        if len(val) != 2:
            raise ValueError
        self.__layers = (val[0], val[1])

    @property
    def all_layers(self) -> Sequence[Layer]:
        out = []
        _first_layer, _second_layer = self.layers
        for layer in self.project.stackup.layers:
            if _first_layer.order <= layer.order <= _second_layer.order:
                out.append(layer)

        return sorted(out, key=lambda x: x.order)

    def __repr__(self) -> str:
        return "<ViaPair Top:%s Bot:%s>" % (self.layers[0], self.layers[1])

    def serialize(self) -> ser.ViaPair:
        _vp = ser.ViaPair.new_message()
        _vp.sid = self.project.scontext.sid_for(self)
        first, second = self.layers
        _vp.firstLayerSid = self.project.scontext.sid_for(first)
        _vp.secondLayerSid = self.project.scontext.sid_for(second)

        return _vp

    @staticmethod
    def deserialize(project: 'pcbre.model.project.Project', msg: ser.ViaPair) -> 'ViaPair':
        l_first = project.scontext.get(msg.firstLayerSid)
        l_second = project.scontext.get(msg.secondLayerSid)

        vp = ViaPair(project, l_first, l_second)
        project.scontext.set_sid(msg.sid, vp)

        return vp
