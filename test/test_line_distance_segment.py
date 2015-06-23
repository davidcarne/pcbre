__author__ = 'davidc'

import unittest

from pcbre.matrix import Point2, line_distance_segment

ROOT_2 = 2**.5
class test_dist_seg(unittest.TestCase):
    def test_non_colinear(self):
        dist = line_distance_segment(Point2(1,2), Point2(3,3), Point2(4,4), Point2(5,5))
        self.assertAlmostEqual(dist, ROOT_2, 3)

    def test_colinear(self):
        dist = line_distance_segment(Point2(2,2), Point2(3,3), Point2(4,4), Point2(5,5))
        self.assertAlmostEqual(dist, ROOT_2, 3)

    def test_intersect(self):
        dist = line_distance_segment(Point2(4.5,0), Point2(4.5,10), Point2(4,4), Point2(5,5))
        self.assertAlmostEqual(dist, 0, 3)

    def test_parallel(self):
        dist = line_distance_segment(Point2(0,0), Point2(0,3), Point2(3,-1), Point2(3,7))
        self.assertAlmostEqual(dist, 3, 3)
