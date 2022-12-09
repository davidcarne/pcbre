# DO NOT REMOVE FOLLOWING IMPORT
# side effect sets up capnp class loader
import capnp  # type: ignore

import pcbre.model.serialization_capnp.pcbre_capnp  # type: ignore

# the PCBRE CAPNP uses a dynamic loader, type analysis will fail on these
from .pcbre_capnp import Project, Stackup, ViaPair, Layer, Color3f, Artwork, Imagery, \
    Net, Nets, Image as ImageMsg, ImageTransform as ImageTransformMsg, Matrix3x3, Matrix4x4, Point2, Point2f, \
    Keypoint as KeypointMsg, ImageTransform, Component as ComponentMsg, Handle as HandleMsg

from typing import Tuple, Union, Dict, TYPE_CHECKING, Optional, BinaryIO

import pcbre.matrix
import numpy
import os

from pcbre.model.serialization import SERIALIZATION_VERSION

if TYPE_CHECKING:
    from pcbre.model.serialization import PersistentID
    import numpy.typing as npt
    import pcbre.model.project
    import pcbre.model.artwork
    import pcbre.model.stackup
    import pcbre.model.imagelayer
    import pcbre.model.dipcomponent
    import pcbre.model.smd4component
    import pcbre.model.passivecomponent
    import pcbre.model.component
    import pcbre.model.net


MAGIC = b"PCBRE\x00"
VERSION_MAGIC = SERIALIZATION_VERSION.to_bytes(2, 'little')

class CapnpIO:
    project: 'pcbre.model.project.Project'
    net_ref: 'Dict[PersistentID, pcbre.model.net.Net]'
    layer_ref: 'Dict[PersistentID, pcbre.model.stackup.Layer]'
    viapair_ref: 'Dict[PersistentID, pcbre.model.stackup.ViaPair]'
    component_ref: 'Dict[PersistentID, pcbre.model.component.Component]'
    keypoint_ref: 'Dict[PersistentID, pcbre.model.imagelayer.KeyPoint]'
    imagelayer_ref: 'Dict[PersistentID, pcbre.model.imagelayer.ImageLayer]'

    @staticmethod
    def serialize_color3f(color: Tuple[float, float, float]) -> Color3f:
        msg = Color3f.new_message()
        msg.r, msg.g, msg.b = map(float, color)
        return msg

    @staticmethod
    def float_lim(v: float) -> float:
        v = float(v)
        if v < 0:
            return 0
        if v > 1:
            return 1
        return v

    def deserialize_color3f(self, msg: Color3f) -> Tuple[float, float, float]:
        return self.float_lim(msg.r), self.float_lim(msg.g), self.float_lim(msg.b)

    @staticmethod
    def serialize_matrix(mat: 'npt.NDArray[numpy.float64]') -> Union[Matrix3x3.Builder, Matrix4x4.Builder]:
        if mat.shape == (3, 3):
            m = Matrix3x3.new_message()

        elif mat.shape == (4, 4):
            m = Matrix4x4.new_message()
        else:
            raise TypeError("Cannot serialize matrix of shape %s" % mat.shape)

        for n, i in enumerate(mat.flatten()):
            setattr(m, "t%d" % n, float(i))

        return m

    @staticmethod
    def deserialize_matrix(msg: Union[Matrix3x3.Reader, Matrix4x4.Reader]) -> 'npt.NDArray[numpy.float64]':
        if isinstance(msg, (Matrix3x3.Builder, Matrix3x3.Reader)):
            shape = (3, 3)

        elif isinstance(msg, (Matrix4x4.Builder, Matrix4x4.Reader)):
            shape = (4, 4)
        else:
            raise TypeError("Can't deserialize matrix type %s" % msg)

        ar = numpy.array([getattr(msg, "t%d" % i) for i in range(shape[0] * shape[1])], dtype=numpy.float64)
        return ar.reshape(shape[0], shape[1])

    @staticmethod
    def serialize_point2(pt2: pcbre.matrix.Vec2) -> Point2:
        msg = Point2.new_message()
        msg.x = int(round(pt2.x))
        msg.y = int(round(pt2.y))
        return msg

    @staticmethod
    def deserialize_point2(msg: Point2) -> pcbre.matrix.Vec2:
        return pcbre.matrix.Point2(msg.x, msg.y)

    @staticmethod
    def serialize_point2f(pt2: pcbre.matrix.Vec2) -> Point2f:
        msg = Point2f.new_message()
        msg.x = float(pt2.x)
        msg.y = float(pt2.y)
        return msg

    @staticmethod
    def deserialize_point2f(msg: Point2f) -> pcbre.matrix.Point2:
        return pcbre.matrix.Point2(msg.x, msg.y)

    def serialize_layer(self, layer: 'pcbre.model.stackup.Layer') -> Layer:
        m = Layer.new_message()
        m.sid = layer.unique_id.as_uint32
        m.name = layer.name
        m.color = self.serialize_color3f(layer.color)
        m.init("imagelayerSids", len(layer.imagelayers))
        for n, i in enumerate(layer.imagelayers):
            m.imagelayerSids[n] = i.unique_id.as_uint32
        return m

    def deserialize_layer(self, msg: Layer) -> 'pcbre.model.stackup.Layer':
        import pcbre.model.stackup

        unique_id = self.project.unique_id_registry.decode_add_from_uint32(msg.sid)
        obj = pcbre.model.stackup.Layer(self.project, unique_id, msg.name, self.deserialize_color3f(msg.color))
        self.layer_ref[unique_id] = obj

        for i in msg.imagelayerSids:
            imlay_oid = self.project.unique_id_registry.decode_check_from_uint32(i)
            obj.imagelayers.append(self.imagelayer_ref[imlay_oid])

        return obj

    @staticmethod
    def serialize_viapair(viapair: 'pcbre.model.stackup.ViaPair') -> ViaPair:
        _vp = ViaPair.new_message()
        _vp.sid = viapair.unique_id.as_uint32
        first, second = viapair.layers
        _vp.firstLayerSid = first.unique_id.as_uint32
        _vp.secondLayerSid = second.unique_id.as_uint32
        return _vp

    def deserialize_viapair(self, msg: ViaPair) -> 'pcbre.model.stackup.ViaPair':
        import pcbre.model.stackup
        oid_first = self.project.unique_id_registry.decode_check_from_uint32(msg.firstLayerSid)
        oid_second = self.project.unique_id_registry.decode_check_from_uint32(msg.secondLayerSid)

        l_first = self.layer_ref[oid_first]
        l_second = self.layer_ref[oid_second]

        oid = self.project.unique_id_registry.decode_add_from_uint32(msg.sid)
        vp = pcbre.model.stackup.ViaPair(self.project, oid, l_first, l_second)
        self.viapair_ref[oid] = vp

        return vp

    def serialize_stackup(self) -> Stackup:
        stackup_msg = Stackup.new_message()
        stackup_msg.init("layers", len(self.project.stackup._layers))

        for n, i_l in enumerate(self.project.stackup._layers):
            stackup_msg.layers[n] = self.serialize_layer(i_l)

        stackup_msg.init("viapairs", len(self.project.stackup._via_pairs))
        for n, i_vp in enumerate(self.project.stackup._via_pairs):
            stackup_msg.viapairs[n] = self.serialize_viapair(i_vp)

        return stackup_msg

    def deserialize_stackup(self, msg: Stackup) -> None:
        to = self.project.stackup
        to._layers.clear()
        for i in msg.layers:
            to._layers.append(self.deserialize_layer(i))

        to._via_pairs.clear()
        for i in msg.viapairs:
            to._via_pairs.append(self.deserialize_viapair(i))

        to._renumber_layers()

    def serialize_keypoint(self, kp: 'pcbre.model.imagelayer.KeyPoint') -> KeypointMsg:
        msg = KeypointMsg.new_message()
        msg.sid = kp.unique_id.as_uint32
        msg.worldPosition = self.serialize_point2(kp.world_position)
        return msg

    def deserialize_keypoint(self, msg: KeypointMsg) -> 'pcbre.model.imagelayer.KeyPoint':
        import pcbre.model.imagelayer
        world_position = self.deserialize_point2(msg.worldPosition)

        unique_id = self.project.unique_id_registry.decode_add_from_uint32(msg.sid)
        obj = pcbre.model.imagelayer.KeyPoint(self.project, world_position, unique_id)
        self.keypoint_ref[unique_id] = obj

        obj._project = self.project
        return obj

    def serialize_keypoint_alignment(self,
                                     keypoint_alignment: 'pcbre.model.imagelayer.KeyPointAlignment') ->\
            ImageTransformMsg.KeypointTransformMeta:

        msg = ImageTransformMsg.KeypointTransformMeta.new_message()
        msg.init("keypoints", len(keypoint_alignment._keypoint_positions))
        for n, i in enumerate(keypoint_alignment._keypoint_positions):
            msg.keypoints[n].kpSid = i.key_point.unique_id.as_uint32
            msg.keypoints[n].position = self.serialize_point2f(i.image_pos)

        return msg

    def deserialize_keypoint_alignment(self,
                                       msg: ImageTransform.KeypointTransformMeta) -> \
            'pcbre.model.imagelayer.KeyPointAlignment':
        import pcbre.model.imagelayer
        obj = pcbre.model.imagelayer.KeyPointAlignment()
        for i in msg.keypoints:
            kp_oid = self.project.unique_id_registry.decode_check_from_uint32(i.kpSid)
            obj.set_keypoint_position(self.keypoint_ref[kp_oid], self.deserialize_point2f(i.position))
        return obj

    def serialize_rect_alignment(self, rect_alignment: 'pcbre.model.imagelayer.RectAlignment') \
            -> ImageTransformMsg.RectTransformMeta.Builder:
        msg = ImageTransformMsg.RectTransformMeta.new_message()
        msg.init("handles", 12)
        msg.init("dimHandles", 4)
        msg.init("dims", 2)

        for n, i in enumerate(rect_alignment.dims):
            msg.dims[n] = i

        msg.lockedToDim = rect_alignment.dims_locked
        msg.originCorner = {
            0: "lowerLeft",
            1: "lowerRight",
            2: "upperLeft",
            3: "upperRight"}[rect_alignment.origin_corner]

        msg.originCenter = self.serialize_point2f(rect_alignment.origin_center)

        for n, i_a in enumerate(rect_alignment.handles):
            self.__serialize_handle_capnp(i_a, msg.handles[n])

        for n, i_b in enumerate(rect_alignment.dim_handles):
            self.__serialize_handle_capnp(i_b, msg.dimHandles[n])

        msg.flipX = rect_alignment.flip_x
        msg.flipY = rect_alignment.flip_y

        return msg

    def __serialize_handle_capnp(self, m: Optional[pcbre.matrix.Vec2], to: HandleMsg.Builder) -> None:
        if m is None:
            to.none = None
        else:
            to.point = self.serialize_point2f(m)

    def __deserialize_handle_capnp(self, msg: HandleMsg.Reader) -> Optional[pcbre.matrix.Vec2]:
        if msg.which() == "none":
            return None
        else:
            return self.deserialize_point2f(msg.point)

    def deserialize_rect_alignment(self, msg: ImageTransformMsg.RectTransformMeta.Reader) -> \
            'pcbre.model.imagelayer.RectAlignment':
        import pcbre.model.imagelayer
        handles = [self.__deserialize_handle_capnp(i) for i in msg.handles]
        dim_handles = [self.__deserialize_handle_capnp(i) for i in msg.dimHandles]
        dims = [i for i in msg.dims]

        assert len(handles) == 12
        assert len(dim_handles) == 4
        assert len(dims) == 2
        origin_corner = {
            "lowerLeft": 0,
            "lowerRight": 1,
            "upperLeft": 2,
            "upperRight": 3}[str(msg.originCorner)]

        origin_center = self.deserialize_point2f(msg.originCenter)

        return pcbre.model.imagelayer.RectAlignment(handles, dim_handles, dims, msg.lockedToDim,
                                                    origin_center, origin_corner, msg.flipX, msg.flipY)

    def serialize_imagelayer(self, imagelayer: 'pcbre.model.imagelayer.ImageLayer') -> 'ImageMsg.Builder':
        import pcbre.model.imagelayer
        msg = ImageMsg.new_message()
        msg.sid = imagelayer.unique_id.as_uint32
        msg.data = imagelayer.data
        msg.name = imagelayer.name
        m = self.serialize_matrix(imagelayer.transform_matrix)
        msg.transform.matrix = m

        if imagelayer.alignment is None:
            # Assign "no-metadata-for-transform"
            msg.transform.meta.noMeta = None
        elif isinstance(imagelayer.alignment, pcbre.model.imagelayer.KeyPointAlignment):
            msg.transform.meta.init("keypointTransformMeta")
            msg.transform.meta.keypointTransformMeta = \
                self.serialize_keypoint_alignment(imagelayer.alignment)
        elif isinstance(imagelayer.alignment, pcbre.model.imagelayer.RectAlignment):
            msg.transform.meta.init("rectTransformMeta")
            msg.transform.meta.rectTransformMeta = self.serialize_rect_alignment(imagelayer.alignment)
        else:
            raise NotImplementedError("Don't know how to serialize %s" % imagelayer.alignment)

        return msg

    def deserialize_imagelayer(self, msg: 'ImageMsg.Reader') -> \
            'pcbre.model.imagelayer.ImageLayer':
        import pcbre.model.imagelayer
        transform = self.deserialize_matrix(msg.transform.matrix)

        unique_id = self.project.unique_id_registry.decode_add_from_uint32(msg.sid)
        obj = pcbre.model.imagelayer.ImageLayer(self.project, unique_id, msg.name, msg.data, transform)
        self.imagelayer_ref[unique_id] = obj

        obj._project = self.project

        meta_which = msg.transform.meta.which()
        if meta_which == "noMeta":
            obj.set_alignment(None)
        elif meta_which == "keypointTransformMeta":
            obj.set_alignment(self.deserialize_keypoint_alignment(msg.transform.meta.keypointTransformMeta))
        elif meta_which == "rectTransformMeta":
            obj.set_alignment(self.deserialize_rect_alignment(msg.transform.meta.rectTransformMeta))
        else:
            raise NotImplementedError()

        return obj

    def serialize_imagery(self) -> Imagery:
        imagery_msg = Imagery.new_message()

        imagery_msg.init("imagelayers", len(self.project.imagery.imagelayers))
        for n, i in enumerate(self.project.imagery.imagelayers):
            imagery_msg.imagelayers[n] = self.serialize_imagelayer(i)

        imagery_msg.init("keypoints", len(self.project.imagery.keypoints))

        for n, i_ in enumerate(self.project.imagery.keypoints):
            imagery_msg.keypoints[n] = self.serialize_keypoint(i_)

        return imagery_msg

    def deserialize_imagery(self, msg: Imagery) -> None:
        # Keypoints may be used by the imagelayers during deserialize

        # Deserialize first to avoid a finalizer
        to = self.project.imagery
        for i in msg.keypoints:
            to._keypoints.append(self.deserialize_keypoint(i))

        for i in msg.imagelayers:
            to._imagelayers.append(self.deserialize_imagelayer(i))

    def serialize_nets(self) -> Nets:
        _nets = Nets.new_message()
        _nets.init("netList", len(self.project.nets.nets))
        for n, i in enumerate(self.project.nets.nets):
            _nets.netList[n].sid = i.unique_id.as_uint32
            _nets.netList[n].name = i.name
            _nets.netList[n].nclass = i.net_class

        return _nets

    def deserialize_nets(self, msg: Nets) -> None:
        import pcbre.model.project
        to = self.project.nets

        for i in msg.netList:
            unique_id = self.project.unique_id_registry.decode_add_from_uint32(i.sid)
            n = pcbre.model.project.Net(
                unique_id=unique_id,
                name=i.name, net_class=i.nclass)
            to._add_net(n)
            self.net_ref[unique_id] = n

    @staticmethod
    def serialize_project(project: 'pcbre.model.project.Project') -> Project:
        self = CapnpIO()
        self.project = project

        project_msg = Project.new_message()
        project_msg.stackup = self.serialize_stackup()
        project_msg.imagery = self.serialize_imagery()
        project_msg.nets = self.serialize_nets()
        project_msg.artwork = self.serialize_artwork()

        return project_msg

    @staticmethod
    def deserialize_project(msg: Project) -> 'pcbre.model.project.Project':
        self = CapnpIO()
        self.net_ref = dict()
        self.layer_ref = dict()
        self.viapair_ref = dict()
        self.component_ref = dict()
        self.keypoint_ref = dict()
        self.imagelayer_ref = dict()

        self.project = pcbre.model.project.Project()
        self.deserialize_imagery(msg.imagery)
        self.deserialize_stackup(msg.stackup)
        self.deserialize_nets(msg.nets)
        self.deserialize_artwork(msg.artwork)
        return self.project

    def serialize_component_common(self, component: 'pcbre.model.component.Component',
                                   cmp_msg: 'ComponentMsg.Builder') -> None:
        import pcbre.model.component
        if component.side == pcbre.model.component.SIDE.Top:
            cmp_msg.side = "top"
        elif component.side == pcbre.model.component.SIDE.Bottom:
            cmp_msg.side = "bottom"
        else:
            raise NotImplementedError()

        cmp_msg.refdes = component.refdes
        cmp_msg.partno = component.partno

        cmp_msg.center = self.serialize_point2(component.center)
        cmp_msg.theta = float(component.theta)
        cmp_msg.sidUNUSED = 0

        cmp_msg.init("pininfo", len(component.get_pads()))
        for n, p in enumerate(component.get_pads()):
            k = p.pad_no
            t = cmp_msg.pininfo[n]

            t.identifier = k
            if k in component.name_mapping:
                t.name = component.name_mapping[k]

            t.net = component.net_mapping[k].unique_id.as_uint32

    def deserialize_component_common(self, msg: 'ComponentMsg.Reader',
                                     target: 'pcbre.model.component.Component') -> None:
        from collections import defaultdict
        import pcbre.model.component
        if msg.side == "top":
            target.side = pcbre.model.component.SIDE.Top
        elif msg.side == "bottom":
            target.side = pcbre.model.component.SIDE.Bottom
        else:
            raise NotImplementedError()

        target.theta = msg.theta
        target.center = self.deserialize_point2(msg.center)
        target.refdes = msg.refdes
        target.partno = msg.partno

        target.name_mapping = {}
        target.net_mapping = defaultdict(lambda: None)

        for i in msg.pininfo:
            ident = i.identifier
            target.name_mapping[ident] = i.name
            assert i.net is not None
            net_oid = self.project.unique_id_registry.decode_check_from_uint32(i.net)
            try:
                target.net_mapping[ident] = self.net_ref[net_oid]
            except KeyError:
                print("Warning: No net for SID %d during component load" % i.net)
                target.net_mapping[ident] = project.nets.new()

    def serialize_sip_component(self, sip_component: 'pcbre.model.dipcomponent.SIPComponent',
                                sip_msg: 'ComponentMsg.Builder') -> None:
        self.serialize_component_common(sip_component, sip_msg.common)
        sip_msg.init("sip")

        m = sip_msg.sip

        m.pinCount = sip_component.pin_count
        m.pinSpace = int(sip_component.pin_space)
        m.padSize = int(sip_component.pad_size)

    def deserialize_sip_component(self, sip_msg: 'ComponentMsg.Reader') -> \
            'pcbre.model.dipcomponent.SIPComponent':

        import pcbre.model.dipcomponent
        m = sip_msg.sip
        cmp: pcbre.model.dipcomponent.SIPComponent = pcbre.model.dipcomponent.SIPComponent.__new__(
            pcbre.model.dipcomponent.SIPComponent)

        self.deserialize_component_common(sip_msg.common, cmp)
        cmp._my_init(m.pinCount, m.pinSpace, m.padSize)
        return cmp

    def serialize_dip_component(self, dip_component: 'pcbre.model.dipcomponent.DIPComponent',
                                dip_msg: 'ComponentMsg.Builder') -> None:

        self.serialize_component_common(dip_component, dip_msg.common)
        dip_msg.init("dip")

        m = dip_msg.dip

        m.pinCount = dip_component.pin_count
        m.pinSpace = dip_component.pin_space
        m.pinWidth = dip_component.pin_width
        m.padSize = dip_component.pad_size

    def deserialize_dip_component(self, dip_msg: 'ComponentMsg.Reader') -> \
            'pcbre.model.component.Component':
        from pcbre.model.dipcomponent import DIPComponent
        m = dip_msg.dip
        cmp: DIPComponent = DIPComponent.__new__(DIPComponent)
        self.deserialize_component_common(dip_msg.common, cmp)
        cmp._my_init(m.pinCount, m.pinSpace, m.pinWidth, m.padSize, self.project)
        return cmp

    def serialize_smd4_component(self, smd4component: 'pcbre.model.smd4component.SMD4Component',
                                 cmp_msg: ComponentMsg.Builder) -> None:
        self.serialize_component_common(smd4component, cmp_msg.common)
        cmp_msg.init("smd4")
        t = cmp_msg.smd4
        t.dim1Body = int(smd4component.dim_1_body)
        t.dim1PinEdge = int(smd4component.dim_1_pincenter)

        t.dim2Body = int(smd4component.dim_2_body)
        t.dim2PinEdge = int(smd4component.dim_2_pincenter)

        t.pinContactLength = int(smd4component.pin_contact_length)
        t.pinContactWidth = int(smd4component.pin_contact_width)
        t.pinSpacing = int(smd4component.pin_spacing)

        t.side1Pins = smd4component.side_pins[0]
        t.side2Pins = smd4component.side_pins[1]
        t.side3Pins = smd4component.side_pins[2]
        t.side4Pins = smd4component.side_pins[3]

    def deserialize_smd4_component(self, msg: ComponentMsg.Reader) -> \
            'pcbre.model.smd4component.SMD4Component':
        import pcbre.model.smd4component
        t = msg.smd4
        cmp = pcbre.model.smd4component.SMD4Component(
            self.project,
            pcbre.matrix.Vec2(0, 0), 0,  pcbre.model.component.SIDE.Top,   # Placeholder values
            self.project,
            t.side1Pins, t.side2Pins, t.side3Pins, t.side4Pins,
            t.dim1Body, t.dim1PinEdge, t.dim2Body, t.dim2PinEdge,
            t.pinContactLength, t.pinContactWidth, t.pinSpacing)

        self.deserialize_component_common(msg.common, cmp)
        return cmp

    def serialize_passive_component(self, passive_component: 'pcbre.model.passivecomponent.Passive2Component',
                                    pasv_msg: 'ComponentMsg.Builder') -> None:
        self.serialize_component_common(passive_component, pasv_msg.common)
        pasv_msg.init("passive2")

        m = pasv_msg.passive2

        m.symType = passive_component.sym_type.value
        m.bodyType = passive_component.body_type.value
        m.pinD = int(passive_component.pin_d)
        m.bodyCornerVec = self.serialize_point2(passive_component.body_corner_vec)
        m.pinCornerVec = self.serialize_point2(passive_component.pin_corner_vec)

    def deserialize_passive_component(self, pasv_msg: 'ComponentMsg.Reader') -> \
            'pcbre.model.passivecomponent.Passive2Component':
        import pcbre.model.passivecomponent as pma
        m = pasv_msg.passive2
        cmp: pma.Passive2Component = pma.Passive2Component.__new__(pma.Passive2Component)
        self.deserialize_component_common(pasv_msg.common, cmp)

        cmp.sym_type = pma.PassiveSymType(m.symType.raw)
        cmp.body_type = pma.Passive2BodyType(m.bodyType.raw)

        # Distance from center to pin
        cmp.pin_d = m.pinD

        cmp.body_corner_vec = self.deserialize_point2(m.bodyCornerVec)
        cmp.pin_corner_vec = self.deserialize_point2(m.pinCornerVec)
        cmp._pads = []

        return cmp

    def serialize_artwork(self) -> Artwork.Builder:
        import pcbre.model.passivecomponent
        import pcbre.model.smd4component
        import pcbre.model.dipcomponent

        artwork = self.project.artwork
        _aw = Artwork.new_message()
        _aw.init("vias", len(artwork.vias))
        _aw.init("traces", len(artwork.traces))
        _aw.init("polygons", len(artwork.polygons))
        _aw.init("components", len(artwork.components))
        _aw.init("airwires", len(artwork.airwires))

        # Serialization done here to reduce instance size
        for n, i_via in enumerate(artwork.vias):
            v = _aw.vias[n]
            v.point = self.serialize_point2(i_via.pt)
            v.r = i_via.r
            v.viapairSid = i_via.viapair.unique_id.as_uint32
            v.netSid = i_via.net.unique_id.as_uint32

        #
        for n, i_trace in enumerate(artwork.traces):
            t = _aw.traces[n]
            t.p0 = self.serialize_point2(i_trace.p0)
            t.p1 = self.serialize_point2(i_trace.p1)
            t.thickness = int(i_trace.thickness)
            t.netSid = i_trace.net.unique_id.as_uint32
            t.layerSid = i_trace.layer.unique_id.as_uint32

        for n, i_comp in enumerate(artwork.components):
            t = _aw.components[n]
            if isinstance(i_comp, pcbre.model.passivecomponent.Passive2Component):
                self.serialize_passive_component(i_comp, t)
            elif isinstance(i_comp, pcbre.model.dipcomponent.SIPComponent):
                self.serialize_sip_component(i_comp, t)
            elif isinstance(i_comp, pcbre.model.dipcomponent.DIPComponent):
                self.serialize_dip_component(i_comp, t)
            elif isinstance(i_comp, pcbre.model.smd4component.SMD4Component):
                self.serialize_smd4_component(i_comp, t)
            else:
                raise NotImplementedError("CAPNP serialization of %s is not supported" % repr(i_comp))

        for n, i_poly in enumerate(artwork.polygons):
            p = _aw.polygons[n]

            p_repr = i_poly.get_poly_repr()
            p.init("exterior", len(p_repr.exterior.coords))
            for nn, ii in enumerate(p_repr.exterior.coords):
                p.exterior[nn] = self.serialize_point2(pcbre.matrix.Point2(ii[0], ii[1]))

            p.init("interiors", len(p_repr.interiors))
            for n_interior, interior in enumerate(p_repr.interiors):
                p.interiors.init(n_interior, len(interior.coords))
                for nn, ii in enumerate(interior.coords):
                    p.interiors[n_interior][nn] = self.serialize_point2(pcbre.matrix.Point2(ii[0], ii[1]))

            p.layerSid = i_poly.layer.unique_id.as_uint32
            p.netSid = i_poly.net.unique_id.as_uint32

        for n, i_ in enumerate(artwork.airwires):
            t = _aw.airwires[n]
            t.p0 = self.serialize_point2(i_.p0)
            t.p1 = self.serialize_point2(i_.p1)
            t.netSid = i_.net.unique_id.as_uint32
            t.p0LayerSid = i_.p0_layer.unique_id.as_uint32
            t.p1LayerSid = i_.p1_layer.unique_id.as_uint32

        return _aw

    def __lookup_net_helper(self, sid: 'PersistentID') -> Net:
        try:
            return self.net_ref.get(sid)
        except KeyError:
            print("WARNING: invalid SID %d for net lookup, replacing with empty net", sid)
            return artwork._project.nets.new()

    def deserialize_artwork(self, msg: Artwork) -> None:
        import pcbre.model.artwork
        for i_via in msg.vias:
            viapair_oid = self.project.unique_id_registry.decode_check_from_uint32(i_via.viapairSid)
            net_oid = self.project.unique_id_registry.decode_check_from_uint32(i_via.netSid)
            v = pcbre.model.artwork.Via(self.deserialize_point2(i_via.point),
                                        self.viapair_ref.get(viapair_oid),
                                        i_via.r,
                                        self.__lookup_net_helper(net_oid)
                                        )

            self.project.artwork.add_artwork(v)

        for i_trace in msg.traces:
            layer_oid = self.project.unique_id_registry.decode_check_from_uint32(i_trace.layerSid)
            net_oid = self.project.unique_id_registry.decode_check_from_uint32(i_trace.netSid)
            t = pcbre.model.artwork.Trace(
                self.deserialize_point2(i_trace.p0),
                self.deserialize_point2(i_trace.p1),
                i_trace.thickness,
                self.layer_ref.get(layer_oid),
                self.__lookup_net_helper(net_oid)
            )
            self.project.artwork.add_artwork(t)

        for i_poly in msg.polygons:
            exterior = [self.deserialize_point2(j) for j in i_poly.exterior]
            interiors = [[self.deserialize_point2(k) for k in j] for j in i_poly.interiors]

            layer_oid = self.project.unique_id_registry.decode_check_from_uint32(i_poly.layerSid)
            net_oid = self.project.unique_id_registry.decode_check_from_uint32(i_poly.netSid)

            p = pcbre.model.artwork.Polygon(
                self.layer_ref.get(layer_oid),
                exterior,
                interiors,
                self.__lookup_net_helper(net_oid),
            )

            self.project.artwork.add_artwork(p)

        for i_airwire in msg.airwires:
            p0_oid = self.project.unique_id_registry.decode_check_from_uint32(i_airwire.p0LayerSid)
            p1_oid = self.project.unique_id_registry.decode_check_from_uint32(i_airwire.p1LayerSid)
            net_oid = self.project.unique_id_registry.decode_check_from_uint32(i_airwire.netSid)
            aw = pcbre.model.artwork.Airwire(
                self.deserialize_point2(i_airwire.p0),
                self.deserialize_point2(i_airwire.p1),
                self.layer_ref.get(p0_oid),
                self.layer_ref.get(p1_oid),
                self.net_ref.get(net_oid)
            )
            self.project.artwork.add_artwork(aw)

        for i_cmp in msg.components:
            if i_cmp.which() == "dip":
                cmp = self.deserialize_dip_component(i_cmp)
            elif i_cmp.which() == "sip":
                cmp = self.deserialize_sip_component(i_cmp)
            elif i_cmp.which() == "smd4":
                cmp = self.deserialize_smd4_component(i_cmp)
            elif i_cmp.which() == "passive2":
                cmp = self.deserialize_passive_component(i_cmp)
            else:
                raise NotImplementedError()

            self.project.artwork.add_component(cmp)


    @staticmethod
    def open_path(path: os.PathLike) -> 'pcbre.model.project.Project':
        with open(path, "rb", buffering=0) as f:
            return CapnpIO.open_fd(f)

    @staticmethod
    def open_fd(fd: BinaryIO) -> 'pcbre.model.project.Project':
        magic = fd.read(8)
        if magic[:6] != MAGIC:
            raise ValueError("Unknown File Type")

        vers = magic[6:8]
        if vers != VERSION_MAGIC:
            raise ValueError("Unknown File Version")

        _project = Project.read(fd)
        self = CapnpIO.deserialize_project(_project)
        return self

    @staticmethod
    def save_path(project, path) -> None:
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
            CapnpIO.save_fd(project, f)
        except Exception as e:
            os.unlink(path)
            os.rename(bakname, path)
            raise e

        f.close()

    @staticmethod
    def save_fd(project, fd: BinaryIO) -> None:
        fd.write(MAGIC + VERSION_MAGIC)
        # This appears to be necessary for some IO types
        # CAPNP may not reflect already buffer contents
        # (see when writing to a named temp file)
        fd.flush()

        message = CapnpIO.serialize_project(project)
        message.write(fd)

        fd.flush()
