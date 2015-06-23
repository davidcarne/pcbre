from pcbre.matrix import Point2
from pcbre.model.artwork_geom import Trace
from pcbre.model.component import Component
from pcbre.model.const import SIDE
from pcbre.model.pad import Pad
from pcbre.model.project import Project
from pcbre.model.stackup import Layer
import numpy

__author__ = 'davidc'

"""
tests relating to component pad merging. Checking that nets are merged/split as is necessary
"""

import unittest


class TestMerges(unittest.TestCase):
    def setUp(self):
        self.p = p = Project()
        l = Layer("foo", [])
        p.stackup.add_layer(l)

        self.l1 = Trace(Point2(-5, 0), Point2(-1, 0), thickness=1, layer=l)
        self.l2 = Trace(Point2(1, 0), Point2(5, 0), thickness=1, layer=l)
        p.artwork.merge_artwork(self.l1)
        p.artwork.merge_artwork(self.l2)

        self.assertIsNotNone(self.l1.net)
        self.assertIsNotNone(self.l2.net)
        self.assertNotEqual(self.l1.net, self.l2.net)

        class Dummy(Component):
            pass

        cmp = Dummy(Point2(0,0), 0, SIDE.Top, side_layer_oracle=p)
        self.pad = Pad(cmp, 0, Point2(0, 0), 0, 3, 3, th_diam=1)


    def test_add_pad(self):

        self.p.artwork.merge_aw_nets(self.pad)

        # mergine should have resulted in joining the nets
        self.assertEqual(self.pad.net, self.l1.net)
        self.assertEqual(self.pad.net, self.l2.net)

    def test_remove_pad(self):
        self.p.artwork.merge_aw_nets(self.pad)
        self.p.artwork.remove_aw_nets(self.pad, suppress_presence_error=True)

        # Since traces are nonoverlapping
        self.assertIsNone(self.pad.net)
        self.assertNotEqual(self.l1.net, self.l2.net)

