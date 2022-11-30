import itertools
import operator
import weakref
from collections import defaultdict
from typing import Dict, Any, Callable, List, Tuple, Iterable, Union, Sequence, Optional, Set, Generator

from rtree import index  # type: ignore

import pcbre.model.project
from pcbre.algo.geom import dist_via_via, dist_via_trace, dist_trace_trace, \
    dist_via_pad, dist_trace_pad, dist_pad_pad, distance, point_inside, can_self_intersect, intersect
from pcbre.matrix import Point2
from pcbre.matrix import Rect
from pcbre.model.artwork_geom import Trace, Via, Polygon, Airwire, Geom
from pcbre.model.component import Component
from pcbre.model.const import IntersectionClass
from pcbre.model.net import Net
from pcbre.model.pad import Pad
from pcbre.model.util import ImmutableSetProxy

QueryableGeom = Union[Via, Trace, Pad, Polygon, Airwire]
InsertableGeom = Union[Via, Trace, Polygon, Airwire]
ArtworkComponent = Union[QueryableGeom, Component]
InsertableGeomComponent = Union[InsertableGeom, Component]
ArtworkComponentPad = Union[ArtworkComponent, Pad]
GeomPad = Union[Geom, Pad]


#   Once an item is added to artwork, it should be considered geometrically and electrically immutable
#
#   changing an object in a way that alters the geometry or connectivity requires removing it before
#   applying the changes, then reading it. This of course can be hidden in the UI.
#
#   The point of this step is to ensure that net connectivity is recalculated as necessary
class ArtworkIndex:
    """
    Artwork index provides a wrapper on the Rtree spatial query library. Specifically, it resolves query results to
    physical geom objects, as well as uses the "fast" query paths
    """

    def __init__(self) -> None:
        self.__index = index.Index()
        self.__idx = 0

        self.__obj_to_idx: weakref.WeakKeyDictionary[Any, int] = \
            weakref.WeakKeyDictionary()
        self.__idx_to_obj: weakref.WeakValueDictionary[int, Any] = \
            weakref.WeakValueDictionary()

    def __get_idx(self, k: Any) -> int:
        try:
            return self.__obj_to_idx[k]
        except KeyError:
            r = self.__obj_to_idx[k] = self.__idx
            self.__idx_to_obj[r] = k
            self.__idx += 1
            return r

    def __get_obj(self, idx: int) -> Any:
        try:
            return self.__idx_to_obj[idx]
        except KeyError:
            raise

    @staticmethod
    def __rect_index_order(rect: Rect) -> Tuple[float, float, float, float]:
        return rect.left, rect.bottom, rect.right, rect.top

    def insert(self, geom: Any) -> None:
        self.__index.insert(self.__get_idx(geom), self.__rect_index_order(geom.bbox))

    def intersect(self, bbox: Rect) -> Iterable[Any]:
        idxs = self.__index.intersection(self.__rect_index_order(bbox))
        return (self.__get_obj(idx) for idx in idxs)

    def nearest(self, bbox: Rect) -> Iterable[Any]:
        idxs = self.__index.nearest(self.__rect_index_order(bbox))
        return (self.__get_obj(idx) for idx in idxs)

    def remove(self, geom: Any) -> None:
        idx = self.__obj_to_idx[geom]
        del self.__obj_to_idx[geom]
        del self.__idx_to_obj[idx]

        self.__index.delete(idx, self.__rect_index_order(geom.bbox))


class Artwork:
    def __init__(self, project: 'pcbre.model.project.Project') -> None:
        self._project = project
        self.__index = ArtworkIndex()

        self.__vias: Set[Via] = set()
        self.__airwires: Set[Airwire] = set()
        self.__traces: Set[Trace] = set()
        self.__polygons: Set[Polygon] = set()
        self.__components: Set[Component] = set()

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

    def add_artwork(self, aw: InsertableGeom) -> None:
        """
        Add any single-net piece of geometry to the board artwork
        :param aw:
        :return:
        """
        assert aw is not None
        assert aw._project is None
        assert aw.net is not None
        assert aw.net._project is self._project

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

        aw._project = self._project

    def add_component(self, cmp: Component) -> None:
        """
        :param cmp:
        :return:
        """
        self.__components.add(cmp)
        cmp._project = self._project

        self.__index.insert(cmp)
        for pad in cmp.get_pads():
            self.__index.insert(pad)

        self.components_generation += 1

    def merge_component(self, cmp: Component) -> None:
        """
        :return:
        """

        for pad in cmp.get_pads():
            self.merge_aw_nets(pad)

        self.add_component(cmp)

    def remove_component(self, cmp: Component) -> None:
        for pad in cmp.get_pads():
            self.remove_aw_nets(pad, suppress_presence_error=False)
            self.__index.remove(pad)

        self.__index.remove(cmp)
        self.__components.remove(cmp)

        self.components_generation += 1

    def remove_artwork(self, aw: InsertableGeom) -> None:
        assert aw._project is self._project
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
            self._project.nets.remove_net(aw_net)

        aw._project = None

    def remove(self, aw: InsertableGeomComponent) -> None:
        if isinstance(aw, Component):
            self.remove_component(aw)
        else:
            self.remove_artwork(aw)

    def merge(self, aw: InsertableGeomComponent) -> None:
        if isinstance(aw, Component):
            self.merge_component(aw)
        else:
            self.merge_artwork(aw)

    @property
    def __all_pads(self) -> Iterable[Pad]:
        for c in self.components:
            yield from c.get_pads()

    def get_all_artwork(self) -> Iterable[GeomPad]:
        def gen() -> Iterable[GeomPad]:
            yield from self.__vias
            yield from self.__airwires
            yield from self.__traces
            yield from self.__polygons
            yield from self.__all_pads

        return gen()

    def get_geom_for_net(self, net: Net) -> Sequence[GeomPad]:
        return [i for i in self.get_all_artwork() if i.net is net]

    def merge_nets(self, net1: Net, net2: Net) -> None:
        """
        Merge two nets, such that all artwork on net2 is now on net1, and net2 is deleted

        :param net1: destination Net object
        :param net2: source Net object
        :return: None
        """
        for aw in self.get_all_artwork():
            if aw.net == net2:
                aw.net = net1

        self._project.nets.remove_net(net2)

    def merge_nets_many(self, nets: Iterable[Net]) -> Net:
        queue = list(nets)
        acc = queue.pop()

        while queue:
            n = queue.pop()
            self.merge_nets(acc, n)

        return acc

    def query_point(self, pt: Point2) -> Union[Geom, Pad, Component, None]:
        """
        Queries a single point to identify geometry at that location
        """

        for aw in self.get_all_artwork():
            if point_inside(aw, pt):
                return aw

        for cmp in self.components:
            if cmp.point_inside(pt):
                return cmp

        return None

    def query_point_multiple(self, pt: Point2) -> Sequence[Union[Geom, Pad, Component]]:
        """
        Queries a single point to identify geometry at that location
        """

        found_aw = []

        for aw in self.get_all_artwork():
            if point_inside(aw, pt):
                found_aw.append(aw)

        for cmp in self.components:
            if cmp.point_inside(pt):
                found_aw.append(cmp)

        return found_aw

    def merge_aw_nets(self, new_geom: QueryableGeom) -> None:
        """
        Perform net merges that would occur if new_geom is added to the project
        :param new_geom:
        :return:
        """
        qr = self.query_intersect(new_geom)

        nets = set()
        if new_geom.net is not None:
            nets.add(new_geom.net)

        for _, geom in qr:
            net = geom.net
            # When added to a project, the net should never be Null
            assert net is not None
            nets.add(net)

        if len(nets) > 1:
            new_net = self.merge_nets_many(nets)
        elif len(nets) == 1:
            new_net = list(nets)[0]
        else:
            new_net = Net()
            self._project.nets.add_net(new_net)

        new_geom.net = new_net

    def remove_aw_nets(self, geom: QueryableGeom, suppress_presence_error: bool = False) -> None:
        """
        Perform any net-splitting that would occur if geom is removed from the project
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

        def net_gen() -> Generator[Optional[Net], None, None]:
            yield geom.net

            newnet = Net()
            self._project.nets.add_net(newnet)
            yield newnet

        for group, net in zip(subgroups, net_gen()):
            for g_ in group:
                g_.net = net

        geom.net = None

    def compute_connected(
            self, all_geom: Iterable[Geom],
            progress_cb: Callable[[int, int], None] = lambda x, y: None) -> List[Set[Geom]]:

        qh = set(all_geom)
        labno = 0
        # TODO: refine these types
        geom_to_label: Dict[Geom, int] = dict()
        label_to_geom: Dict[int, Set[Geom]] = defaultdict(set)
        seen: Set[Any] = set()

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
            if label is None:
                geom_to_label[k] = labno
                label_to_geom[labno].add(k)
                labno += 1

        return list(label_to_geom.values())

    def rebuild_connectivity(self, progress_cb: Callable[[int, int], None] = lambda x, y: None) -> None:
        connectivity = self.compute_connected(self.get_all_artwork(), progress_cb=progress_cb)

        # First, for each existing net, we identify which groups are owned by the net
        # and remove the groups having the smaller amounts of geometry (by count)
        nets_to_groups: Dict[Net, List[Set[Geom]]] = defaultdict(list)
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
                n0 = self._project.nets.new()
            else:
                n0 = nets.pop()

            for i in group:
                i.net = n0

        assigned_nets = set(i.net for i in self.get_all_artwork())

        existing_nets = set(self._project.nets.nets)

        to_remove_nets = existing_nets - assigned_nets

        for net in to_remove_nets:
            self._project.nets.remove_net(net)

    def merge_artwork(self, geom: InsertableGeom) -> None:
        """
        Merge a geometry object into the design. Takes care of either assigning object a net, or merging nets if necessary
        :param geom:
        :rtype: bool
        :return: Whether the geometry may be merged
        """

        assert geom._project is None

        self.merge_aw_nets(geom)
        self.add_artwork(geom)

    def query_intersect(self, geom: QueryableGeom) -> List[Tuple[float, GeomPad]]:
        qr = self.query(geom, bbox_prune=True)
        return list(itertools.takewhile(lambda a: a[0] <= 0, qr))

    def intersect_with(self, a: Geom, b: Set[QueryableGeom]) -> Iterable[QueryableGeom]:
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
    def query(self, geom: QueryableGeom, bbox_prune: bool = False) -> List[Tuple[float, Geom]]:
        """

        :param geom:  object to query
        :return: list of artwork objects
        """
        assert bbox_prune

        if bbox_prune:
            ilist = self.__index.intersect(geom.bbox)
            ilist = [i for i in ilist if i.ISC != IntersectionClass.NONE]

            return sorted([(distance(geom, other), other) for other in ilist], key=operator.itemgetter(0))

        bbox = geom.bbox

        # TODO refine geom type
        results: List[Tuple[float, Any]] = []
        if isinstance(geom, Via):
            # Build structures used to determine if artwork is on same layer
            vps_ok = {}
            my_layerset = set(id(i) for i in geom.viapair.all_layers)

            for v in self._project.stackup.via_pairs:
                v_layerset = set(id(i) for i in v.all_layers)
                vps_ok[id(v)] = len(v_layerset.intersection(my_layerset))

            for other_via in self.__vias:
                if not vps_ok[id(other_via.viapair)]:
                    continue

                if bbox_prune and not bbox.intersects(other_via.bbox):
                    continue

                results.append((
                    dist_via_via(geom, other_via),
                    other_via
                ))

            for other_trace in self.__traces:
                if id(other_trace.layer) not in my_layerset:
                    continue

                if bbox_prune and not bbox.intersects(other_trace.bbox):
                    continue

                results.append((
                    dist_via_trace(geom, other_trace),
                    other_trace
                ))

            for other_pad in self.__all_pads:
                if other_pad.is_through() or other_pad.layer in geom.viapair.all_layers:

                    if bbox_prune and not bbox.intersects(other_pad.bbox):
                        continue
                    results.append((
                        dist_via_pad(geom, other_pad),
                        other_pad
                    ))

        elif isinstance(geom, Trace):
            for other_trace in self.__traces:
                if other_trace.layer is not geom.layer:
                    continue

                if bbox_prune and not bbox.intersects(other_trace.bbox):
                    continue
                results.append((
                    dist_trace_trace(geom, other_trace),
                    other_trace
                ))

            # Build lookup to check viapair
            vps_ok = {}
            for v in self._project.stackup.via_pairs:
                v_layerset = set(id(i) for i in v.all_layers)
                vps_ok[id(v)] = id(geom.layer) in v_layerset

            for other_via in self.__vias:
                if not vps_ok[id(other_via.viapair)]:
                    continue

                if bbox_prune and not bbox.intersects(other_via.bbox):
                    continue

                results.append((
                    dist_via_trace(other_via, geom),
                    other_via
                ))

            for other_pad in self.__all_pads:
                if bbox_prune and not bbox.intersects(other_pad.bbox):
                    continue

                results.append((
                    dist_trace_pad(geom, other_pad),
                    other_pad
                ))

        elif isinstance(geom, Pad):
            # TODO: More opts here, can exclude some pads based on TH
            for other_via in self.__vias:
                if bbox_prune and not bbox.intersects(other_via.bbox):
                    continue

                results.append((
                    dist_via_pad(other_via, geom),
                    other_via
                ))

            for other_trace in self.__traces:
                if bbox_prune and not bbox.intersects(other_trace.bbox):
                    continue

                results.append((
                    dist_trace_pad(other_trace, geom),
                    other_trace
                ))

            for cmp in self.__components:
                if bbox_prune and not bbox.intersects(cmp.bbox):
                    continue

                for other_pad in cmp.get_pads():
                    if bbox_prune and not bbox.intersects(other_pad.bbox):
                        continue
                    results.append((
                        dist_pad_pad(geom, other_pad),
                        other_pad
                    ))

        else:
            raise NotImplementedError()

        return sorted(results, key=operator.itemgetter(0))

