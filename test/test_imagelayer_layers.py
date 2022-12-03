
import pcbre.model.project as P
import pcbre.model.stackup as S
import pcbre.model.imagelayer as IL
import unittest

from pcbre.model.serialization import PersistentIDClass


class via_sanity(unittest.TestCase):
    def setUp(self):
        self.p = P.Project.create()

    def test_via_sanity(self):
        p = self.p

        color = (1, 1, 1)

        l1 = p.stackup.add_layer("Top", color)
        l2 = p.stackup.add_layer("Bottom", color)

        lv1 = IL.ImageLayer(p, p.unique_id_registry.generate(PersistentIDClass.KeyPoint), name="foo", data=bytes())
        lv2 = IL.ImageLayer(p, p.unique_id_registry.generate(PersistentIDClass.KeyPoint), name="bar", data=bytes())

        p.imagery.add_imagelayer(lv1)
        p.imagery.add_imagelayer(lv2)

        l1.imagelayers = [lv1, lv2]

        assert lv1 in l1.imagelayers


