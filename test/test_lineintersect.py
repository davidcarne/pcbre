import unittest
from pcbre.matrix import *

class test_mmath(unittest.TestCase):
    def setUp(self):
        pass

    def test_line_intersect_colinear_1(self):
        pt1 = 1, 1
        pt2 = 2, 3

        why, pt = line_intersect(pt1, pt2, pt2, pt1)

        self.assertEqual(why, INTERSECT_COLINEAR)
        self.assertEqual(pt, None)

    def test_line_intersect_colinear_2(self):
        pt1 = 1, 1
        pt2 = 2, 3

        pt3 = 3, 5
        pt4 = 4, 7

        why, pt = line_intersect(pt1, pt2, pt3, pt4)

        self.assertEqual(why, INTERSECT_COLINEAR)
        self.assertEqual(pt, None)

    def test_line_intersect_parallel_1(self):
        pt1 = Vec2(7, 13)
        pt2 = Vec2(2, 96)

        d = Vec2(11,4)
        pt3 = pt1 + d
        pt4 = pt2 + d

        why, pt = line_intersect(pt1, pt2, pt3, pt4)

        self.assertEqual(why, INTERSECT_PARALLEL)
        self.assertEqual(pt, None)

    def test_line_intersect_1(self):
        pt1 = Vec2(0, -3)
        pt2 = Vec2(0, 14)

        pt3 = Vec2(-10, 0)
        pt4 = Vec2(10, 0)

        why, pt = line_intersect(pt1, pt2, pt3, pt4)
        self.assertEqual(why, INTERSECT_NORMAL)
        self.assertAlmostEqual(pt[0], 0, 5)
        self.assertAlmostEqual(pt[1], 0, 5)

    def test_line_intersect_2(self):
        pt1 = Vec2(0, -3)
        pt2 = Vec2(0, 14)

        pt3 = Vec2(-10, 7)
        pt4 = Vec2(10, 7)

        why, pt = line_intersect(pt1, pt2, pt3, pt4)
        self.assertEqual(why, INTERSECT_NORMAL)
        self.assertAlmostEqual(pt[0], 0, 5)
        self.assertAlmostEqual(pt[1], 0, 5)

    def test_line_intersect_2(self):
        pt1 = Vec2(-1, -5)
        pt2 = Vec2(5, 19)


        pt3 = Vec2(-5, 5)
        pt4 = Vec2(-2, 4)
        # passes through 1, 3

        why, pt = line_intersect(pt1, pt2, pt3, pt4)
        self.assertEqual(why, INTERSECT_NORMAL)
        self.assertAlmostEqual(pt[0], 1, 5)
        self.assertAlmostEqual(pt[1], 3, 5)
