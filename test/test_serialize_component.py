from pcbre.matrix import Point2
from pcbre.model.const import SIDE
from pcbre.model.dipcomponent import DIPComponent
from pcbre.model.net import Net
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
        l = Layer("test", [1,1,1])
        p.stackup.add_layer(l)
        d = DIPComponent(Point2(64, 54), 33.5, SIDE.Top, p, 12, 512, 640, 1111)
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

    def test_save_dip(self):
        p = Project()
        l = Layer("test", [1,1,1])
        p.stackup.add_layer(l)
        d = DIPComponent(Point2(64, 54), 33.5, SIDE.Top, p, 12, 512, 640, 1111)
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
        l = Layer("test", [1,1,1])
        p.stackup.add_layer(l)
        d = SMD4Component(Point2(64, 54), 33.5, SIDE.Top, p,
                          32, 46,17,55, 801,914,3232, 604, 123, 456, 17)
                          
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

