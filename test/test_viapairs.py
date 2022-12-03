from pcbre.matrix import Point2
from pcbre.model.artwork_geom import Via
from pcbre.model.net import Net

import pcbre.model.project as P
import pcbre.model.imagelayer as IL
import pcbre.model.stackup as S
import pcbre.model.artwork as A
import unittest


class ViaSanity(unittest.TestCase):
    def setUp(self):
        self.p = P.Project.create()

    def test_via_sanity(self):
        p = self.p

        color = (1, 1, 1)
        l1 = p.stackup.add_layer(name="Top", color=color)
        l2 = p.stackup.add_layer(name="L2", color=color)
        l3 = p.stackup.add_layer(name="L3", color=color)
        l4 = p.stackup.add_layer(name="L4", color=color)
        l5 = p.stackup.add_layer(name="L5", color=color)
        l6 = p.stackup.add_layer(name="Bottom", color=color)

        vp1 = p.stackup.add_via_pair(l1, l6)
        vp2 = p.stackup.add_via_pair(l5, l2)

        self.assertEqual(vp1.layers, (l1, l6))
        self.assertEqual(vp2.layers, (l2, l5))

        self.assertEqual(vp1.all_layers, [l1, l2, l3, l4, l5, l6])
        self.assertEqual(vp2.all_layers, [l2, l3, l4, l5])

    def test_add_via(self):
        p = self.p
        l1 = p.stackup.add_layer("Top", (1, 1, 1))
        l2 = p.stackup.add_layer("Bot", (1, 1, 1))

        vp = p.stackup.add_via_pair(l1, l2)

        n = p.nets.new()
        via = Via(Point2(0, 0), vp, 1, net=n)
        p.artwork.add_artwork(via)
