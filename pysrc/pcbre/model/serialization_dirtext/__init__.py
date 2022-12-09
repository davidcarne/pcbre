import contextlib
import os
import re
import typing
import hashlib
import binascii
from typing import Dict, Tuple, Any, Iterable, BinaryIO, Optional, Generator, List, Callable, Any
import numpy

from pcbre.matrix import Point2
from pcbre.model.serialization import PersistentID, PersistentIDClass, SERIALIZATION_VERSION, PersistentIDRegistry

if typing.TYPE_CHECKING:
    import pcbre.model.project
    import pcbre.model.artwork
    import pcbre.model.net
    import pcbre.model.stackup
    import pcbre.model.component


class FileFormatError(Exception):
    pass


class ParseError(Exception):
    pass


def _encode_string(s: str) -> bytes:
    slist = []
    needs_escaping = False
    for c in s:
        if c == '\\':
            slist.append(r'\\')
            needs_escaping = True
        if c == '"':
            slist.append(r'\"')
            needs_escaping = True
        elif c == '\r':
            slist.append(r'\r')
            needs_escaping = True
        elif c == '\n':
            slist.append(r'\n')
            needs_escaping = True
        elif c == '\t':
            slist.append(r'\t')
            needs_escaping = True
        elif not c.isalnum() and not c == '_':
            slist.append(c)
            needs_escaping = True
        else:
            slist.append(c)

    if len(s) == 0:
        needs_escaping = True

    if needs_escaping:
        return b'"%b"' % "".join(slist).encode("utf8")

    return s.encode("utf8")


class Tokenizer:
    WORD_MATCH = re.compile(rb"^([-+a-zA-Z0-9_.][a-zA-Z0-9_.]*)")

    def __init__(self, line: bytes):
        self.buf = line
        self.pos = 0

    def remaining(self):
        return len(self.buf) - self.pos

    def peek(self) -> bytes:
        return self.buf[self.pos:self.pos+1]

    def take1(self) -> bytes:
        r = self.buf[self.pos: self.pos+1]
        self.pos += 1
        return r

    def get_string_token(self):
        # Initial quote
        self.take1()

        b = list()

        escaped = False
        while self.remaining() >= 1:
            ch = self.take1()
            if not escaped:
                if ch == b'"':
                    return b"".join(b)
                elif ch == b'\\':
                    escaped = True
                else:
                    b.append(ch)
            else: # escaped
                if ch == b"\"":
                    b.append(b"\"")
                elif ch == b"\\":
                    b.append(b"\\")
                elif ch == b"n":
                    b.append(b"\n")
                elif ch == b"t":
                    b.append(b"\t")
                elif ch == b"r":
                    b.append(b"\r")
                else:
                    raise ParseError("Unknown Escape")
                escaped = False

        raise ParseError("Unterminated string")

    def get_word_integer(self):
        # TODO
        # take up until the next
        # space, comma, paren, equals
        # any non alnum, underscore is a parse error
        m = self.WORD_MATCH.match(self.buf[self.pos:])
        if m is None:
            raise ParseError("Bad word")
        s = m.group(1)
        self.pos += len(s)
        return s

    def get_token(self) -> Optional[bytes]:
        while self.remaining() >= 1:
            ch = self.peek()
            if ch == b" " or ch == b"\t":
                self.take1()
                continue
            elif ch == b'(' or ch == b')' or ch == b'=' or ch == b',':
                return self.take1()
            elif ch == b'"':
                return self.get_string_token()
            else:
                return self.get_word_integer()

        return None

    def __iter__(self):
        return self

    def __next__(self):
        t = self.get_token()
        if t is None:
            raise StopIteration()
        return t


def parse_recursive(tokenizer, line_no):
    first = tokenizer.get_token()
    if first == b'':
        return b''

    if first is None:
        raise ParseError("Missing token")

    if first in b'=,)':
        raise ParseError("Got unexpected equals")

    if first == b'(':
        l = []
        while 1:
            l.append(parse_recursive(tokenizer, line_no))
            separator = tokenizer.get_token()
            if separator == b")":
                return tuple(l)
            elif separator == b',':
                continue
            else:
                raise ParseError("Invalid tuple separator %s" % separator)
    else:
        return first


def parse_line_dict(line, line_no):
    top_level = {}

    tokenizer = Tokenizer(line)
    while 1:
        key = tokenizer.get_token()
        if key is None:
            break

        if not tokenizer.WORD_MATCH.match(key):
            raise ParseError("Expected key on line %d, got %s" % (line_no, key))

        if key in top_level:
            raise ParseError("Duplicate key %s on line %d" % (key, line_no))

        eqtoken = tokenizer.get_token()
        if eqtoken != b'=':
            raise ParseError("Expected '=' following key '%s' on line %d, got %s" % (key, line_no, eqtoken))

        value = parse_recursive(tokenizer, line_no)

        top_level[key] = value

    return top_level

def decode_persistent_id_str(v):
    cls, num = v.split(b'_')
    return PersistentID(PersistentIDClass[cls.decode('ascii')], int(num,16)).as_uint32

class DirTextIO:
    dir_path: os.PathLike[str]
    project: 'pcbre.model.project.Project'
    file_hashes: Dict[Tuple[str, ...], bytes]
    nets_ref: 'Dict[PersistentID, pcbre.model.net.Net]'
    layers_ref: 'Dict[PersistentID, pcbre.model.stackup.Layer]'
    viapairs_ref: 'Dict[PersistentID, pcbre.model.stackup.ViaPair]'
    keypoints_ref: 'Dict[PersistentID, pcbre.model.imagelayer.KeyPoint]'
    imagelayers_ref: 'Dict[PersistentID, pcbre.model.imagelayer.ImageLayer]'

    def _object_line_iter(self, fd: BinaryIO) -> Generator[Tuple[int, bytes, bytes], None, None]:
        for line_no, line in enumerate(fd.readlines(), start=1):
            hash_pos = line.find(b'#')
            if hash_pos != -1:
                line = line[:hash_pos]
            line = line.rstrip()

            if len(line) == 0:
                continue

            tokens = line.split(b' ', 1)
            if len(tokens) == 1:
                raise FileFormatError("line %d has only one token %s" % line_no)

            yield line_no, tokens[0], tokens[1]

    def __load_metadata(self):
        params = {}
        with self.__open_read_subfile(("project_info.txt",)) as fd:
            for line_no, token, remainder in self._object_line_iter(fd):
                params[token] = remainder

        if int(params[b"SERIALIZATION_VERSION"]) > SERIALIZATION_VERSION:
            raise FileFormatError("newer than this program")

    def __save_metadata(self) -> None:
        with self.__open_write_subfile(("project_info.txt",)) as fd:
            fd.write(b"# This is a PCBRE https://github.com/pcbre/pcbre directory format project file\n")
            fd.write(b"# The directory format is intended for versioning. The files should not be directly edited\n")
            fd.write(b"WRITER_VERSION 0\n") # TODO include
            fd.write(b"WRITER_GIT_HASH_ x\n") # TODO include
            fd.write(b"SERIALIZATION_VERSION %d\n" % SERIALIZATION_VERSION)


    def __unpack_partial(self, filename: str, line_no: int, defn: Tuple[Tuple[bytes, Callable[[Any], Any]], ...], params: Dict[bytes, Any]) -> Tuple[Dict, Any]:
        class _Record:
            pass

        r = _Record()
        for ent_name, cons in defn:
            setattr(r, ent_name.decode('utf8'), cons(params.pop(ent_name)))
        return params, r

    def __unpack_exact(self, filename: str, line_no: int, defn: Tuple[Tuple[bytes, Callable[[Any], Any]], ...], params: Dict[bytes, Any]) -> Any:
        remain, r = self.__unpack_partial(filename, line_no, defn, params)

        if len(remain):
            raise ParseError("Unknown keys %s on line %d of %s" % (params.keys(), line_no, filename))

        return r


    def __load_stackup(self) -> None:
        from pcbre.model.project import Layer, ViaPair
        layer_parse_def = (
            (b'index', int),
            (b'name', lambda x: x.decode("utf8")),
            (b'color', lambda x: (float(x[0]), float(x[1]), float(x[2]))),
            (b'unique_id', decode_persistent_id_str)
        )
        viapair_parse_def = (
            (b'unique_id', decode_persistent_id_str),
            (b'start_layer', decode_persistent_id_str),
            (b'end_layer', decode_persistent_id_str),
        )

        to_do_layers : List[Tuple[int, Layer]] = []
        viapairs = []

        with self.__open_read_subfile(("stackup.txt" ,)) as fd:
            for line_no, noun, line in self._object_line_iter(fd):
                params = parse_line_dict(line, line_no)
                if noun == b"LAYER":
                    r = self.__unpack_exact("stackup.txt", line_no, layer_parse_def, params)
                    layer_unique_id = self.project.unique_id_registry.decode_add_from_uint32(r.unique_id)
                    l = Layer(self.project, layer_unique_id, r.name, r.color)
                    self.layers_ref[layer_unique_id] = l
                    to_do_layers.append((r.index, l))

                elif noun == b"VIAPAIR":
                    r1 = self.__unpack_exact("stackup.txt", line_no, viapair_parse_def, params)
                    viapair_unique_id = self.project.unique_id_registry.decode_add_from_uint32(r1.unique_id)
                    viapairs.append((line_no, viapair_unique_id, r1))
                else:
                    raise ParseError("Unknown noun %s in 'stackup.txt' on line %d" % (noun, line_no))

        from collections import Counter
        layers = sorted(to_do_layers, key=lambda x: x[0])
        c = Counter(i[0] for i in layers)

        for i in range(0, len(layers)):
            if c[i] != 1:
                raise ValueError("Missing layer ordinal %d" %i)

        for ordinal, count in c.items():
            if count != 1:
                raise ValueError("Duplicate layer ordinal %d" % ordinal)

        for n, layer in layers:
            self.project.stackup._add_layer_existing(layer)
            assert layer.number == n

        for line_no, unique_id, record in viapairs:
            start_layer_id = self.project.unique_id_registry.decode_check_from_uint32(record.start_layer)
            end_layer_id = self.project.unique_id_registry.decode_check_from_uint32(record.end_layer)

            start_layer = self.layers_ref[start_layer_id]
            end_layer = self.layers_ref[end_layer_id]

            vp = ViaPair(self.project, unique_id, start_layer, end_layer)
            self.viapairs_ref[unique_id] = vp
            self.project.stackup._add_via_pair_existing(vp)


    def __save_stackup(self) -> None:
        with self.__open_write_subfile_hashed(("stackup.txt",)) as fd:
            for layer in self.project.stackup.layers:
                self.__write_record(fd, b"LAYER", (
                    (b"unique_id", layer.unique_id),
                    (b"index", layer.order),
                    (b"name", layer.name),
                    (b"color", layer.color)
                ))
            for viapair in self.project.stackup.via_pairs:
                self.__write_record(fd, b"VIAPAIR", (
                    (b"unique_id", viapair.unique_id),
                    (b"start_layer", viapair.layers[0].unique_id),
                    (b"end_layer", viapair.layers[1].unique_id)
                ))


    def __load_imagery(self) -> None:
        from pcbre.model.imagelayer import ImageLayer, KeyPointAlignment, RectAlignment, KeyPoint

        keypoint_def = (
            (b'unique_id', decode_persistent_id_str),
            (b'index', lambda x: int(x)),
            (b'world_position', lambda x: Point2(int(x[0]), int(x[1])))
        )

        image_base_def = (
            (b"unique_id", decode_persistent_id_str),
            (b"hash", lambda x:x.decode('utf8')),
            (b"name", lambda x: x.decode('utf8')),
            (b"transform", lambda x: [float(i) for i in x]),
            (b"alignment_mode", lambda x: x.decode('utf8'))
        )

        corner_map = {
            b"lower_left": 0,
            b"lower_right": 1,
            b"upper_left": 2,
            b"upper_right": 3
        }

        def point2f_or_none(x):
            if x == b"none":
                return None
            else:
                return Point2(float(x[0]), float(x[1]))

        rect_ext_def = (
            (b"handles", lambda x: tuple(point2f_or_none(i) for i in x)),
            (b"dim_handles", lambda x: tuple(point2f_or_none(i) for i in x)),
            (b"locked_to_dim", lambda x: x==b'true'),
            (b"origin_center", lambda x: Point2(int(x[0]), int(x[1]))),
            (b"origin_corner", lambda x: corner_map[x]),
            (b"dims", lambda x: (float(x[0]), float(x[1]))),
            (b"flip_x", lambda x: x == b'true'),
            (b"flip_y", lambda x: x == b'true')
        )

        def unpack_keypoint(kp_tuples):
            kp_unpack = []
            for x in kp_tuples:
                uid_s = decode_persistent_id_str(x[0])
                uid = self.project.unique_id_registry.decode_check_from_uint32(uid_s)
                p = Point2(float(x[1][0]), float(x[1][1]))
                kp_unpack.append((uid, p))

            return kp_unpack

        keypoint_ext_def = (
            (b"keypoints", unpack_keypoint),
        )

        keypoints = []
        images = []
        with self.__open_read_subfile(("imagery", "setup.txt")) as fd:
            for line_no, noun, line in self._object_line_iter(fd):
                params = parse_line_dict(line, line_no)
                if noun == b'KEYPOINT':
                    keypoint_r = self.__unpack_exact("imagery/setup.txt", line_no, keypoint_def, params)
                    uid = self.project.unique_id_registry.decode_add_from_uint32(keypoint_r.unique_id)
                    keypoints.append((uid, keypoint_r))
                if noun == b'IMAGE':
                    remaining, base_image_r = self.__unpack_partial("imagery/setup.txt", line_no, image_base_def, params)
                    uid = self.project.unique_id_registry.decode_add_from_uint32(base_image_r.unique_id)
                    if base_image_r.alignment_mode == "rect":
                        ext_r = self.__unpack_exact("imagery/setup.txt", line_no, rect_ext_def, remaining)
                    elif base_image_r.alignment_mode == "keypoint":
                        ext_r = self.__unpack_exact("imagery/setup.txt", line_no, keypoint_ext_def, remaining)
                    elif base_image_r.alignment_mode == "none":
                        ext_r = None
                    else:
                        raise ValueError("Unknown align mode %s" % base_image_r.alignment_mode)

                    images.append((uid, base_image_r, ext_r))

        # Instantiate keypoints
        self.project.imagery._keypoints.clear()
        for uid, kp in sorted(keypoints, key=lambda x: x[1].index):
            kp_o = KeyPoint(self.project, kp.world_position, uid)
            self.project.imagery._keypoints.append(kp_o)
            self.keypoints_ref[uid] = kp_o

        # Alignments
        for uid, image_r, ext_r in images:
            flat_arr = numpy.asarray(image_r.transform, dtype=numpy.float64)
            transform = numpy.reshape(flat_arr, (3, 3))
            with self.__open_read_subfile(("imagery", "img_%s" % image_r.hash)) as binfd:
                data = binfd.read()

            il = ImageLayer(self.project, uid, image_r.name, data, transform)

            if image_r.alignment_mode == "keypoint":
                alignment = KeyPointAlignment()
                for uid, worldpos in ext_r.keypoints:
                    kp = self.keypoints_ref[uid]
                    alignment.set_keypoint_position(kp, worldpos)

                il.set_alignment(alignment)
            elif image_r.alignment_mode == "rect":
                alignment = RectAlignment(ext_r.handles, ext_r.dim_handles, ext_r.dims, ext_r.locked_to_dim,
                                          ext_r.origin_center, ext_r.origin_corner,
                                          bool(ext_r.flip_x), bool(ext_r.flip_y))
                il.set_alignment(alignment)

            self.project.imagery._imagelayers.append(il)
            self.imagelayers_ref[uid] = il



    def __save_imagery(self) -> None:
        from pcbre.model.imagelayer import RectAlignment, KeyPointAlignment
        with self.__open_write_subfile(("imagery", "setup.txt")) as setup_fd:
            for keypoint in self.project.imagery.keypoints:
                self.__write_record(setup_fd, b"KEYPOINT", (
                    (b"unique_id", keypoint.unique_id),
                    (b"index", keypoint.index),
                    (b"world_position", keypoint.world_position),
                ))

            for image in self.project.imagery.imagelayers:
                content_hash = hashlib.sha256()
                content_hash.update(image.data)
                img_digest = binascii.b2a_hex(content_hash.digest()).decode("ascii")
                img_filename = "img_%s" % img_digest

                with self.__open_write_subfile(("imagery", img_filename)) as img_fd:
                    img_fd.write(image.data)

                if isinstance(image.alignment, RectAlignment):
                    align: 'RectAlignment' = image.alignment
                    alignment_mode = "rect"
                    corner = {
                        0: "lower_left",
                        1: "lower_right",
                        2: "upper_left",
                        3: "upper_right"
                    }[align.origin_corner]
                    alignment_specific = (
                        (b"handles", tuple(align.handles)),
                        (b"dim_handles", tuple(align.dim_handles)),
                        (b"locked_to_dim", align.dims_locked),
                        (b"origin_center", Point2(*align.origin_center.to_int_tuple())),
                        (b"origin_corner", corner),
                        (b"dims", tuple(align.dims)),
                        (b"flip_x", align.flip_x),
                        (b"flip_y", align.flip_y)
                    )
                elif isinstance(image.alignment, KeyPointAlignment):
                    alignment_mode = "keypoint"
                    kp_align: 'KeyPointAlignment' = image.alignment
                    key_point_data = []
                    for kp in sorted(kp_align.keypoint_positions, key=lambda x: x.key_point.index):
                        key_point_data.append((
                            kp.key_point.unique_id,
                            kp.image_pos
                        ))
                    alignment_specific = (
                        (b"keypoints", tuple(key_point_data)),
                    )
                elif image.alignment is None:
                    alignment_mode = "none"
                    alignment_specific = ()

                self.__write_record(setup_fd, b"IMAGE", (
                    (b"unique_id", image.unique_id),
                    (b"hash", img_digest),
                    (b"name", image.name),
                    (b"transform", image.transform_matrix),
                    (b"alignment_mode", alignment_mode)
                ) + alignment_specific)

    def __load_nets(self):
        from pcbre.model.net import Net
        # TODO - prune unreferenced nets
        # TODO - generate unconnected nets
        all_nets = []
        with self.__open_read_subfile(("nets.txt",)) as fd:
            for line_no, noun, remainder in self._object_line_iter(fd):
                if noun != b"NET":
                    raise ParseError("Unknown object %s in nets.txt on line %d" % (noun, line_no))

                params = parse_line_dict(remainder, line_no)
                unique_id_str = decode_persistent_id_str(params.pop(b"unique_id"))
                unique_id = self.project.unique_id_registry.decode_add_from_uint32(unique_id_str)
                name = params.pop(b"name").decode("utf8")
                if name == "":
                    name = None
                net_class = params.pop(b"net_class").decode("utf8")

                if params != {}:
                    raise ParseError("Unknown keys %s on line %s of nets.txt" % (params.keys(), line_no))

                self.nets_ref[unique_id] = net = Net(unique_id, name, net_class)
                net._project = self.project
                all_nets.append(net)

        for net in all_nets:
            self.project.nets._add_net(net)

    def __save_nets(self) -> None:
        with self.__open_write_subfile(("nets.txt",)) as fd:
            for net in self.project.nets.nets:
                if net._name is None:
                    name = ""
                else:
                    name = net._name

                self.__write_record(fd, b"NET", (
                    (b"unique_id", net.unique_id),
                    (b"name", name),
                    (b"net_class", net.net_class)
                ))

    def __load_component_defs(self) -> None:
        pass

    def __save_component_defs(self) -> None:
        pass

    def __load_artwork(self) -> None:
        from pcbre.model.artwork_geom import Via, Trace, Polygon, Airwire
        via_def = (
            (b"center", lambda x: Point2(int(x[0]), int(x[1]))),
            (b"radius", lambda x: int(x)),
            (b"viapair", decode_persistent_id_str),
            (b"net", decode_persistent_id_str),
        )
        trace_def = (
            (b"p0", lambda x: Point2(int(x[0]), int(x[1]))),
            (b"p1", lambda x: Point2(int(x[0]), int(x[1]))),
            (b"thickness", lambda x: int(x)),
            (b"layer", decode_persistent_id_str),
            (b"net", decode_persistent_id_str),
        )
        airwire_def = (
            (b"p0", lambda x: (decode_persistent_id_str(x[0]), Point2(int(x[1][0]), int(x[1][1])))),
            (b"p1", lambda x: (decode_persistent_id_str(x[0]), Point2(int(x[1][0]), int(x[1][1])))),
            (b"net", decode_persistent_id_str),
        )

        polygon_def = (
            (b"exterior", lambda x: tuple(Point2(int(i[0]), int(i[1])) for i in x)),
            (b"interior", lambda x: tuple(
                tuple(Point2(int(i[0]), int(i[1])) for i in interior) for interior in x
            )),
            (b"layer", decode_persistent_id_str),
            (b"net", decode_persistent_id_str),
        )

        with self.__open_read_subfile(("artwork", "vias.txt")) as fd:
            for line_no, noun, remainder in self._object_line_iter(fd):
                if noun != b"VIA":
                    raise ValueError("Unknown noun %s on line %d of artwork/vias.txt" % (noun, line_no))
                params = parse_line_dict(remainder, line_no)
                rec = self.__unpack_exact("artwork/vias.txt", line_no, via_def, params)
                vp = self.viapairs_ref[self.project.unique_id_registry.decode_check_from_uint32(rec.viapair)]
                net = self.nets_ref[self.project.unique_id_registry.decode_check_from_uint32(rec.net)]
                v = Via(rec.center, vp, rec.radius, net)
                self.project.artwork.add_artwork(v)

        with self.__open_read_subfile(("artwork", "traces.txt")) as fd:
            for line_no, noun, remainder in self._object_line_iter(fd):
                if noun != b"TRACE":
                    raise ValueError("Unknown noun %s on line %d of artwork/traces.txt" % (noun, line_no))
                params = parse_line_dict(remainder, line_no)
                rec = self.__unpack_exact("artwork/traces.txt", line_no, trace_def, params)
                layer = self.layers_ref[self.project.unique_id_registry.decode_check_from_uint32(rec.layer)]
                net = self.nets_ref[self.project.unique_id_registry.decode_check_from_uint32(rec.net)]
                v = Trace(rec.p0, rec.p1, rec.thickness, layer, net)
                self.project.artwork.add_artwork(v)

        with self.__open_read_subfile(("artwork", "airwires.txt")) as fd:
            for line_no, noun, remainder in self._object_line_iter(fd):
                if noun != b"AIRWIRE":
                    raise ValueError("Unknown noun %s on line %d of artwork/airwires.txt" % (noun, line_no))
                params = parse_line_dict(remainder, line_no)
                rec = self.__unpack_exact("artwork/airwires.txt", line_no, airwire_def, params)

                p0_layer = self.layers_ref[self.project.unique_id_registry.decode_check_from_uint32(rec.p0[0])]
                p1_layer = self.layers_ref[self.project.unique_id_registry.decode_check_from_uint32(rec.p1[0])]
                net = self.nets_ref[self.project.unique_id_registry.decode_check_from_uint32(rec.net)]
                v = Airwire(rec.p0[1], rec.p1[1], p0_layer, p1_layer, net)
                self.project.artwork.add_artwork(v)

        with self.__open_read_subfile(("artwork", "polygons.txt")) as fd:
            for line_no, noun, remainder in self._object_line_iter(fd):
                if noun != b"POLYGON":
                    raise ValueError("Unknown noun %s on line %d of artwork/polygons.txt" % (noun, line_no))
                params = parse_line_dict(remainder, line_no)
                rec = self.__unpack_exact("artwork/polygons.txt", line_no, polygon_def, params)

                layer = self.layers_ref[self.project.unique_id_registry.decode_check_from_uint32(rec.layer)]
                net = self.nets_ref[self.project.unique_id_registry.decode_check_from_uint32(rec.net)]

                v = Polygon(layer, rec.exterior, rec.interior, net)
                self.project.artwork.add_artwork(v)

    def __save_artwork(self) -> None:

        # vias
        with self.__open_write_subfile_hashed(("artwork", "vias.txt")) as fd:
            def via_key(v: 'pcbre.model.artwork.Via'):
                return v.viapair.unique_id, v.pt.x, v.pt.y, v.r

            for via in sorted(self.project.artwork.vias, key=via_key):
                self.__write_record(fd, b"VIA", (
                    (b"center", via.pt),
                    (b"radius", via.r),
                    (b"viapair", via.viapair.unique_id),
                    (b"net", via.net.unique_id)
                ))

        # traces
        with self.__open_write_subfile_hashed(("artwork", "traces.txt")) as fd:
            def trace_key(t: 'pcbre.model.artwork.Trace'):
                return t.layer.unique_id, t.p0.x, t.p0.y, t.p1.x, t.p1.y, t.thickness

            for trace in sorted(self.project.artwork.traces, key=trace_key):
                self.__write_record(fd, b"TRACE", (
                    (b"p0", trace.p0),
                    (b"p1", trace.p1),
                    (b"thickness", trace.thickness),
                    (b"layer", trace.layer.unique_id),
                    (b"net", trace.net.unique_id)
                ))

        # polygons
        with self.__open_write_subfile_hashed(("artwork", "polygons.txt")) as fd:
            def poly_key(p: 'pcbre.model.artwork.Polygon'):
                p_repr = p.get_poly_repr()
                return tuple(tuple(j) for j in p_repr.exterior.coords), \
                       tuple(tuple(tuple(j) for j in i.coords) for i in p_repr.interiors)

            for poly in sorted(self.project.artwork.polygons, key=poly_key):
                p_repr = poly.get_poly_repr()
                self.__write_record(fd, b"POLYGON", (
                    (b"layer", poly.layer.unique_id),
                    (b"net", poly.net.unique_id),
                    (b"exterior", tuple(Point2(int(i[0]), int(i[1])) for i in p_repr.exterior.coords)),
                    (b"interior", tuple(
                        tuple(
                            Point2(int(i[0]), int(i[1])) for i in interior.coords
                        ) for interior in p_repr.interiors
                    )),
                ))

        # components
        # TODO: waiting for component FP definition

        # airwires
        with self.__open_write_subfile_hashed(("artwork", "airwires.txt")) as fd:
            def airwire_key(a: 'pcbre.model.artwork.Airwire'):
                return a.p0_layer.unique_id, a.p1_layer.unique_id, a.p0.x, a.p0.y, a.p1.x, a.p1.y

            for airwire in sorted(self.project.artwork.airwires, key=airwire_key):
                self.__write_record(fd, b"AIRWIRE", (
                    (b"p0", (airwire.p0_layer.unique_id, airwire.p0)),
                    (b"p1", (airwire.p1_layer.unique_id, airwire.p1)),
                    (b"net", airwire.net.unique_id),
                ))


    def __check_checksum(self) -> bool:
        pass

    def __write_checksum(self) -> None:
        ordered_hashes = sorted(self.file_hashes.items(), key=lambda x: x[1])

        hash_string = b";".join(b"%b:%b" % (
            b"/".join(i.encode("utf8") for i in path_components),
            binascii.b2a_hex(digest))
                                for path_components, digest in ordered_hashes)

        hasher = hashlib.sha256()
        hasher.update(hash_string)
        digest = hasher.digest()

        with self.__open_write_subfile(("checksum.txt",)) as fd:
            fd: typing.BinaryIO
            fd.write(b"# This checksum is used to validate that the file hasn't been edited/merged\n")
            fd.write(b"# which could invalidate electrical connnectivity. If you edit the files in\n")
            fd.write(b"# this repository outside of PCBRE, do not try to recompute this checksum. \n")
            fd.write(b"# Instead, delete this file, or leave the checksum invalid\n")
            fd.write(b"# PCBRE will then know to recalculate electrical connectivity at next load\n")

            fd.write(b"HASH: %s\n" % binascii.b2a_hex(digest))


    def __convert_value(self, object_typestr, key_name, value):
        if isinstance(value, str):
            value_repr = _encode_string(value)
        elif isinstance(value, bool):
            if value:
                value_repr = b"true"
            else:
                value_repr = b"false"
        elif isinstance(value, int):
            value_repr = b"%d" % value
        elif isinstance(value, float):
            value_repr = b"%f" % value
        elif value is None:
            value_repr = b"none"
        elif isinstance(value, PersistentID):
            value_repr = b"%b_%#08x" % (value.id_class.name.encode("ascii"), value.id_value)
        elif isinstance(value, Point2):
            value_repr = self.__convert_value(object_typestr, key_name, (value.x, value.y))
        elif isinstance(value, tuple):
            elements = []
            for n, sub_element in enumerate(value):
                elements.append(self.__convert_value(object_typestr,
                                                     key_name + b"[%d]" % n,
                                                     sub_element))

            value_repr = b"(%b)" % (b", ".join(elements))
        elif isinstance(value, numpy.ndarray):
            if value.shape not in ((3, 3), (4, 4)):
                raise NotImplementedError("Unknown matrix shape %r for parameter %s object %s" % (
                    value.shape,
                    key_name,
                    object_typestr
                ))

            value_repr = b"(%b)" % (b", ".join(b"%f" % i for i in value.flatten()))
        else:
            raise NotImplementedError("Cannot save parameter %s type %s for object %s, " % (
                key_name,
                type(value),
                object_typestr))
        return value_repr

    def __write_record(self, fd: typing.BinaryIO, object_typestr: bytes, record: Iterable[Tuple[bytes, Any]]) -> None:
        key_strings = [object_typestr]
        for key_name, value in record:
            value_repr = self.__convert_value(object_typestr, key_name, value)
            key_strings.append(b"%b=%b" % (key_name, value_repr))

        fd.write(b"%b\n" % b" ".join(key_strings))


    @contextlib.contextmanager
    def __open_read_subfile(self, sub_path_components: Tuple[str, ...]) -> \
            typing.Generator[typing.BinaryIO, None, None]:

        for i in range(len(sub_path_components)-1):
            subdir_path = os.path.join(self.dir_path, *sub_path_components[:i + 1])
            if not os.path.exists(subdir_path):
                raise IOError("Path %s does not exist" % subdir_path)
        with open(os.path.join(self.dir_path, *sub_path_components), "rb") as fd:
            yield fd


    @contextlib.contextmanager
    def __open_write_subfile(self, sub_path_components: Tuple[str, ...]) -> \
            typing.Generator[typing.BinaryIO, None, None]:

        for i in range(len(sub_path_components)-1):
            subdir_path = os.path.join(self.dir_path, *sub_path_components[:i + 1])
            if not os.path.exists(subdir_path):
                os.mkdir(subdir_path)
        with open(os.path.join(self.dir_path, *sub_path_components), "wb") as fd:
            yield fd

    @contextlib.contextmanager
    def __open_write_subfile_hashed(self, sub_path_components: Tuple[str, ...]) -> \
            typing.Generator[typing.BinaryIO, None, None]:

        for i in range(len(sub_path_components)-1):
            subdir_path = os.path.join(self.dir_path, *sub_path_components[:i + 1])
            if not os.path.exists(subdir_path):
                os.mkdir(subdir_path)

        path = os.path.join(self.dir_path, *sub_path_components)
        with open(path, "wb") as fd:
            yield fd
            fd.flush()

        with open(path, "rb") as fd:
            fd.seek(0, os.SEEK_END)
            file_size = fd.tell()
            fd.seek(0, os.SEEK_SET)

            chunk_size = 4096

            hasher = hashlib.sha256()
            for i in range(0, file_size, chunk_size):
                read_size = chunk_size
                if file_size - i < chunk_size:
                    read_size = file_size - i

                data = fd.read(read_size)
                if len(data) != read_size:
                    raise IOError("Read came in short")

                hasher.update(data)

        self.file_hashes[sub_path_components] = hasher.digest()


    @staticmethod
    def open_path(dir_path: str) -> 'pcbre.model.project.Project':
        import pcbre.model.project

        if not os.path.isdir(dir_path):
            raise IOError("open target is not a directory")
        dir_path = os.path.abspath(dir_path)
        io = DirTextIO()
        io.dir_path = dir_path
        io.project = pcbre.model.project.Project()
        io.nets_ref = {}
        io.viapairs_ref = {}
        io.layers_ref = {}
        io.keypoints_ref = {}
        io.imagelayers_ref = {}
        io.images_ref = {}

        io.__load_metadata()
        io.__load_stackup()
        io.__load_imagery()
        io.__load_nets()
        io.__load_component_defs()
        io.__load_artwork()
        checksum_ok = io.__check_checksum()

        if not checksum_ok:
            io.project.artwork.rebuild_connectivity()

        return io.project

    @staticmethod
    def save_path(dir_path: str, project: 'pcbre.model.project.Project') -> None:
        path_split = os.path.split(dir_path)
        if path_split[-1] == "":
            path_split = path_split[:-1]

        parent_dir_path = os.path.abspath(os.path.join(*path_split[:-1]))

        if not os.path.isdir(parent_dir_path):
            raise IOError("Parent of save target is not a directory")

        dir_path = os.path.join(parent_dir_path, path_split[-1])
        if not os.path.exists(dir_path):
            os.mkdir(dir_path)
        else:
            if not os.path.isdir(dir_path):
                raise IOError("Save target exists and is not a directory")

        io = DirTextIO()
        io.project = project

        io.file_hashes = {}

        io.dir_path = dir_path
        io.__save_metadata()
        io.__save_stackup()
        io.__save_imagery()
        io.__save_nets()
        io.__save_component_defs()
        io.__save_artwork()
        io.__write_checksum()

