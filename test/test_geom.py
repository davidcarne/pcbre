from pcbre.matrix import Point2
from pcbre.model.net import Net
from pcbre.model.project import Project
from pcbre.model.stackup import Layer, ViaPair

__author__ = 'davidc'

from pcbre.algo.geom import *
import unittest


class test_geom(unittest.TestCase):
    def test_via_via(self):
        class FakeVP():
            @property
            def all_layers(self):
                return [1]

        vp = FakeVP()
        v = Via(Point2(7,13), vp, 3, None)
        v1 = Via(Point2(-5, 6), vp, 7, None)

        self.assertAlmostEqual((12 ** 2 + 7 ** 2)**0.5 - 10, dist_via_via(v, v1))

    def test_trace_trace_par(self):
        t1 = Trace(Point2(7,7), Point2(15, 7), 3, None, None)
        t2 = Trace(Point2(1,12), Point2(32, 12), 4, None, None)
        self.assertAlmostEqual(dist_trace_trace(t1, t2), 1.5)

    def test_trace_trace_off_end(self):
        t1 = Trace(Point2(7,7), Point2(32, 7), 3, None, None)
        t2 = Trace(Point2(36, 13), Point2(36, 0), 3, None, None)
        self.assertGreater(dist_trace_trace(t1, t2), 0)

class test_aw_queries(unittest.TestCase):
    def setUp(self):
        world = Project()

        for i in range(4):
            world.stackup.add_layer(Layer("l%d" % i, None))

        world.stackup.add_via_pair(ViaPair(world.stackup.layers[0], world.stackup.layers[1]))
        world.stackup.add_via_pair(ViaPair(world.stackup.layers[2], world.stackup.layers[3]))
        world.stackup.add_via_pair(ViaPair(world.stackup.layers[0], world.stackup.layers[3]))
        world.stackup.add_via_pair(ViaPair(world.stackup.layers[1], world.stackup.layers[2]))

        #   0 1 2 3
        # 0 x   x x
        # 1   x x x
        # 2 x x x x
        # 3 x x x x

        n1 = Net()
        n2 = Net()
        world.nets.add_net(n1)
        world.nets.add_net(n2)
        self.v1 = Via(Point2(3,3),  world.stackup.via_pairs[0], 2, n1)
        world.artwork.add_artwork(self.v1)
        self.v2 = Via(Point2(11,11), world.stackup.via_pairs[1], 2, n2)
        world.artwork.add_artwork(self.v2)
        self.world = world


    def test_via_query_intersect_miss_distance(self):
        v = Via(Point2(7,7), self.world.stackup.via_pairs[2], 1, None)
        self.assertEqual(len(self.world.artwork.query_intersect(v)), 0)

    def test_via_query_intersect_pass_distance(self):
        # Inclusive viapair
        v = Via(Point2(7,7), self.world.stackup.via_pairs[2], 4, None)
        self.assertEqual(len(self.world.artwork.query_intersect(v)), 2)

        # Overlapping
        v = Via(Point2(7,7), self.world.stackup.via_pairs[3], 4, None)
        self.assertEqual(len(self.world.artwork.query_intersect(v)), 2)

        # Only one via should overlap
        v = Via(Point2(7,7), self.world.stackup.via_pairs[0], 4, None)
        self.assertEqual(len(self.world.artwork.query_intersect(v)), 1)

    def test_trace_intersect(self):
        t = Trace(Point2(3,3), Point2(11,11), 1, self.world.stackup.layers[0], None)
        qr = self.world.artwork.query_intersect(t)
        self.assertEqual(len(qr), 1)

    def test_connected_island_un(self):
        connected = self.world.artwork.compute_connected(self.world.artwork.get_all_artwork())
        self.assertEqual(len(connected), 2)
        for i in connected:
            self.assertEqual(len(i), 1)

    def test_via_trace_intersect(self):
        t = Trace(Point2(3,3), Point2(11,11), 3, self.world.stackup.layers[0])
        self.assertLessEqual(distance(t, self.v1), 0)
        self.assertGreater(distance(t, self.v2), 0)

    def test_connected_island(self):
        self.world.artwork.merge_artwork(Trace(Point2(3,3), Point2(11,11), 3, self.world.stackup.layers[0]))
        connected = self.world.artwork.compute_connected(self.world.artwork.get_all_artwork())
        self.assertEqual(len(connected), 2)


class test_sequence(unittest.TestCase):
    def test_point_insert(self):
        p = Project()
        l1 = Layer("l1", None)
        l2 = Layer("l2", None)
        p.stackup.add_layer(l1)
        p.stackup.add_layer(l2)
        vp = ViaPair(l1, l2)
        p.stackup.add_via_pair(vp)

        t1 = Trace(Point2(200,1000), Point2(2000, 1000), 10, l1)
        p.artwork.merge_artwork(t1)

        t2 = Trace(Point2(400, 0), Point2(400, 2000), 10, l2)
        p.artwork.merge_artwork(t2)

        # Should be two objects, not connected
        self.assertIsNotNone(t1.net)
        self.assertIsNotNone(t2.net)
        self.assertNotEqual(t1.net, t2.net)

        # Add two more traces, make sure they're connected to nets
        t3 = Trace(Point2(2000,1001), Point2(2000, 3000), 10, l1)
        p.artwork.merge_artwork(t3)
        self.assertEqual(t1.net, t3.net)

        t4 = Trace(Point2(401, -1), Point2(-1000, -1000), 10, l2)
        p.artwork.merge_artwork(t4)
        self.assertEqual(t2.net, t4.net)

        # Now put a via between the two
        v = Via(Point2(400, 1000), vp, 10)
        p.artwork.merge_artwork(v)
        # Make sure net is not none
        self.assertIsNotNone(v.net)

        # Make sure net is all the same
        self.assertEqual(v.net, t1.net)
        self.assertEqual(v.net, t2.net)
        self.assertEqual(v.net, t3.net)
        self.assertEqual(v.net, t4.net)

        # Should only be one net in the project now, and it should be v.net
        self.assertEqual(len(p.nets.nets), 1)
        self.assertEqual(p.nets.nets[0], v.net)

        # Ok, now remove the via from the artwork.
        # via should then have no net, and the traces on each layer should split off
        p.artwork.remove_artwork(v)

        # We should now have two nets on separate layers
        self.assertEqual(len(p.nets.nets), 2)
        self.assertEqual(t1.net, t3.net)
        self.assertEqual(t2.net, t4.net)
        self.assertNotEqual(t1.net, t2.net)





