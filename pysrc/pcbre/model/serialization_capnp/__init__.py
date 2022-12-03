# DO NOT REMOVE FOLLOWING IMPORT
# side effect sets up capnp class loader
import capnp  # type: ignore

import pcbre.model.serialization_capnp.pcbre_capnp  # type: ignore

# the PCBRE CAPNP uses a dynamic loader, type analysis will fail on these
from .pcbre_capnp import Project, Stackup, ViaPair, Layer, Color3f, Artwork, Imagery, \
    Net, Nets, Image as ImageMsg, ImageTransform as ImageTransformMsg, Matrix3x3, Matrix4x4, Point2, Point2f, \
    Keypoint as KeypointMsg, ImageTransform, Component as ComponentMsg, Handle as HandleMsg

from typing import Tuple, Any, Union, Callable, Dict, List, Generator, TYPE_CHECKING, Optional

import pcbre.matrix
import contextlib
import numpy
from collections import defaultdict

if TYPE_CHECKING:
    import numpy.typing as npt
    import pcbre.model.project
    import pcbre.model.artwork
    import pcbre.model.stackup
    import pcbre.model.imagelayer
    import pcbre.model.dipcomponent
    import pcbre.model.smd4component
    import pcbre.model.passivecomponent
    import pcbre.model.component


def serialize_color3f(color: Tuple[float, float, float]) -> Color3f:
    msg = Color3f.new_message()
    msg.r, msg.g, msg.b = map(float, color)
    return msg


def float_lim(v: float) -> float:
    v = float(v)
    if v < 0:
        return 0
    if v > 1:
        return 1
    return v


def deserialize_color3f(msg: Color3f) -> Tuple[float, float, float]:
    return float_lim(msg.r), float_lim(msg.g), float_lim(msg.b)


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


def __deserialize_matrix_n(msg: Union[Matrix3x3.Reader, Matrix4x4.Reader], nterms: int) -> 'npt.NDArray[numpy.float64]':
    return ar


def deserialize_matrix(msg: Union[Matrix3x3.Reader, Matrix4x4.Reader]) -> 'npt.NDArray[numpy.float64]':
    if isinstance(msg, (Matrix3x3.Builder, Matrix3x3.Reader)):
        shape = (3, 3)

    elif isinstance(msg, (Matrix4x4.Builder, Matrix4x4.Reader)):
        shape = (4, 4)
    else:
        raise TypeError("Can't deserialize matrix type %s" % msg)

    ar = numpy.array([getattr(msg, "t%d" % i) for i in range(shape[0] * shape[1])], dtype=numpy.float64)
    return ar.reshape(shape[0], shape[1])


def serialize_point2(pt2: pcbre.matrix.Vec2) -> Point2:
    msg = Point2.new_message()
    msg.x = int(round(pt2.x))
    msg.y = int(round(pt2.y))
    return msg


def deserialize_point2(msg: Point2) -> pcbre.matrix.Vec2:
    return pcbre.matrix.Point2(msg.x, msg.y)


def serialize_point2f(pt2: pcbre.matrix.Vec2) -> Point2f:
    msg = Point2f.new_message()
    msg.x = float(pt2.x)
    msg.y = float(pt2.y)
    return msg


def deserialize_point2f(msg: Point2f) -> pcbre.matrix.Point2:
    return pcbre.matrix.Point2(msg.x, msg.y)


class StateError(Exception):
    pass


class SContext:
    def __init__(self) -> None:
        self.obj_to_sid: Dict[Any, int] = {}
        self.sid_to_obj: Dict[int, Any] = {}
        self._id_n = 0

        self.__restoring = False

    def new_sid(self) -> int:
        if self.__restoring:
            raise StateError("Can't create SID while restoring")

        self._id_n += 1
        return self._id_n

    def add_deser_fini(self, m: Callable[[], None]) -> None:
        assert self.__restoring
        self.__deser_fini.append(m)

    def start_restore(self) -> None:
        self.__restoring = True
        self.__deser_fini: List[Callable[[], None]] = []

    def end_restoring(self) -> None:
        # Call all finalizers
        for __finalizer in self.__deser_fini:
            __finalizer()

        del self.__deser_fini
        self.__restoring = False
        self._id_n = max([self._id_n] + list(self.sid_to_obj.keys()))

    @contextlib.contextmanager
    def restoring(self) -> Generator[None, None, None]:
        self.start_restore()
        yield
        self.end_restoring()

    @staticmethod
    def key(m: Any) -> int:
        return id(m)

    def set_sid(self, sid: int, m: Any) -> None:
        if not self.__restoring:
            raise StateError("Must be in restore mode to create objects with SID")
        assert sid not in self.sid_to_obj
        self.sid_to_obj[sid] = m

        self.obj_to_sid[self.key(m)] = sid

    def sid_for(self, m: Any) -> int:
        k = self.key(m)
        try:
            return self.obj_to_sid[k]
        except KeyError:
            sid = self.obj_to_sid[k] = self.new_sid()
            self.sid_to_obj[sid] = m
            return sid

    def get(self, sid: int) -> Any:
        return self.sid_to_obj[sid]


def serialize_layer(layer: 'pcbre.model.stackup.Layer') -> Layer:
    m = Layer.new_message()
    m.sid = layer.project.scontext.sid_for(layer)
    m.name = layer.name
    m.color = serialize_color3f(layer.color)
    m.init("imagelayerSids", len(layer.imagelayers))
    for n, i in enumerate(layer.imagelayers):
        m.imagelayerSids[n] = layer.project.scontext.sid_for(i)
    return m


def deserialize_layer(project: 'pcbre.model.project.Project', msg: Layer) -> 'pcbre.model.stackup.Layer':
    import pcbre.model.stackup
    obj = pcbre.model.stackup.Layer(project, msg.name, deserialize_color3f(msg.color))
    project.scontext.set_sid(msg.sid, obj)

    def finalize() -> None:
        for i in msg.imagelayerSids:
            obj.imagelayers.append(project.scontext.get(i))

    project.scontext.add_deser_fini(finalize)

    return obj


def serialize_viapair(viapair: 'pcbre.model.stackup.ViaPair') -> ViaPair:
    _vp = ViaPair.new_message()
    _vp.sid = viapair.project.scontext.sid_for(viapair)
    first, second = viapair.layers
    _vp.firstLayerSid = viapair.project.scontext.sid_for(first)
    _vp.secondLayerSid = viapair.project.scontext.sid_for(second)
    return _vp


def deserialize_viapair(project: 'pcbre.model.project.Project', msg: ViaPair) -> 'pcbre.model.stackup.ViaPair':
    import pcbre.model.stackup
    l_first = project.scontext.get(msg.firstLayerSid)
    l_second = project.scontext.get(msg.secondLayerSid)

    vp = pcbre.model.stackup.ViaPair(project, l_first, l_second)
    project.scontext.set_sid(msg.sid, vp)

    return vp


def serialize_stackup(stackup: 'pcbre.model.project.Stackup') -> Stackup:
    stackup_msg = Stackup.new_message()
    stackup_msg.init("layers", len(stackup._layers))

    for n, i_l in enumerate(stackup._layers):
        stackup_msg.layers[n] = serialize_layer(i_l)

    stackup_msg.init("viapairs", len(stackup._via_pairs))
    for n, i_vp in enumerate(stackup._via_pairs):
        stackup_msg.viapairs[n] = serialize_viapair(i_vp)

    return stackup_msg


def deserialize_stackup(to: 'pcbre.model.project.Stackup', msg: Stackup) -> None:
    to._layers.clear()
    for i in msg.layers:
        to._layers.append(deserialize_layer(to._project, i))

    to._via_pairs.clear()
    for i in msg.viapairs:
        to._via_pairs.append(deserialize_viapair(to._project, i))

    to._renumber_layers()


def serialize_keypoint(self: 'pcbre.model.imagelayer.KeyPoint') -> KeypointMsg:
    msg = KeypointMsg.new_message()
    assert self._project is not None
    msg.sid = self._project.scontext.sid_for(self)
    msg.worldPosition = serialize_point2(self.world_position)
    return msg


def deserialize_keypoint(project: 'pcbre.model.project.Project', msg: KeypointMsg) -> 'pcbre.model.imagelayer.KeyPoint':
    import pcbre.model.imagelayer
    world_position = serialize_point2(msg.worldPosition)
    obj = pcbre.model.imagelayer.KeyPoint(project, world_position)

    project.scontext.set_sid(msg.sid, obj)
    obj._project = project
    return obj


def serialize_keypoint_alignment(keypoint_alignment: 'pcbre.model.imagelayer.KeyPointAlignment',
                                 project: 'Project') -> ImageTransformMsg.KeypointTransformMeta:
    msg = ImageTransformMsg.KeypointTransformMeta.new_message()
    msg.init("keypoints", len(keypoint_alignment._keypoint_positions))
    for n, i in enumerate(keypoint_alignment._keypoint_positions):
        msg.keypoints[n].kpSid = project.scontext.sid_for(i.key_point)
        msg.keypoints[n].position = serialize_point2f(i.image_pos)

    return msg


def deserialize_keypoint_alignment(project: 'pcbre.model.project.Project',
                                   msg: ImageTransform.KeypointTransformMeta) -> \
        'pcbre.model.imagelayer.KeyPointAlignment':
    import pcbre.model.imagelayer
    obj = pcbre.model.imagelayer.KeyPointAlignment()
    for i in msg.keypoints:
        obj.set_keypoint_position(project.scontext.get(i.kpSid), deserialize_point2f(i.position))
    return obj


def serialize_rect_alignment(rect_alignment: 'pcbre.model.imagelayer.RectAlignment') \
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

    msg.originCenter = serialize_point2f(rect_alignment.origin_center)

    for n, i_a in enumerate(rect_alignment.handles):
        __serialize_handle_capnp(i_a, msg.handles[n])

    for n, i_b in enumerate(rect_alignment.dim_handles):
        __serialize_handle_capnp(i_b, msg.dimHandles[n])

    msg.flipX = rect_alignment.flip_x
    msg.flipY = rect_alignment.flip_y

    return msg


def __serialize_handle_capnp(m: Optional[pcbre.matrix.Vec2], to: HandleMsg.Builder) -> None:
    if m is None:
        to.none = None
    else:
        to.point = serialize_point2f(m)


def __deserialize_handle_capnp(msg: HandleMsg.Reader) -> Optional[pcbre.matrix.Vec2]:
    if msg.which() == "none":
        return None
    else:
        return deserialize_point2f(msg.point)


def deserialize_rect_alignment(msg: ImageTransformMsg.RectTransformMeta.Reader) -> \
        'pcbre.model.imagelayer.RectAlignment':
    import pcbre.model.imagelayer
    handles = [__deserialize_handle_capnp(i) for i in msg.handles]
    dim_handles = [__deserialize_handle_capnp(i) for i in msg.dimHandles]
    dims = [i for i in msg.dims]

    assert len(handles) == 12
    assert len(dim_handles) == 4
    assert len(dims) == 2
    origin_corner = {
        "lowerLeft": 0,
        "lowerRight": 1,
        "upperLeft": 2,
        "upperRight": 3}[str(msg.originCorner)]

    origin_center = deserialize_point2f(msg.originCenter)

    return pcbre.model.imagelayer.RectAlignment(handles, dim_handles, dims, msg.lockedToDim,
                                                origin_center, origin_corner, msg.flipX, msg.flipY)


def serialize_imagelayer(imagelayer: 'pcbre.model.imagelayer.ImageLayer') -> 'ImageMsg.Builder':
    import pcbre.model.imagelayer
    msg = ImageMsg.new_message()
    msg.sid = imagelayer._project.scontext.sid_for(imagelayer)
    msg.data = imagelayer.data
    msg.name = imagelayer.name
    m = serialize_matrix(imagelayer.transform_matrix)
    msg.transform.matrix = m

    if imagelayer.alignment is None:
        # Assign "no-metadata-for-transform"
        msg.transform.meta.noMeta = None
    elif isinstance(imagelayer.alignment, pcbre.model.imagelayer.KeyPointAlignment):
        msg.transform.meta.init("keypointTransformMeta")
        msg.transform.meta.keypointTransformMeta = \
            serialize_keypoint_alignment(imagelayer.alignment, imagelayer._project)
    elif isinstance(imagelayer.alignment, pcbre.model.imagelayer.RectAlignment):
        msg.transform.meta.init("rectTransformMeta")
        msg.transform.meta.rectTransformMeta = serialize_rect_alignment(imagelayer.alignment)
    else:
        raise NotImplementedError("Don't know how to serialize %s" % imagelayer.alignment)

    return msg


def deserialize_imagelayer(project: 'pcbre.model.project.Project', msg: 'ImageMsg.Reader') -> \
        'pcbre.model.imagelayer.ImageLayer':
    import pcbre.model.imagelayer
    transform = deserialize_matrix(msg.transform.matrix)
    obj = pcbre.model.imagelayer.ImageLayer(project, msg.name, msg.data, transform)

    project.scontext.set_sid(msg.sid, obj)
    obj._project = project

    meta_which = msg.transform.meta.which()
    if meta_which == "noMeta":
        obj.set_alignment(None)
    elif meta_which == "keypointTransformMeta":
        obj.set_alignment(deserialize_keypoint_alignment(project, msg.transform.meta.keypointTransformMeta))
    elif meta_which == "rectTransformMeta":
        obj.set_alignment(deserialize_rect_alignment(msg.transform.meta.rectTransformMeta))
    else:
        raise NotImplementedError()

    return obj


def serialize_imagery(imagery: 'pcbre.model.project.Imagery') -> Imagery:
    imagery_msg = Imagery.new_message()

    imagery_msg.init("imagelayers", len(imagery.imagelayers))
    for n, i in enumerate(imagery.imagelayers):
        imagery_msg.imagelayers[n] = serialize_imagelayer(i)

    imagery_msg.init("keypoints", len(imagery.keypoints))

    for n, i_ in enumerate(imagery.keypoints):
        imagery_msg.keypoints[n] = serialize_keypoint(i_)

    return imagery_msg


def deserialize_imagery(to: 'pcbre.model.project.Imagery', msg: Imagery) -> None:
    # Keypoints may be used by the imagelayers during deserialize

    # Deserialize first to avoid a finalizer
    for i in msg.keypoints:
        to._keypoints.append(deserialize_keypoint(to._project, i))

    for i in msg.imagelayers:
        to._imagelayers.append(deserialize_imagelayer(to._project, i))


def serialize_nets(nets: 'pcbre.model.project.Nets') -> Nets:
    assert nets._project is not None

    _nets = Nets.new_message()
    _nets.init("netList", len(nets.nets))
    for n, i in enumerate(nets.nets):
        _nets.netList[n].sid = nets._project.scontext.sid_for(i)
        _nets.netList[n].name = i.name
        _nets.netList[n].nclass = i.net_class

    return _nets


def deserialize_nets(to: 'pcbre.model.project.Nets', msg: Nets) -> None:
    import pcbre.model.project
    assert to._project is not None

    for i in msg.netList:
        n = pcbre.model.project.Net(name=i.name, net_class=i.nclass)
        to._project.scontext.set_sid(i.sid, n)
        to.add_net(n)


def serialize_project(project: 'pcbre.model.project.Project') -> Project:
    project_msg = Project.new_message()
    project_msg.stackup = serialize_stackup(project.stackup)
    project_msg.imagery = serialize_imagery(project.imagery)
    project_msg.nets = serialize_nets(project.nets)
    project_msg.artwork = serialize_artwork(project.artwork)

    return project_msg


def deserialize_project(msg: Project) -> 'pcbre.model.project.Project':
    p = pcbre.model.project.Project()
    with p.scontext.restoring():
        deserialize_stackup(p.stackup, msg.stackup)
        deserialize_imagery(p.imagery, msg.imagery)
        deserialize_nets(p.nets, msg.nets)
        deserialize_artwork(p.artwork, msg.artwork)
    return p


def serialize_component_common(component: 'pcbre.model.component.Component', cmp_msg: 'ComponentMsg.Builder') -> None:
    import pcbre.model.component
    if component.side == pcbre.model.component.SIDE.Top:
        cmp_msg.side = "top"
    elif component.side == pcbre.model.component.SIDE.Bottom:
        cmp_msg.side = "bottom"
    else:
        raise NotImplementedError()

    cmp_msg.refdes = component.refdes
    cmp_msg.partno = component.partno

    cmp_msg.center = serialize_point2(component.center)
    cmp_msg.theta = float(component.theta)
    cmp_msg.sidUNUSED = 0

    cmp_msg.init("pininfo", len(component.get_pads()))
    for n, p in enumerate(component.get_pads()):
        k = p.pad_no
        t = cmp_msg.pininfo[n]

        t.identifier = k
        if k in component.name_mapping:
            t.name = component.name_mapping[k]

        t.net = component._project.scontext.sid_for(component.net_mapping[k])


def deserialize_component_common(project: 'pcbre.model.project.Project', msg: 'ComponentMsg.Reader',
                                 target: 'pcbre.model.component.Component') -> None:
    import pcbre.model.component
    if msg.side == "top":
        target.side = pcbre.model.component.SIDE.Top
    elif msg.side == "bottom":
        target.side = pcbre.model.component.SIDE.Bottom
    else:
        raise NotImplementedError()

    target.theta = msg.theta
    target.center = deserialize_point2(msg.center)
    target.refdes = msg.refdes
    target.partno = msg.partno

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


def serialize_sip_component(sip_component: 'pcbre.model.dipcomponent.SIPComponent',
                            sip_msg: 'ComponentMsg.Builder') -> None:
    serialize_component_common(sip_component, sip_msg.common)
    sip_msg.init("sip")

    m = sip_msg.sip

    m.pinCount = sip_component.pin_count
    m.pinSpace = sip_component.pin_space
    m.padSize = sip_component.pad_size


def deserialize_sip_component(project: 'pcbre.model.project.Project', sip_msg: 'ComponentMsg.Reader') -> \
        'pcbre.model.dipcomponent.SIPComponent':

    import pcbre.model.dipcomponent
    m = sip_msg.sip
    cmp: pcbre.model.dipcomponent.SIPComponent = pcbre.model.dipcomponent.SIPComponent.__new__(
        pcbre.model.dipcomponent.SIPComponent)

    deserialize_component_common(project, sip_msg.common, cmp)
    cmp._my_init(m.pinCount, m.pinSpace, m.padSize)
    return cmp


def serialize_dip_component(dip_component: 'pcbre.model.dipcomponent.DIPComponent',
                            dip_msg: 'ComponentMsg.Builder') -> None:

    serialize_component_common(dip_component, dip_msg.common)
    dip_msg.init("dip")

    m = dip_msg.dip

    m.pinCount = dip_component.pin_count
    m.pinSpace = dip_component.pin_space
    m.pinWidth = dip_component.pin_width
    m.padSize = dip_component.pad_size


def deserialize_dip_component(project: 'pcbre.model.project.Project', dip_msg: 'ComponentMsg.Reader') -> \
        'pcbre.model.component.Component':
    from pcbre.model.dipcomponent import DIPComponent
    m = dip_msg.dip
    cmp: DIPComponent = DIPComponent.__new__(DIPComponent)
    deserialize_component_common(project, dip_msg.common, cmp)
    cmp._my_init(m.pinCount, m.pinSpace, m.pinWidth, m.padSize, project)
    return cmp


def serialize_smd4_component(smd4component: 'pcbre.model.smd4component.SMD4Component',
                             cmp_msg: ComponentMsg.Builder) -> None:
    serialize_component_common(smd4component, cmp_msg.common)
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


def deserialize_smd4_component(project: 'pcbre.model.project.Project', msg: ComponentMsg.Reader) -> \
        'pcbre.model.smd4component.SMD4Component':
    import pcbre.model.smd4component
    t = msg.smd4
    cmp = pcbre.model.smd4component.SMD4Component(
        project,
        pcbre.matrix.Vec2(0, 0), 0,  pcbre.model.component.SIDE.Top,   # Placeholder values
        project,
        t.side1Pins, t.side2Pins, t.side3Pins, t.side4Pins,
        t.dim1Body, t.dim1PinEdge, t.dim2Body, t.dim2PinEdge,
        t.pinContactLength, t.pinContactWidth, t.pinSpacing)

    deserialize_component_common(project, msg.common, cmp)
    return cmp


def serialize_passive_component(passive_component: 'pcbre.model.passivecomponent.Passive2Component',
                                pasv_msg: 'ComponentMsg.Builder') -> None:
    serialize_component_common(passive_component, pasv_msg.common)
    pasv_msg.init("passive2")

    m = pasv_msg.passive2

    m.symType = passive_component.sym_type.value
    m.bodyType = passive_component.body_type.value
    m.pinD = int(passive_component.pin_d)
    m.bodyCornerVec = serialize_point2(passive_component.body_corner_vec)
    m.pinCornerVec = serialize_point2(passive_component.pin_corner_vec)


def deserialize_passive_component(project: 'pcbre.model.project.Project', pasv_msg: 'ComponentMsg.Reader') -> \
        'pcbre.model.passivecomponent.Passive2Component':
    import pcbre.model.passivecomponent as pma
    m = pasv_msg.passive2
    cmp: pma.Passive2Component = pma.Passive2Component.__new__(pma.Passive2Component)
    deserialize_component_common(project, pasv_msg.common, cmp)

    cmp.sym_type = pma.PassiveSymType(m.symType.raw)
    cmp.body_type = pma.Passive2BodyType(m.bodyType.raw)

    # Distance from center to pin
    cmp.pin_d = m.pinD

    cmp.body_corner_vec = deserialize_point2(m.bodyCornerVec)
    cmp.pin_corner_vec = deserialize_point2(m.pinCornerVec)
    cmp._pads = []

    return cmp


def serialize_artwork(artwork: 'pcbre.model.artwork.Artwork') -> Artwork.Builder:
    import pcbre.model.passivecomponent
    import pcbre.model.smd4component
    import pcbre.model.dipcomponent

    _aw = Artwork.new_message()
    _aw.init("vias", len(artwork.vias))
    _aw.init("traces", len(artwork.traces))
    _aw.init("polygons", len(artwork.polygons))
    _aw.init("components", len(artwork.components))
    _aw.init("airwires", len(artwork.airwires))

    # Serialization done here to reduce instance size
    for n, i_via in enumerate(artwork.vias):
        v = _aw.vias[n]
        v.point = serialize_point2(i_via.pt)
        v.r = i_via.r
        v.viapairSid = artwork._project.scontext.sid_for(i_via.viapair)
        v.netSid = artwork._project.scontext.sid_for(i_via.net)

    #
    for n, i_trace in enumerate(artwork.traces):
        t = _aw.traces[n]
        t.p0 = serialize_point2(i_trace.p0)
        t.p1 = serialize_point2(i_trace.p1)
        t.thickness = int(i_trace.thickness)
        t.netSid = artwork._project.scontext.sid_for(i_trace.net)
        t.layerSid = artwork._project.scontext.sid_for(i_trace.layer)

    for n, i_comp in enumerate(artwork.components):
        t = _aw.components[n]
        if isinstance(i_comp, pcbre.model.passivecomponent.Passive2Component):
            serialize_passive_component(i_comp, t)
        elif isinstance(i_comp, pcbre.model.dipcomponent.SIPComponent):
            serialize_sip_component(i_comp, t)
        elif isinstance(i_comp, pcbre.model.dipcomponent.DIPComponent):
            serialize_dip_component(i_comp, t)
        elif isinstance(i_comp, pcbre.model.smd4component.SMD4Component):
            serialize_smd4_component(i_comp, t)
        else:
            raise NotImplementedError("CAPNP serialization of %s is not supported" % repr(i_comp))

    for n, i_poly in enumerate(artwork.polygons):
        p = _aw.polygons[n]

        p_repr = i_poly.get_poly_repr()
        p.init("exterior", len(p_repr.exterior.coords))
        for nn, ii in enumerate(p_repr.exterior.coords):
            p.exterior[nn] = serialize_point2(pcbre.matrix.Point2(ii[0], ii[1]))

        p.init("interiors", len(p_repr.interiors))
        for n_interior, interior in enumerate(p_repr.interiors):
            p.interiors.init(n_interior, len(interior.coords))
            for nn, ii in enumerate(interior.coords):
                p.interiors[n_interior][nn] = serialize_point2(pcbre.matrix.Point2(ii[0], ii[1]))

        p.layerSid = artwork._project.scontext.sid_for(i_poly.layer)
        p.netSid = artwork._project.scontext.sid_for(i_poly.net)

    for n, i_ in enumerate(artwork.airwires):
        t = _aw.airwires[n]
        t.p0 = serialize_point2(i_.p0)
        t.p1 = serialize_point2(i_.p1)
        t.netSid = artwork._project.scontext.sid_for(i_.net)
        t.p0LayerSid = artwork._project.scontext.sid_for(i_.p0_layer)
        t.p1LayerSid = artwork._project.scontext.sid_for(i_.p1_layer)

    return _aw


def __lookup_net_helper(artwork: 'pcbre.model.artwork.Artwork', sid: int) -> Net:
    try:
        a = artwork._project.scontext.get(sid)
        assert isinstance(a, pcbre.model.project.Net)
        return a
    except KeyError:
        print("WARNING: invalid SID %d for net lookup, replacing with empty net", sid)
        return artwork._project.nets.new()


def deserialize_artwork(artwork: 'pcbre.model.artwork.Artwork', msg: Artwork) -> None:
    import pcbre.model.artwork
    for i_via in msg.vias:
        v = pcbre.model.artwork.Via(deserialize_point2(i_via.point),
                                    artwork._project.scontext.get(i_via.viapairSid),
                                    i_via.r,
                                    __lookup_net_helper(artwork, i_via.netSid)
                                    )

        artwork.add_artwork(v)

    for i_trace in msg.traces:
        t = pcbre.model.artwork.Trace(
            deserialize_point2(i_trace.p0),
            deserialize_point2(i_trace.p1),
            i_trace.thickness,
            artwork._project.scontext.get(i_trace.layerSid),
            __lookup_net_helper(artwork, i_trace.netSid)
        )
        artwork.add_artwork(t)

    for i_poly in msg.polygons:
        exterior = [deserialize_point2(j) for j in i_poly.exterior]
        interiors = [[deserialize_point2(k) for k in j] for j in i_poly.interiors]

        p = pcbre.model.artwork.Polygon(
            artwork._project.scontext.get(i_poly.layerSid),
            exterior,
            interiors,
            __lookup_net_helper(artwork, i_poly.netSid)
        )

        artwork.add_artwork(p)

    for i_airwire in msg.airwires:
        aw = pcbre.model.artwork.Airwire(
            deserialize_point2(i_airwire.p0),
            deserialize_point2(i_airwire.p1),
            artwork._project.scontext.get(i_airwire.p0LayerSid),
            artwork._project.scontext.get(i_airwire.p1LayerSid),
            artwork._project.scontext.get(i_airwire.netSid)
        )
        artwork.add_artwork(aw)

    for i_cmp in msg.components:
        if i_cmp.which() == "dip":
            cmp = deserialize_dip_component(artwork._project, i_cmp)
        elif i_cmp.which() == "sip":
            cmp = deserialize_sip_component(artwork._project, i_cmp)
        elif i_cmp.which() == "smd4":
            cmp = deserialize_smd4_component(artwork._project, i_cmp)
        elif i_cmp.which() == "passive2":
            cmp = deserialize_passive_component(artwork._project, i_cmp)
        else:
            raise NotImplementedError()

        artwork.add_component(cmp)
