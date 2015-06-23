from pcbre.matrix import Point2
from pcbre.model.change import ChangeType

__author__ = 'davidc'

import unittest
from pcbre.model.project import Project
from pcbre.model.artwork import Via
from pcbre.model.artwork_geom import Airwire, Via
from pcbre.model.stackup import Layer, ViaPair
from pcbre.model.net import Net

class test_nets(unittest.TestCase):
    def setUp(self):
        self.p = Project.create()

        l1 = Layer(name="Top", color=(0,0,0))
        l2 = Layer(name="Bot", color=(0,0,1))
        vp = ViaPair(l1,l2)

        self.net0 = Net()
        self.net1 = Net()

        self.v1 = Via(Point2(0, 0), r=1, viapair=vp, net=self.net0)
        self.v2 = Via(Point2(0, 0), r=1, viapair=vp, net=self.net1)


        self.p.stackup.add_layer(l1)
        self.p.stackup.add_layer(l2)

        self.p.stackup.add_via_pair(vp)

        self.p.nets.add_net(self.net0)
        self.p.nets.add_net(self.net1)

        self.p.artwork.add_artwork(self.v1)
        self.p.artwork.add_artwork(self.v2)

    def test_n0(self):
        self.assertEqual(self.net0.name, "N$1")

    def test_n1(self):
        self.assertEqual(self.net1.name, "N$2")

    def test_via_net(self):
        self.assertNotEqual(self.v1.net, self.v2.net)
        self.assertEqual(self.v1.net, self.net0)

    def test_net_merge(self):
        self.p.artwork.merge_nets(self.net0, self.net1)

        self.assertEqual(self.v1.net, self.v2.net)

    def test_net_callback(self):
        self.x = 0

        def f(arg):
            self.x = arg

        self.p.nets.changed.connect(f)
        self.p.artwork.merge_nets(self.net0, self.net1)

        self.assertNotEqual(self.x, 0)
        self.assertEqual(self.x.container, self.p.nets)
        self.assertEqual(self.x.what, self.net1)
        self.assertEqual(self.x.reason, ChangeType.REMOVE)



