import numpy
from pcbre.matrix import Point2
from pcbre.model.imagelayer import KeyPointAlignment
import pcbre.model.project as P
import pcbre.model.imagelayer as IL

import unittest

class keypoint_sanity(unittest.TestCase):
    def setUp(self):
        self.p = P.Project.create()

    def test_keyPointCreation(self):
        p = self.p

        il1 = IL.ImageLayer(name="foo", data=bytes())
        il2 = IL.ImageLayer(name="bar", data=bytes())
        p.imagery.add_imagelayer(il1)
        p.imagery.add_imagelayer(il2)

        kp1 = IL.KeyPoint(Point2(5,5))
        kp2 = IL.KeyPoint(Point2(10,20))
        p.imagery.add_keypoint(kp1)
        p.imagery.add_keypoint(kp2)

        # Verify that keypoint indicies are working as expected
        self.assertEqual(kp1.index, 0)
        self.assertEqual(kp2.index, 1)

        #
        al = KeyPointAlignment()
        il1.set_alignment(al)
        al.set_keypoint_position(kp1, Point2(0,2))

        kp_set = il1.alignment.keypoint_positions
        kpp0 = list(kp_set)[0]

        self.assertEqual(kpp0.key_point, kp1)
        eps = numpy.absolute(kpp0.image_pos - Point2(0,2)).max()
        self.assertLess(eps, 0.0000001)

        al.remove_keypoint(kp1)

        self.assertEqual(len(kp_set), 0)

    def test_keyPointLayerPositions(self):
        p = self.p


        il1 = IL.ImageLayer(name="foo", data=bytes())
        il2 = IL.ImageLayer(name="bar", data=bytes())
        p.imagery.add_imagelayer(il1)
        p.imagery.add_imagelayer(il2)

        kp1 = IL.KeyPoint(Point2(5,5))
        kp2 = IL.KeyPoint(Point2(10,20))
        p.imagery.add_keypoint(kp1)
        p.imagery.add_keypoint(kp2)

        al = KeyPointAlignment()
        il2.set_alignment(al)
        al.set_keypoint_position(kp1, Point2(5,4))

        ll = kp1.layer_positions
        self.assertEqual(len(ll), 1)
        self.assertIs(ll[0][0], il2)
        self.assertEqual(ll[0][1].x, 5)
        self.assertEqual(ll[0][1].y, 4)


