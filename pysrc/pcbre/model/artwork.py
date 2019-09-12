import itertools

from collections import defaultdict
import operator

from pcbre.algo.geom import dist_via_via, dist_via_trace, dist_trace_trace, \
            dist_via_pad, dist_trace_pad, dist_pad_pad, distance, point_inside, can_self_intersect, intersect
from pcbre.matrix import Point2
from pcbre.model import serialization as ser
from pcbre.model.artwork_geom import Trace, Via, Polygon, Airwire
from pcbre.model.component import Component
from pcbre.model.const import IntersectionClass
from pcbre.model.dipcomponent import DIPComponent
from pcbre.model.net import Net
from pcbre.model.pad import Pad
from pcbre.model.serialization import serialize_point2, deserialize_point2
from pcbre.model.smd4component import SMD4Component
from pcbre.model.util import ImmutableSetProxy

from rtree import index
import weakref

#kref Rules of engagement:
#
#   Once an item is added to artwork, it should be considered geometrically and electrically immutable
#
#
class ArtworkIndex:
    """
    Artwork index provides a wrapper on the Rtree spatial query library. Specifically, it resolves query results to
    physical geom objects, as well as uses the "fast" query paths
    """

    def __init__(self):
        self.__index = index.Index()
        self.__idx = 0

        self.__obj_to_idx = weakref.WeakKeyDictionary()
        self.__idx_to_obj = weakref.WeakValueDictionary()

    def __get_idx(self, k):
        try:
            return self.__obj_to_idx[k]
        except KeyError:
            r = self.__obj_to_idx[k] = self.__idx
            self.__idx_to_obj[r] = k
            self.__idx += 1
            return r

    def __get_obj(self, idx):
        try:
            return self.__idx_to_obj[idx]
        except KeyError:
            raise

    @staticmethod
    def __rect_index_order(rect):
        return (rect.left, rect.bottom, rect.right, rect.top)

    def insert(self, geom):
        self.__index.insert(self.__get_idx(geom), self.__rect_index_order(geom.bbox))

    def intersect(self, bbox):
        idxs = self.__index.intersection(self.__rect_index_order(bbox))
        return (self.__get_obj(idx) for idx in idxs)

    def nearest(self, bbox):
        idxs = self.__index.nearest(self.__rect_index_order(bbox))
        return (self.__get_obj(idx) for idx in idxs)

    def remove(self, geom):
        idx = self.__obj_to_idx[geom]
        del self.__obj_to_idx[geom]
        del self.__idx_to_obj[idx]

        self.__index.delete(idx, self.__rect_index_order(geom.bbox))

class Artwork:
    def __init__(self, project):
        self.__project = project
        self.__index = ArtworkIndex()

        self.__vias = set()
        self.__airwires = set()
        self.__traces = set()
        self.__polygons = set()
        self.__components = set()

        self.vias = ImmutableSetProxy(self.__vias)
        self.vias_generation = 0

        self.airwires = ImmutableSetProxy(self.__airwires)
        self.airwires_generation = 0

        self.traces = ImmutableSetProxy(self.__traces)
        self.traces_generation = 0

        self.components = ImmutableSetProxy(self.__components)
        self.components_generation = 0

        self.polygons = ImmutableSetProxy(self.__polygons)
        self.polygons_generation = 0

    def add_artwork(self, aw):
        """
        Add any single-net piece of geometry to the board artwork
        :param aw:
        :return:
        """
        assert aw is not None
        assert aw._project is None
        assert aw.net is not None
        assert aw.net._project is self.__project

        if isinstance(aw, Trace):
            self.__traces.add(aw)
            self.traces_generation += 1

        elif isinstance(aw, Via):
            self.__vias.add(aw)
            self.vias_generation += 1

        elif isinstance(aw, Polygon):
            self.__polygons.add(aw)
            self.polygons_generation += 1

        elif isinstance(aw, Airwire):
            self.__airwires.add(aw)
            self.airwires_generation += 1

        else:
            raise NotImplementedError()


        self.__index.insert(aw)

        aw._project = self.__project

    def add_component(self, cmp):
        """

        :param cmp:
        :return:
        """
        self.__components.add(cmp)
        cmp._project = self.__project

        self.__index.insert(cmp)
        for pad in cmp.get_pads():
            self.__index.insert(pad)

        self.components_generation += 1


    def merge_component(self, cmp):
        """
        :return:
        """

        for pad in cmp.get_pads():
            self.merge_aw_nets(pad)

        self.add_component(cmp)

    def remove_component(self, cmp):
        for pad in cmp.get_pads():
            self.remove_aw_nets(pad, suppress_presence_error=False)
            self.__index.remove(pad)

        self.__index.remove(cmp)
        self.__components.remove(cmp)

        self.components_generation += 1


    def remove_artwork(self, aw):
        assert aw._project is self.__project
        assert aw.net is not None

        # Strip
        aw_net = aw.net
        self.remove_aw_nets(aw)

        self.__index.remove(aw)

        if isinstance(aw, Trace):
            self.__traces.remove(aw)
            self.traces_generation += 1

        elif isinstance(aw, Via):
            self.__vias.remove(aw)
            self.vias_generation += 1

        elif isinstance(aw, Polygon):
            self.__polygons.remove(aw)
            self.polygons_generation += 1

        elif isinstance(aw, Airwire):
            self.__airwires.remove(aw)
            self.airwires_generation += 1

        else:
            raise NotImplementedError()

        # If its not an airwire we're removing
        # We need to find any airwires that rely on the geom
        # and remove them
        if not isinstance(aw, Airwire):
            for airwire in set(self.__airwires):
                if intersect(aw, airwire):
                    self.__airwires.remove(airwire)
                    self.airwires_generation += 1


        # If no remaining geometry is on the net, we need to drop it
        n = self.get_geom_for_net(aw_net)

        if len(n) == 0:
            self.__project.nets.remove_net(aw_net)

        aw._project = None

    def remove(self, aw):
        if isinstance(aw, Component):
            self.remove_component(aw)
        else:
            self.remove_artwork(aw)

    def merge(self, aw):
        if isinstance(aw, Component):
            self.merge_component(aw)
        else:
            self.merge_artwork(aw)


    @property
    def __all_pads(self):
        for c in self.components:
            yield from c.get_pads()

    def get_all_artwork(self):
        def gen():
            yield from self.__vias
            yield from self.__airwires
            yield from self.__traces
            yield from self.__polygons
            yield from self.__all_pads

        return gen()

    def get_geom_for_net(self, net):
        return [i for i in self.get_all_artwork() if i.net is net]

    def merge_nets(self, net1, net2):
        """
        Merge two nets, such that all artwork on net2 is now on net1, and net2 is deleted

        :param net1: destination Net object
        :param net2: source Net object
        :return: None
        """
        for aw in self.get_all_artwork():
            if aw.net == net2:
                aw.net = net1

        self.__project.nets.remove_net(net2)

    def merge_nets_many(self, nets):
        queue = list(nets)
        acc = queue.pop()

        while queue:
            n = queue.pop()
            self.merge_nets(acc, n)

        return acc

    def query_point(self, pt, layers_include=None, layers_exclude=None):
        """
        Queries a single point to identify geometry at that location

        :param pt: Point to query
        :type pt: (float, float)
        :param layers_include:
        :param layers_exclude:
        :return:
        """
        pt = Point2(pt)

        # layers_include / layers_exclude specify IDs of the layers to search, or exclude from the search
        # since exclude implicitly means "all layers minus the specified", the combination of both is invalid
        assert layers_include is None or layers_exclude is None

        for aw in self.get_all_artwork():
            if point_inside(aw, pt):
                return aw

        for cmp in self.components:
            if cmp.point_inside(pt):
                return cmp

        return None

    def merge_aw_nets(self, new_geom):
        """
        Perform net merges that would occur if new_geom is added to the project
        :param new_geom:
        :return:
        """
        qr = self.query_intersect(new_geom)

        nets = set()
        if new_geom.net is not None:
            nets.add(new_geom.net)

        if len(qr) > 0:
            nets.update(i[1].net for i in qr)

        if len(nets) > 1:
            new_net = self.merge_nets_many(nets)
        elif len(nets) == 1:
            new_net = list(nets)[0]
        else:
            new_net = Net()
            self.__project.nets.add_net(new_net)

        new_geom.net = new_net

    def remove_aw_nets(self, geom, suppress_presence_error=False):
        """
        Perform any net-splitting that would occur if geom is removed from the project
        :param new_geom:
        :param suppress_presence_error: Ignore that the geometry being removed isn't actually present in the DB.
                                        primarily useful for unit tests
        :return:
        """
        connected = set([i for d, i in self.query_intersect(geom)])

        # Our query should find the object we're removing
        # In some cases, specifically those when the geometry is "virtual"
        # the removed geometry can't self-intersect, so we should not remove it from the list
        try:
            if can_self_intersect(geom):
                connected.remove(geom)
        except KeyError:
            if not suppress_presence_error:
                raise

        # Build list of all geometry on the net
        all_geom = []
        for aw in self.get_all_artwork():
            if aw.net == geom.net and aw is not geom:
                all_geom.append(aw)

        subgroups = self.compute_connected(all_geom)

        # Sanity check
        for g in subgroups:
            assert geom not in g
            for gg in g:
                assert gg.net == geom.net

        def net_gen():
            yield geom.net

            newnet = Net()
            self.__project.nets.add_net(newnet)
            yield newnet

        for group, net in zip(subgroups, net_gen()):
            for g in group:
                g.net = net

        geom.net = None



    def compute_connected(self, all_geom, progress_cb = lambda x,y:0 ):
        """
        Compute connected sets from all_geom
        :param all_geom:
        :return:
        """

        qh = set(all_geom)
        labno = 0
        geom_to_label = dict()
        label_to_geom = defaultdict(set)
        seen = set()

        size = len(qh)
        while qh:
            progress_cb(size - len(qh), size)
            k = qh.pop()
            label = None

            connected = self.intersect_with(k, seen)
            seen.add(k)

            for n in connected:
                eg = geom_to_label[n]

                if label is None:
                    # If we don't have a label then take the label of what we're connected to
                    label_to_geom[eg].add(k)
                    geom_to_label[k] = eg
                    label = eg

                elif eg != label:
                    # If we do have a label, but this group isn't us
                    # Update all such that it has the same group
                    update_set = label_to_geom[eg]
                    del label_to_geom[eg]
                    label_to_geom[label].update(update_set)

                    for i in update_set:
                        geom_to_label[i] = label

            # Still no label
            if label == None:
                geom_to_label[k] = labno
                label_to_geom[labno].add(k)
                labno += 1

        return list(label_to_geom.values())


    def rebuild_connectivity(self, progress_cb = lambda x,y:0):
        connectivity = self.compute_connected(self.get_all_artwork(), progress_cb = progress_cb)

        # First, for each existing net, we identify which groups are owned by the net
        # and remove the groups having the smaller amounts of geometry (by count)
        nets_to_groups = defaultdict(list)
        for g in connectivity:
            for i in g:
                nets_to_groups[i.net].append(g)

        for net, groups in nets_to_groups.items():
            groups_sorted = sorted(groups, key=len)
            for g in groups_sorted[:-1]:
                for i in g:
                    if i.net == net:
                        i.net = None

        # Second, now for all groups, we build a list of all nets on the group. We choose the
        # highest priority net and assign it to the whole group
        for group in connectivity:
            nets = set(i.net for i in group if i.net is not None)
            # TODO: Prioritize net
            if len(nets) == 0:
                n0 = self.__project.nets.new()
            else:
                n0 = nets.pop()

            for i in group:
                i.net = n0



    def merge_artwork(self, geom):
        """
        Merge a geometry object into the design. Takes care of either assigning object a net, or merging nets if necessary
        :param geom:
        :rtype: bool
        :return: Whether the geometry may be merged
        """

        assert geom._project is None

        self.merge_aw_nets(geom)
        self.add_artwork(geom)

    def query_intersect(self, geom):
        qr = self.query(geom, bbox_prune=True)
        return list(itertools.takewhile(lambda a: a[0] <= 0, qr))


    def intersect_sets(self, a, b):
        """
        Determine the intersections between sets a and b
        :param a:
        :param b:
        :return:
        """
        # Ensure no duplicates
        a = set(a)
        b = set(b)
        raise NotImplementedError()

    def intersect_with(self, a, b):
        """
        returns all geoms from list b that intersect with a
        :param a:
        :param b:
        :return:
        """

        bbox_items = self.__index.intersect(a.bbox)

        pruned_list = b.intersection(bbox_items)

        res = []
        for i in pruned_list:
            if distance(a, i) <= 0:
                res.append(i)
        return res




    # return distance-sorted list of intersects
    def query(self, geom, bbox_prune = False):
        """

        :param geom:  object to query
        :param distance: if d is None, find nearest object (or all touching objects).
                        If d is a number, those nearer than d
        :return: list of artwork objects
        """
        assert bbox_prune

        if bbox_prune:
            ilist = self.__index.intersect(geom.bbox)
            ilist = [i for i in ilist if i.ISC != IntersectionClass.NONE]

            return sorted([(distance(geom, other), other) for other in ilist], key=operator.itemgetter(0))

        bbox = geom.bbox

        results = []
        if isinstance(geom, Via):
            # Build structures used to determine if artwork is on same layer
            vps_ok = {}
            my_layerset = set(id(i) for i in geom.viapair.all_layers)

            for v in self.__project.stackup.via_pairs:
                v_layerset = set(id(i) for i in v.all_layers)
                vps_ok[id(v)] = len(v_layerset.intersection(my_layerset))

            for other in self.__vias:
                if not vps_ok[id(other.viapair)]:
                    continue

                if bbox_prune and not bbox.intersects(other.bbox):
                    continue

                results.append((
                    dist_via_via(geom, other),
                    other
                ))

            for other in self.__traces:
                if id(other.layer) not in my_layerset:
                    continue

                if bbox_prune and not bbox.intersects(other.bbox):
                    continue

                results.append((
                    dist_via_trace(geom, other),
                    other
                ))

            for other in self.__all_pads:
                if other.is_through() or other.layer in geom.viapair.all_layers:

                    if bbox_prune and not bbox.intersects(other.bbox):
                        continue
                    results.append((
                        dist_via_pad(geom, other),
                        other
                    ))


        elif isinstance(geom, Trace):
            for other in self.__traces:
                if other.layer is not geom.layer:
                    continue

                if bbox_prune and not bbox.intersects(other.bbox):
                    continue
                results.append((
                        dist_trace_trace(geom, other),
                    other
                ))


            # Build lookup to check viapair
            vps_ok = {}
            for v in self.__project.stackup.via_pairs:
                v_layerset = set(id(i) for i in v.all_layers)
                vps_ok[id(v)] = id(geom.layer) in v_layerset

            for other in self.__vias:
                if not vps_ok[id(other.viapair)]:
                    continue

                if bbox_prune and not bbox.intersects(other.bbox):
                    continue

                results.append((
                    dist_via_trace(other, geom),
                    other
                ))

            for other in self.__all_pads:
                if bbox_prune and not bbox.intersects(other.bbox):
                    continue

                results.append((
                    dist_trace_pad(geom, other),
                    other
                ))

        elif isinstance(geom, Pad):
            # TODO: More opts here, can exclude some pads based on TH
            for other in self.__vias:
                if bbox_prune and not bbox.intersects(other.bbox):
                    continue

                results.append((
                    dist_via_pad(other, geom),
                    other
                ))

            for other in self.__traces:
                if bbox_prune and not bbox.intersects(other.bbox):
                    continue

                results.append((
                    dist_trace_pad(other, geom),
                    other
                ))

            for cmp in self.__components:
                if bbox_prune and not bbox.intersects(cmp.bbox):
                    continue

                for other in cmp.get_pads():
                    if bbox_prune and not bbox.intersects(other.bbox):
                        continue
                    results.append((
                        dist_pad_pad(geom, other),
                        other
                    ))

        else:
            raise NotImplementedError()

        return sorted(results, key=operator.itemgetter(0))

    def serialize(self):
        _aw = ser.Artwork.new_message()
        _aw.init("vias", len(self.vias))
        _aw.init("traces", len(self.traces))
        _aw.init("polygons", len(self.polygons))
        _aw.init("components", len(self.components))
        _aw.init("airwires", len(self.airwires))

        # Serialization done here to reduce instance size
        for n, i in enumerate(self.vias):
            v = _aw.vias[n]
            v.point = serialize_point2(i.pt)
            v.r = i.r
            v.viapairSid = self.__project.scontext.sid_for(i.viapair)
            v.netSid = self.__project.scontext.sid_for(i.net)

        #
        for n, i in enumerate(self.traces):
            t = _aw.traces[n]
            t.p0 = serialize_point2(i.p0)
            t.p1 = serialize_point2(i.p1)
            t.thickness = int(i.thickness)
            t.netSid = self.__project.scontext.sid_for(i.net)
            t.layerSid = self.__project.scontext.sid_for(i.layer)

        for n, i in enumerate(self.components):
            t = _aw.components[n]
            i.serializeTo(t)

        for n, i in enumerate(self.polygons):
            p = _aw.polygons[n]

            p_repr = i.get_poly_repr()
            p.init("exterior", len(p_repr.exterior.coords))
            for nn, ii in enumerate(p_repr.exterior.coords):
                p.exterior[nn] = serialize_point2(Point2(ii))

            p.init("interiors", len(p_repr.interiors))
            for n_interior, interior in enumerate(p_repr.interiors):
                p.interiors.init(n_interior, len(interior.coords))
                for nn, ii in enumerate(interior.coords):
                    p.interiors[n_interior][nn] = serialize_point2(Point2(ii))

            p.layerSid = self.__project.scontext.sid_for(i.layer)
            p.netSid = self.__project.scontext.sid_for(i.net)

        for n, i in enumerate(self.airwires):
            t = _aw.airwires[n]
            t.p0 = serialize_point2(i.p0)
            t.p1 = serialize_point2(i.p1)
            t.netSid = self.__project.scontext.sid_for(i.net)
            t.p0LayerSid = self.__project.scontext.sid_for(i.p0_layer)
            t.p1LayerSid = self.__project.scontext.sid_for(i.p1_layer)

        return _aw

    def deserialize(self, msg):
        for i in msg.vias:
            v = Via(deserialize_point2(i.point),
                    self.__project.scontext.get(i.viapairSid),
                    i.r,
                    self.__project.scontext.get(i.netSid)
            )

            self.add_artwork(v)

        for i in msg.traces:
            t = Trace(
                deserialize_point2(i.p0),
                deserialize_point2(i.p1),
                i.thickness,
                self.__project.scontext.get(i.layerSid),
                self.__project.scontext.get(i.netSid)
            )

            self.add_artwork(t)

        for i in msg.polygons:
            exterior = [deserialize_point2(j) for j in i.exterior]
            interiors = [[deserialize_point2(k) for k in j] for j in i.interiors]

            p = Polygon(
                self.__project.scontext.get(i.layerSid),
                exterior,
                interiors,
                self.__project.scontext.get(i.netSid)
            )

            self.add_artwork(p)

        for i in msg.airwires:
            aw = Airwire(
                deserialize_point2(i.p0),
                deserialize_point2(i.p1),
                self.__project.scontext.get(i.p0LayerSid),
                self.__project.scontext.get(i.p1LayerSid),
                self.__project.scontext.get(i.netSid)
            )
            self.add_artwork(aw)

        for i in msg.components:
            if i.which() == "dip":
                cmp = DIPComponent.deserialize(self.__project, i)
            elif i.which() == "smd4":
                cmp = SMD4Component.deserialize(self.__project, i)
            else:
                raise NotImplementedError()

            self.add_component(cmp)
