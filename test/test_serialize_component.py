from pcbre.matrix import Point2
from pcbre.model.const import SIDE
from pcbre.model.dipcomponent import DIPComponent, SIPComponent
from pcbre.model.net import Net
from pcbre.model.passivecomponent import Passive2Component, PassiveSymType, Passive2BodyType
from pcbre.model.smd4component import SMD4Component
from pcbre.model.stackup import Layer

__author__ = 'davidc'

import unittest
from tempfile import TemporaryFile
from pcbre.model.project import Project


class test_ser_cmp_restore(unittest.TestCase):
    def __saverestore(self, p):
        with TemporaryFile(buffering=0) as fd:

            p.save_fd_capnp(fd)
            fd.seek(0)

            p_new = Project.open_fd_capnp(fd)


        return p_new

    def test_save_pin_names_nets(self):
        p = Project()
        p.stackup.add_layer("test", (1, 1, 1))
        d = DIPComponent(p, Point2(64, 54), 33.5, SIDE.Top, p, 12, 512, 640, 1111)
        d.refdes = "UFOO"
        d.partno = "BLAH"


        pads = d.get_pads()
        pads[0].pad_name = "NAME1"
        pads[1].pad_name = "NAME2"
        p.artwork.merge_component(d)

        p_new = self.__saverestore(p)


        self.assertEqual(len(p_new.artwork.components), 1)
        c = next(iter(p_new.artwork.components))

        self.assertEqual(d.refdes, c.refdes)
        self.assertEqual(d.partno, c.partno)

        pads_new = c.get_pads()

        for p_old, p_new in zip(pads, pads_new):
            self.assertEqual(p_old.net.name, p_new.net.name)

        self.assertEqual(pads_new[0].pad_name, "NAME1")
        self.assertEqual(pads_new[1].pad_name, "NAME2")

    def test_save_sip(self):
        p = Project()
        p.stackup.add_layer("test", (1, 1, 1))
        d = SIPComponent(p, Point2(13, 19), 22, SIDE.Bottom, p, 17, 18, 19)
        d.refdes = "UFOO"

        p.artwork.merge_component(d)

        p_new = self.__saverestore(p)

        self.assertEqual(len(p_new.artwork.components), 1)
        c = next(iter(p_new.artwork.components))

        self.assertIsInstance(c, SIPComponent)
        self.assertEqual(d.body_length(), c.body_length())
        self.assertEqual(d.body_width(), c.body_width())
        self.assertEqual(d.pin_count, c.pin_count)
        self.assertEqual(d.pin_space, c.pin_space)
        self.assertEqual(d.pad_size, c.pad_size)
        self.assertEqual(d.theta, c.theta)
        self.assertEqual(d.refdes, c.refdes)

    def test_save_dip(self):
        p = Project()
        p.stackup.add_layer("test", (1, 1, 1))
        d = DIPComponent(p, Point2(64, 54), 33.5, SIDE.Top, p, 12, 512, 640, 1111)
        d.refdes = "UFOO"

        p.artwork.merge_component(d)

        p_new = self.__saverestore(p)

        self.assertEqual(len(p_new.artwork.components), 1)
        c = next(iter(p_new.artwork.components))
        
        self.assertIsInstance(c, DIPComponent)
        self.assertEqual(d.body_length(), c.body_length())
        self.assertEqual(d.body_width(), c.body_width())
        self.assertEqual(d.pin_count, c.pin_count)
        self.assertEqual(d.pin_space, c.pin_space)
        self.assertEqual(d.pin_width, c.pin_width)
        self.assertEqual(d.pad_size, c.pad_size)
        self.assertEqual(d.theta, c.theta)
        self.assertEqual(d.refdes, c.refdes)
    
    def test_save_smd(self):
        p = Project()
        p.stackup.add_layer("test", (1, 1, 1))
        d = SMD4Component(p,
                          Point2(64, 54), 33.5, SIDE.Top, p,
                          32, 46, 17, 55, 801, 914, 3232, 604, 123, 456, 17)
                          
        d.refdes = "UFOO"

        p.artwork.merge_component(d)

        p_new = self.__saverestore(p)
        
        self.assertEqual(len(p_new.artwork.components), 1)
        c = next(iter(p_new.artwork.components))

        self.assertEqual(d.side_pins, c.side_pins)

        self.assertEqual(d.dim_1_body, c.dim_1_body)
        self.assertEqual(d.dim_1_pincenter, c.dim_1_pincenter)
        self.assertEqual(d.dim_2_body, c.dim_2_body)
        self.assertEqual(d.dim_2_pincenter, c.dim_2_pincenter)

        self.assertEqual(d.pin_contact_length, c.pin_contact_length)
        self.assertEqual(d.pin_contact_width, c.pin_contact_width)
        self.assertEqual(d.pin_spacing, c.pin_spacing)

    def test_save_smd(self):
        p = Project()
        p.stackup.add_layer("test", (1, 1, 1))
        d = Passive2Component(p, Point2(11, 12), 13.3, SIDE.Top, PassiveSymType.TYPE_IND,
                              Passive2BodyType.TH_FLIPPED_CAP, 14, Point2(15, 16),
                              Point2(17, 18), p)

        d.refdes = "UFOO"
        d.partno = "ABCD"

        p.artwork.merge_component(d)

        p_new = self.__saverestore(p)

        self.assertEqual(len(p_new.artwork.components), 1)
        c : Passive2Component = next(iter(p_new.artwork.components))
        self.assertEqual(d.refdes, c.refdes)
        self.assertAlmostEqual(d.theta, c.theta, 3)
        self.assertEqual(d.partno, c.partno)
        self.assertAlmostEqual(d.center.x, c.center.x)
        self.assertAlmostEqual(d.center.y, c.center.y)
        self.assertEqual(d.side, c.side)
        self.assertAlmostEqual(d.body_corner_vec.x, c.body_corner_vec.x)
        self.assertAlmostEqual(d.body_corner_vec.y, c.body_corner_vec.y)
        self.assertAlmostEqual(d.pin_corner_vec.x, c.pin_corner_vec.x)
        self.assertAlmostEqual(d.pin_corner_vec.y, c.pin_corner_vec.y)
        self.assertEqual(d.pin_d, c.pin_d)
        self.assertEqual(d.sym_type, c.sym_type)
        self.assertEqual(d.body_type, c.body_type)



