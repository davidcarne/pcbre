from pcbre.matrix import Point2
from pcbre.model.artwork_geom import Via
from pcbre.model.net import Net

import pcbre.model.project as P
import pcbre.model.imagelayer as IL
import pcbre.model.stackup as S
import pcbre.model.artwork as A
import unittest

class via_sanity(unittest.TestCase):
    def setUp(self):
        self.p = P.Project.create()

    def test_via_sanity(self):
        p = self.p

        color = (1,1,1,0)
        l1 = S.Layer(name="Top", color=color)
        l2 = S.Layer(name="L2", color=color)
        l3 = S.Layer(name="L3", color=color)
        l4 = S.Layer(name="L4", color=color)
        l5 = S.Layer(name="L5", color=color)
        l6 = S.Layer(name="Bottom", color = color)

        p.stackup.add_layer(l1)
        p.stackup.add_layer(l2)
        p.stackup.add_layer(l3)
        p.stackup.add_layer(l4)
        p.stackup.add_layer(l5)
        p.stackup.add_layer(l6)

        vp1 = S.ViaPair(l1, l6)
        vp2 = S.ViaPair(l5, l2)

        p.stackup.add_via_pair(vp1)
        p.stackup.add_via_pair(vp2)

        self.assertEqual(vp1.layers, (l1, l6))
        self.assertEqual(vp2.layers, (l2, l5))


        self.assertEqual(vp1.all_layers, [l1,l2,l3,l4,l5,l6])
        self.assertEqual(vp2.all_layers, [l2,l3,l4,l5])

    def test_add_via(self):
        p = self.p
        l1 = S.Layer(name="Top", color=(1,1,1,0))
        l2 = S.Layer(name="Bot", color=(1,1,1,0))

        vp = S.ViaPair(l1, l2)

        p.stackup.add_layer(l1)
        p.stackup.add_layer(l2)

        p.stackup.add_via_pair(vp)



        n = Net()
        p.nets.add_net(n)
        via = Via(Point2(0,0), vp, 1, net=n)
        p.artwork.add_artwork(via)



