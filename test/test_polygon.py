from pcbre.algo.geom import distance
from pcbre.matrix import Point2
from pcbre.model.artwork_geom import Polygon
from pcbre.model.project import Project
from pcbre.model.stackup import Layer

__author__ = 'davidc'

import unittest

class test_polygon_basic_intersect(unittest.TestCase):
    def setUp(self):
        self.p = Project()

        self.l1 = self.p.stackup.add_layer("l1", (1, 0, 0))
        self.l2 = self.p.stackup.add_layer("l2", (0, 0, 1))

        self.ext1 = [Point2(0, 0), Point2(1, 0), Point2(1, 1), Point2(0, 1)]
        self.ext2 = [Point2(1, 0), Point2(2, 0), Point2(2, 1), Point2(1, 1)]
        self.ext3 = [Point2(2, 0), Point2(3, 0), Point2(3, 1), Point2(2, 1)]

    def test_intersect(self):
        p = Polygon(self.l1, self.ext1, [])
        p2 = Polygon(self.l1, self.ext2, [])
        p3 = Polygon(self.l1, self.ext3, [])

        d = distance(p, p2)
        self.assertLessEqual(d, 0)

        d = distance(p2, p3)
        self.assertLessEqual(d, 0)

        d1 = distance(p, p3)
        self.assertGreater(d1, 0)

    def test_separate_layers(self):
        p = Polygon(self.l1, self.ext1, [])
        p2 = Polygon(self.l2, self.ext2, [])

        self.assertGreater(distance(p, p2), 0)

    def test_inner_ring(self):
        ext = [Point2(0,0), Point2(10, 0), Point2(10, 10), Point2(0, 10)]
        inner = [Point2(3,3), Point2(7, 3), Point2(7, 7), Point2(3, 7)]

        inner2 = [Point2(4,4), Point2(6, 4), Point2(6, 6), Point2(4, 6)]

        outer_ring = Polygon(self.l1, ext, [inner])
        inner_ring = Polygon(self.l1, inner2, [])

        self.assertAlmostEqual(distance(outer_ring, inner_ring), 1)

        outer_ring.get_tris_repr()
        inner_ring.get_tris_repr()

class test_p2t_exc(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.l1 = self.p.stackup.add_layer("l1", (0, 0, 1))
        self.l2 = self.p.stackup.add_layer("l2", (1, 0, 0))

