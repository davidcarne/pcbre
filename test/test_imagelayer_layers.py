
import pcbre.model.project as P
import pcbre.model.stackup as S
import pcbre.model.imagelayer as IL
import unittest

class via_sanity(unittest.TestCase):
    def setUp(self):
        self.p = P.Project.create()

    def test_via_sanity(self):
        p = self.p

        color = (1,1,1)
        l1 = S.Layer(p, name="Top", color=color)
        l2 = S.Layer(p, name="Bottom", color=color)

        p.stackup.add_layer(l1)
        p.stackup.add_layer(l2)

        lv1 = IL.ImageLayer(p, name="foo", data=bytes())
        lv2 = IL.ImageLayer(p, name="bar", data=bytes())

        p.imagery.add_imagelayer(lv1)
        p.imagery.add_imagelayer(lv2)

        l1.imagelayers = [lv1, lv2]

        assert lv1 in l1.imagelayers


