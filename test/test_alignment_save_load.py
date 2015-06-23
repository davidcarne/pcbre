from pcbre.matrix import Point2
from pcbre.model.imagelayer import KeyPointAlignment, ImageLayer, KeyPoint, RectAlignment
from pcbre.model.project import Project
from pcbre.ui.dialogs.layeralignmentdialog.keypointalign import KeypointAlignmentModel, CONS_PERSPECTIVE
import numpy
import random
import unittest
from pcbre.ui.dialogs.layeralignmentdialog.rectalign import RectAlignmentModel

__author__ = 'davidc'


def random_point():
    return Point2(random.randint(-32768, 32768), random.randint(-32768, 32768))

def setup_global(self):
    p = Project()
    self.p = p
    self.kps = [
        KeyPoint(random_point())
        for i in range(0,4)
    ]

    for i in self.kps:
        p.imagery.add_keypoint(i)

    self.il = ImageLayer("foo", b"")
    p.imagery.add_imagelayer(self.il)

    self.il2 = ImageLayer("bar", b"")
    p.imagery.add_imagelayer(self.il2)


class test_kpalign_load(unittest.TestCase):

    def test(self):
        setup_global(self)

        self.ini_align = KeyPointAlignment()
        self.il.set_alignment(self.ini_align)

        for i in range(3):
            self.ini_align.set_keypoint_position(self.kps[i], random_point())

        ial2 = KeyPointAlignment()
        self.il2.set_alignment(ial2)
        ial2.set_keypoint_position(self.kps[2], random_point())

        self.kpa = KeypointAlignmentModel(self.il)

        self.kpa.load(self.p)

        self.assertEqual(len(self.kpa.keypoints), 4)

        # All kps except 3 are in use on the layer
        for i in range(0, 3):
            self.assertTrue(self.kpa.keypoints[i].use)
        self.assertFalse(self.kpa.keypoints[3].use)

        # KP 2 is used on multiple layers, so gui can't delete/recreate it
        self.assertTrue(self.kpa.keypoints[0].is_new)
        self.assertTrue(self.kpa.keypoints[1].is_new)
        self.assertFalse(self.kpa.keypoints[2].is_new)
        self.assertTrue(self.kpa.keypoints[3].is_new)

class test_kpalign_initial_save(unittest.TestCase):
    def test(self):
        p = Project()
        il = ImageLayer("foo",b"")
        il.set_decoded_data(numpy.ndarray((800,600,3), dtype=numpy.float32))


        ini_align = KeypointAlignmentModel(il)

        for i in range(0, 4):
            idx = ini_align.add_keypoint()
            ini_align.set_keypoint_used(idx, True)
            ini_align.set_keypoint_world(idx, random_point())
            ini_align.set_keypoint_px(idx, random_point())

        ini_align.save(p)

        # Make sure we're constrained to perspective
        self.assertEqual(ini_align.constraint_info, CONS_PERSPECTIVE)

        kpa = il.alignment
        self.assertIsInstance(kpa, KeyPointAlignment)
        self.assertEqual(len(kpa.keypoint_positions), 4)
        self.assertEqual(len(p.imagery.keypoints), 4)

        # Now check the positions are equal
        #sa = sorted(kpa.keypoint_positions, lambda x: x.image_pos)
        #sb = sorted(ini_align.keypoints, lambda x: x.layer)


        # Check writeback
        eps = numpy.abs(numpy.identity(3) - il.transform_matrix).max()
        self.assertGreater(eps, 1)

        # Check persp terms calculated
        eps = numpy.abs(il.transform_matrix[2][:2]).max()
        self.assertGreater(eps, 0)

class test_rectalign_initial_save(unittest.TestCase):
    def test(self):
        p = Project()
        il = ImageLayer("foo","b")
        il.set_decoded_data(numpy.ndarray((800,600,3), dtype=numpy.float32))

        ini_align = RectAlignmentModel(il)

        # Setup dimensions
        ini_align.dims_locked = False

        ini_align.dim_values[0] = random.randint(1, 512)
        ini_align.dim_values[1] = random.randint(1, 512)

        for i in range(0, 4):
            ini_align.set_handle(i, random_point())
        for i in range(12, 16):
            ini_align.set_handle(i, random_point())

        ini_align.flip_x = random.random() > 0.5
        ini_align.flip_y = random.random() > 0.5

        ini_align.translate_x = random.random()
        ini_align.translate_y = random.random()

        ini_align.save(p)


        ra = il.alignment
        self.assertIsInstance(ra, RectAlignment)
        self.assertFalse(ra.dims_locked)
        self.assertEqual(len(ra.handles), 12)
        self.assertEqual(len(ra.dim_handles), 4)

        # Check writeback
        eps = numpy.abs(numpy.identity(3) - il.transform_matrix).max()
        self.assertGreater(eps, 1)

        new_ram = RectAlignmentModel(il)
        new_ram.load(p)


        for a, b in zip(ini_align.all_handles(), new_ram.all_handles()):
            if a is None and b is not None or b is None and a is not None:
                self.assertFalse(False, "handles mismatch")
            elif a is None and b is None:
                continue

            eps = float(numpy.abs(a-b).max())
            self.assertAlmostEqual(eps, 0)

        self.assertEqual(new_ram.flip_x, ini_align.flip_x)
        self.assertEqual(new_ram.flip_y, ini_align.flip_y)
        self.assertAlmostEqual(new_ram.translate_x, ini_align.translate_x)
        self.assertAlmostEqual(new_ram.translate_y, ini_align.translate_y)


