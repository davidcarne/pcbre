import math
from pcbre.matrix import Point2
from pcbre.model.artwork_geom import Trace
from pcbre.model.net import Net
from pcbre.model.project import Project
from pcbre.model.stackup import Layer

__author__ = 'davidc'
import unittest

class test_regressions(unittest.TestCase):
    def test_sorted_query_regression(self):
        # Attempt to
        p = Project()

        l = Layer(p, "t1", (1,1,1))

        p.stackup.add_layer(l)

        cx = Point2(30000, 30000)
        ts = []
        for i in range(100):
            r = 5000 - 40 * i
            r1 = 5000 - 40 * (i+1)

            t = math.radians(30 * i)
            t1 = math.radians(30 * (i+1))

            v = Point2(math.cos(t) * r, math.sin(t) * r)
            v1 = Point2(math.cos(t1) * r1, math.sin(t1) * r1)

            t1 = Trace(v + cx, v1 + cx, 100, l)
            t1.STUFFED_ID = i
            p.artwork.merge_artwork(t1)
            ts.append(t1)

        t0 = ts[0]
        for n, a in enumerate(ts[1:], start=1):
            self.assertEqual(t0.net, a.net, "mismatch on %d" % n)

        self.assertIsNotNone(t0.net)

    def test_fixup_broken_nets(self):
        p = Project()

        l = Layer(p, "t1", (1,1,1))

        p.stackup.add_layer(l)

        n1 = p.nets.new()
        n2 = p.nets.new()
        n3 = p.nets.new()


        # T1 and T2 should be joined
        # T2 and T3 should be split
        # T4 should stay the same

        t1 = Trace(Point2(0,0), Point2(100, 100), 10, l, n1)
        t2 = Trace(Point2(200, 200), Point2(100, 100), 10, l, n2)
        t3 = Trace(Point2(400, 400), Point2(500, 500), 10, l, n2)
        t4 = Trace(Point2(600, 600), Point2(700, 700), 10, l, n3)


        p.artwork.add_artwork(t1)
        p.artwork.add_artwork(t2)
        p.artwork.add_artwork(t3)
        p.artwork.add_artwork(t4)

        self.assertNotEqual(t1.net, t2.net)
        p.artwork.rebuild_connectivity()
        self.assertEqual(t1.net, t2.net)
        self.assertNotEqual(t2.net, t3.net)
        self.assertEqual(t4.net, n3)

        # And all objects must have nets
        self.assertIsNotNone(t1.net)
        self.assertIsNotNone(t2.net)
        self.assertIsNotNone(t3.net)
        self.assertIsNotNone(t4.net)

