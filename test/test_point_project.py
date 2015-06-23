__author__ = 'davidc'

import unittest
from pcbre.matrix import *

ROOT_2 = math.sqrt(2)

class test_pointproject(unittest.TestCase):
    def setUp(self):
        pass

    def assertPointEqual(self, pt1, pt2):
        self.assertAlmostEqual((pt1 - pt2).mag(), 0, 3)

    def test_point_project_zerolen(self):
        pt, dist = project_point_line(Point2(7,7), Point2(6,6), Point2(6,6))

        self.assertPointEqual(pt, Point2(6,6))
        self.assertAlmostEqual(dist, ROOT_2, 3)

    def test_point_project_off_ends(self):

        pt1 = Point2(3,4)
        pt2 = Point2(13,9)

        pi1, di1 = project_point_line(Point2(14,10), pt1, pt2, True, True)

        self.assertPointEqual(pi1, pt2)
        self.assertAlmostEqual(di1, (Point2(14,10) - pt2).mag(), 3)
