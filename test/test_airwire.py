from pcbre.matrix import Point2
from pcbre.model.artwork_geom import Trace, Airwire
from pcbre.model.project import Project

__author__ = 'davidc'

import unittest

class test_airwire(unittest.TestCase):
    def setUp(self):
        from test.common import setup2Layer
        setup2Layer(self)


        self.trace_top = Trace(Point2(50, 50), Point2(7000, 7000), 10, self.top_layer)
        self.trace_bot = Trace(Point2(7000, 50), Point2(50, 7000), 10, self.bottom_layer)
        self.p.artwork.merge_artwork(self.trace_top)
        self.p.artwork.merge_artwork(self.trace_bot)

        self.assertNotEqual(self.trace_top.net, self.trace_bot.net)

    def test_basic_join(self):
        airwire = Airwire(Point2(200, 201), Point2(51, 7000), self.top_layer, self.bottom_layer, None)
        self.p.artwork.merge_artwork(airwire)

        # Validate airwire addition causes add
        self.assertEqual(self.trace_top.net, self.trace_bot.net)
        self.assertEqual(self.trace_top.net, airwire.net)

        self.p.artwork.remove_artwork(airwire)

        # Validate airwire removal causes unjoin
        self.assertNotEqual(self.trace_top.net, self.trace_bot.net)


    def test_remove_one_ep(self):
        airwire = Airwire(Point2(200, 201), Point2(49, 7000), self.top_layer, self.bottom_layer, None)
        self.p.artwork.merge_artwork(airwire)


        self.assertIn(airwire, self.p.artwork.airwires)

        self.p.artwork.remove_artwork(self.trace_top)

        # Removal of endpoint geom should result in removal of airwire
        self.assertNotIn(airwire, self.p.artwork.airwires)


    def test_remove_other_ep(self):
        airwire = Airwire(Point2(200, 201), Point2(50, 7000), self.top_layer, self.bottom_layer, None)
        self.p.artwork.merge_artwork(airwire)


        self.assertIn(airwire, self.p.artwork.airwires)

        self.p.artwork.remove_artwork(self.trace_bot)

        # Removal of endpoint geom should result in removal of airwire
        self.assertNotIn(airwire, self.p.artwork.airwires)
