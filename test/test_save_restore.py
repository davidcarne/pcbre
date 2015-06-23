import numpy
from tempfile import TemporaryFile
from pcbre.matrix import Point2
from pcbre.model.artwork import Via
from pcbre.model.artwork_geom import Trace, Via, Polygon, Airwire
from pcbre.model.imagelayer import ImageLayer, KeyPoint, KeyPointAlignment, RectAlignment
from pcbre.model.net import Net
from pcbre.model.project import Project
from pcbre.model.serialization import serialize_matrix, deserialize_matrix, serialize_point2, \
    deserialize_point2, serialize_point2f, deserialize_point2f
from pcbre.model.stackup import Layer, ViaPair
import random
__author__ = 'davidc'


import unittest

class test_save_restore(unittest.TestCase):
    def __saverestore(self, p):
        with TemporaryFile(buffering=0) as fd:

            p.save_fd(fd)
            fd.seek(0)

            p_new = Project.open_fd(fd)
        return p_new

    def test_basic_save_restore(self):
        p = Project.create()
        p_new = self.__saverestore(p)

    def compare_tuple(self, a, b):
        self.assertEqual(len(a), len(b))
        for i, j in zip(a, b):
            self.assertAlmostEqual(i, j)

    def __setup_layers(self, n):
        names = ["foo","bar","quux", "sed","a"] + list("abcdefghijklmnop")
        p = Project.create()
        for i, name in zip(range(n), names):
            color = (random.random(), random.random(), random.random())
            l0 = Layer(name, color)
            p.stackup.add_layer(l0)

        return p

    def check_obj(self, new_p, new_o, old_o):
        self.assertTrue(new_o is not old_o)
        self.assertEqual(new_o._project, new_p)

    def test_layer_save_restore(self):
        p = self.__setup_layers(2)

        p_new = self.__saverestore(p)

        self.assertEqual(len(p_new.stackup.layers), len(p.stackup.layers))

        for l_old, l_new in zip(p.stackup.layers, p_new.stackup.layers):
            self.check_obj(p_new, l_new, l_old)
            self.assertEqual(l_new.name, l_old.name)
            self.compare_tuple(l_new.color, l_old.color)

    def __setup_via_pairs_layers(self):
        p = self.__setup_layers(4)

        l0, l1, l2, l3 = p.stackup.layers

        vp1 = ViaPair(l0, l3)
        vp2 = ViaPair(l1, l2)

        p.stackup.add_via_pair(vp1)
        p.stackup.add_via_pair(vp2)

        return p

    def test_via_pairs(self):
        p = self.__setup_via_pairs_layers()

        p_new = self.__saverestore(p)

        self.assertEqual(len(p.stackup.via_pairs), len(p_new.stackup.via_pairs))
        for vp_old, vp_new in zip(p.stackup.via_pairs, p_new.stackup.via_pairs):
            self.check_obj(p_new, vp_new, vp_old)

            new_first_i, new_second_i = [p_new.stackup.layers.index(i) for i in vp_new.layers]
            old_first_i, old_second_i = [p.stackup.layers.index(i) for i in vp_old.layers]

            self.assertEqual(new_first_i, old_first_i)
            self.assertEqual(new_second_i, old_second_i)


    def setup_i3(self):
        p = self.__setup_via_pairs_layers()
        il1 = ImageLayer("foo", bytes(b"12344"))
        il2 = ImageLayer("bar", bytes(b"12345"))
        il3 = ImageLayer("quux", bytes(b"12346"))
        p.imagery.add_imagelayer(il1)
        p.imagery.add_imagelayer(il2)
        p.imagery.add_imagelayer(il3)
        p.stackup.layers[0].imagelayers = [il1, il2]
        p.stackup.layers[1].imagelayers = [il3]
        return p

    def test_image_layers(self):
        p = self.setup_i3()
        p_new = self.__saverestore(p)

        self.assertEqual(len(p.imagery.imagelayers), len(p_new.imagery.imagelayers))
        for il_old, il_new in zip(p.imagery.imagelayers, p_new.imagery.imagelayers):
            self.check_obj(p_new, il_new, il_old)
            self.assertEqual(il_new.data, il_old.data)
            self.assertEqual(il_new.name, il_old.name)

        self.assertListEqual(p.stackup.layers[0].imagelayers, p.imagery.imagelayers[:2])
        self.assertListEqual(p.stackup.layers[1].imagelayers, p.imagery.imagelayers[2:])

    def cmpMat(self, a, b):
        eps = numpy.absolute(b-a).max()
        self.assertLess(eps, 0.00001, "CmpMat: %s %s" % (a, b))

    def test_keypoints(self):
        p = self.setup_i3()
        kp1 = KeyPoint(Point2(3,6))
        kp2 = KeyPoint(Point2(5,5))
        p.imagery.add_keypoint(kp1)
        p.imagery.add_keypoint(kp2)

        align = KeyPointAlignment()
        p.imagery.imagelayers[0].set_alignment(align)

        align.set_keypoint_position(kp1, Point2(-7,13))
        align.set_keypoint_position(kp2, Point2(4, 5))

        p_new = self.__saverestore(p)

        # Verify Keypoints saved/restored
        self.assertEqual(len(p_new.imagery.keypoints), len(p.imagery.keypoints))
        for kp_old, kp_new in zip(p.imagery.keypoints, p_new.imagery.keypoints):
            self.check_obj(p_new, kp_new, kp_old)

            self.cmpMat(kp_new.world_position, kp_old.world_position)

        # Verify object align makes it through
        il_0_new = p_new.imagery.imagelayers[0]
        self.assertIsInstance(il_0_new.alignment, KeyPointAlignment)
        al = il_0_new.alignment

        new_kpl = sorted(al.keypoint_positions, key=lambda x: x.key_point.world_position.x)
        old_kpl = sorted(align.keypoint_positions, key=lambda x: x.key_point.world_position.x)

        self.cmpMat(new_kpl[0].image_pos, old_kpl[0].image_pos)
        self.cmpMat(new_kpl[1].image_pos, old_kpl[1].image_pos)

    def test_rectalign(self):
        p = self.setup_i3()
        align = RectAlignment(
            [Point2(3,3), Point2(7,3), Point2(7,7), Point2(3, 7), None, None, None, None, Point2(4, 7), None, None, None],
            [Point2(5,6), Point2(7,8), Point2(1, 3), Point2(2,3)],
            (5.77, 3.135),
            False,
            Point2(47, 56),
            1,
            True,
            False)
        p.imagery.imagelayers[0].set_alignment(align)

        p_new = self.__saverestore(p)

        new_align = p_new.imagery.imagelayers[0].alignment
        """:type : RectAlignment"""

        self.assertEqual(len(align.handles), len(new_align.handles))
        self.assertEqual(len(align.dim_handles), len(new_align.dim_handles))
        self.assertEqual(align.dims_locked, new_align.dims_locked)
        self.assertEqual(align.origin_corner, new_align.origin_corner)
        self.cmpMat(align.origin_center, new_align.origin_center)
        self.assertEqual(align.flip_x, new_align.flip_x)
        self.assertEqual(align.flip_y, new_align.flip_y)

        for a,b in zip(align.handles, new_align.handles):
            if a is None:
                self.assertIsNone(b)
            else:
                self.assertIsNotNone(b)
                self.cmpMat(a,b)

        for a,b in zip(align.dim_handles, new_align.dim_handles):
            if a is None:
                self.assertIsNone(b)
            else:
                self.assertIsNotNone(b)
                self.cmpMat(a,b)

    def test_vias(self):
        p = self.__setup_via_pairs_layers()

        n1 = Net()
        p.nets.add_net(n1)

        n2 = Net()
        p.nets.add_net(n2)

        v = Via(Point2(3700, 2100), p.stackup.via_pairs[0], 31337, n1)
        v2 = Via(Point2(1234, 5678), p.stackup.via_pairs[1], 31339, n2)

        p.artwork.add_artwork(v)
        p.artwork.add_artwork(v2)

        p_new = self.__saverestore(p)

        v2_new = sorted(p_new.artwork.vias, key=lambda x: x.pt.x)[0]
        v_new = sorted(p_new.artwork.vias, key=lambda x: x.pt.x)[1]
        self.assertEqual(v_new._project, p_new)
        self.assertEqual(v2_new._project, p_new)

        for a, b in ((v, v_new), (v2, v2_new)):
            self.cmpMat(a.pt, b.pt)
            self.assertEqual(p.stackup.via_pairs.index(a.viapair),
                             p_new.stackup.via_pairs.index(b.viapair))
            self.assertEqual(a.r, b.r)
            self.assertEqual(p.nets.nets.index(a.net), p_new.nets.nets.index(b.net))

    def test_airwires(self):
        p = self.__setup_via_pairs_layers()

        n1 = Net()
        p.nets.add_net(n1)

        v = Via(Point2(3700, 2100), p.stackup.via_pairs[0], 31337, n1)
        v2 = Via(Point2(1234, 5678), p.stackup.via_pairs[1], 31339, n1)

        airwire = Airwire(v.pt, v2.pt, v.viapair.layers[0], v2.viapair.layers[0], n1)

        p.artwork.add_artwork(v)
        p.artwork.add_artwork(v2)
        p.artwork.add_artwork(airwire)

        p_new = self.__saverestore(p)

        aw_new = list(p_new.artwork.airwires)[0]

        v2_new = sorted(p_new.artwork.vias, key=lambda x: x.pt.x)[0]
        v_new = sorted(p_new.artwork.vias, key=lambda x: x.pt.x)[1]

        self.cmpMat(aw_new.p0, airwire.p0)
        self.cmpMat(aw_new.p1, airwire.p1)

        self.assertEqual(aw_new.p0_layer, v_new.viapair.layers[0])
        self.assertEqual(aw_new.p1_layer, v2_new.viapair.layers[0])
        self.assertEqual(aw_new.net, v_new.net)

    def test_polyons(self):
        p = self.__setup_via_pairs_layers()
        n1 = Net()
        p.nets.add_net(n1)
        n2 = Net()
        p.nets.add_net(n2)

        ext = [Point2(0,0), Point2(10,0), Point2(10,10), Point2(0, 10)]
        int1 = [Point2(1,1), Point2(2,1), Point2(2,2), Point2(1,2)]
        int2 = [Point2(4,1), Point2(5,1), Point2(5,2), Point2(4,2)]


        po = Polygon(p.stackup.layers[0], ext, [int1, int2], n1)

        p.artwork.add_artwork(po)

        p_new = self.__saverestore(p)

        pols = p_new.artwork.polygons

        self.assertEqual(len(pols), 1)
        pol_new = list(pols)[0]
        self.assertIsInstance(pol_new, Polygon)

        r = pol_new.get_poly_repr()

        # All LineRings contain the first element as the last, so we drop during the comparison

        pb = po.get_poly_repr()
        self.assertListEqual(list(r.exterior.coords), [tuple(i) for i in pb.exterior.coords])
        interiors = r.interiors
        self.assertEqual(len(interiors), 2)
        self.assertListEqual(list(interiors[0].coords), [tuple(i) for i in pb.interiors[0].coords])
        self.assertListEqual(list(interiors[1].coords), [tuple(i) for i in pb.interiors[1].coords])

        self.assertIsNotNone(pol_new.net)
        self.assertIsNotNone(pol_new.layer)

    def test_trace(self):
        p = self.__setup_via_pairs_layers()

        n1 = Net()
        p.nets.add_net(n1)

        n2 = Net()
        p.nets.add_net(n2)

        t1 = Trace(Point2(61, -300), Point2(848, 1300), 775, p.stackup.layers[0], n1)
        t2 = Trace(Point2(1234, 5678), Point2(90210, 84863), 775, p.stackup.layers[0], n2)

        p.artwork.add_artwork(t1)
        p.artwork.add_artwork(t2)

        self.assertEqual(t1._project, p)

        p_new = self.__saverestore(p)

        self.assertEqual(len(p_new.artwork.traces), 2)
        self.assertIs(list(p_new.artwork.traces)[0]._project, p_new)

        # Walk ordered traces
        l_old = sorted(p.artwork.traces, key=lambda x: x.p0.x)
        l_new = sorted(p_new.artwork.traces, key=lambda x: x.p0.x)
        for t_old, t_new in zip(l_old, l_new):
            self.cmpMat(t_old.p0, t_new.p0)
            self.cmpMat(t_old.p1, t_new.p1)
            self.assertEqual(t_old.thickness, t_new.thickness)

            # Check links to layer object and net object are restored
            self.assertEqual(p.nets.nets.index(t_old.net), p_new.nets.nets.index(t_new.net))
            self.assertEqual(p.stackup.layers.index(t_old.layer),
                             p_new.stackup.layers.index(t_new.layer))

class test_save_mats(unittest.TestCase):
    def __test_shape(self, n):

        mat = numpy.random.rand(n,n)

        msg = serialize_matrix(mat)

        mat2 = deserialize_matrix(msg)

        eps = numpy.absolute(mat2 - mat).max()
        self.assertLess(eps, 0.00001)

    def test_mat_3_3(self):
        self.__test_shape(3)

    def test_mat_4_4(self):
        self.__test_shape(4)

class test_save_point2(unittest.TestCase):
    def test_point2(self):
        # Point2 class is floating (for now), but serialized form is integral units
        pt = Point2(54.3, 72.9)
        msg = serialize_point2(pt)

        pt2 = deserialize_point2(msg)

        self.assertAlmostEqual(pt2.x, round(pt.x))
        self.assertAlmostEqual(pt2.y, round(pt.y))

    def test_point2f(self):
        pt = Point2(54.3, 72.9)
        msg = serialize_point2f(pt)

        pt2 = deserialize_point2f(msg)

        self.assertAlmostEqual(pt2.x, pt.x)
        self.assertAlmostEqual(pt2.y, pt.y)
