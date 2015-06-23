from pcbre.model.const import SIDE
import pcbre.model.imagelayer
import pcbre.model.serialization as ser

class Layer:

    def __init__(self, name, color):
        self.name = name
        self.color = color
        self.imagelayers = []

        self._project = None

    def __repr__(self):
        return "<Layer name:'%s' order:%s color:%s>" % (self.name,
                                                           self.order,
                                                           self.color)
    def serialize(self):
        m = ser.Layer.new_message()
        m.sid = self._project.scontext.sid_for(self)
        m.name = self.name
        m.color = ser.serialize_color3f(self.color)
        m.init("imagelayerSids", len(self.imagelayers))
        for n, i in enumerate(self.imagelayers):
            m.imagelayerSids[n] = self._project.scontext.sid_for(i)
        return m

    @staticmethod
    def deserialize(project, msg):
        obj = Layer(msg.name, ser.deserialize_color3f(msg.color))
        obj._project = project
        project.scontext.set_sid(msg.sid, obj)

        def finalize():
            for i in msg.imagelayerSids:
                obj.imagelayers.append(project.scontext.get(i))

        project.scontext.add_deser_fini(finalize)

        return obj


    @property
    def order(self):
        return self._project.stackup._order_for_layer(self)

    @property
    def side(self):
        return SIDE.Bottom if self.order > 0 else SIDE.Top





class ViaPair:
    def __init__(self, first_layer, second_layer):
        if first_layer == second_layer:
            raise ValueError("Can't have single layer layerpair")

        # Have to check equality first since Py3 says NoneType can't be compared with >
        self.__layers = set((first_layer, second_layer))
        self._project = None

    @property
    def layers(self):
        return tuple(sorted(self.__layers, key=lambda x: x.order))

    @layers.setter
    def layers(self, val):
        if len(val) != 2:
            raise ValueError
        self.__layers = set(val)

    @property
    def all_layers(self):
        out = []
        _first_layer, _second_layer = self.layers
        for layer in self._project.stackup.layers:
            if _first_layer.order <= layer.order <= _second_layer.order:
                out.append(layer)

        return sorted(out, key=lambda x: x.order)

    def __repr__(self):
        return "<ViaPair Top:%s Bot:%s>" % (self.layers)

    def serialize(self):
        _vp = ser.ViaPair.new_message()
        _vp.sid = self._project.scontext.sid_for(self)
        first, second = self.layers
        _vp.firstLayerSid = self._project.scontext.sid_for(first)
        _vp.secondLayerSid = self._project.scontext.sid_for(second)

        return _vp


    @staticmethod
    def deserialize(project, msg):
        l_first = project.scontext.get(msg.firstLayerSid)
        l_second = project.scontext.get(msg.secondLayerSid)

        vp = ViaPair(l_first, l_second)
        vp._project = project
        project.scontext.set_sid(msg.sid, vp)

        return vp

