__author__ = 'davidc'

from pcbre.matrix import RectSize
import pcbre.algo.skyline as S
import unittest
import numpy


def splitright(node, left, rightheight):
    """
    helper function for building skylines
    This differs from Skyline.split in that split updates the LHS of the split

    :param node: Node to split
    :param left: position to split the node at
    :param rightheight: height of the right side chunk
    :return:
    """

    assert left > node.left

    if node.next is not None:
        assert left < node.next.left


    newnode = S.SkyLineNode(left, rightheight)

    newnode.next = node.next
    node.next = newnode

class TestSkyline(unittest.TestCase):
    def assertSkyLineEquals(self, s, to):
        nodes = list(s.first_iter())
        l = [(n.left, n.height) for n in nodes]
        self.assertListEqual(to, l)

    def test_split(self):
        s = S.SkyLine(64, 64)

        s.split(s.first, 57, 8)
        s.split(s.first, 16, 22)
        s.split(s.first, 7, 23)

        to = [(0,23), (7,22), (16,8), (57,0)]

        self.assertSkyLineEquals(s, to)

    def test_merge(self):

        s = S.SkyLine(64, 64)
        splitright(s.first, 40, 11)
        splitright(s.first, 30, 12)
        splitright(s.first, 23, 12)
        splitright(s.first, 22, 12)
        splitright(s.first, 20, 12)
        splitright(s.first, 10, 11)
        splitright(s.first,  8, 12)
        s.merge()

        to = [(0,0), (8, 12), (10, 11), (20, 12), (40, 11)]
        self.assertSkyLineEquals(s, to)

    def assertCandEquals(self, cand, x, h):
        self.assertIsNotNone(cand)
        msg = "%s not at %d,%d" % (cand, x, h)
        self.assertEqual(cand.node.left, x, msg)
        self.assertEqual(cand.height, h, msg)

    def test_find(self):
        s = S.SkyLine(64, 64)

        splitright(s.first, 40, 4)
        splitright(s.first, 31, 3)
        splitright(s.first, 23, 2)
        splitright(s.first, 22, 1)
        splitright(s.first, 21, 3)
        splitright(s.first, 20, 4)
        splitright(s.first, 10, 3)
        splitright(s.first,  8, 4)


        #  4         ..          .                   ........................
        #  3           .......... .         .........
        #  2                        ........
        #  1                       .
        #  0 ........
        #    ----------------------------------------------------------------
        #    0000000000111111111122222222223333333333444444444455555555556666
        #    0123456789012345678901234567890123456789012345678901234567890123

        self.assertIsNone(s.find(65,0))
        self.assertIsNone(s.find(0,65))
        self.assertCandEquals(s.find(0,64), 0, 0)
        self.assertCandEquals(s.find(8,64), 0, 0)
        self.assertIsNone(s.find(9,65))

        self.assertCandEquals(s.find(8,5), 0, 0)
        self.assertCandEquals(s.find(9,5), 22, 2)
        self.assertCandEquals(s.find(10,5), 10, 3)
        self.assertCandEquals(s.find(11,5), 21, 3)
        self.assertCandEquals(s.find(19,5), 21, 3)
        self.assertCandEquals(s.find(20,5), 0, 4)
        self.assertIsNone(s.find(20,63))

    def test_fill(self):
        s = S.SkyLine(64, 64)

        v = s.pack(64, 4)
        self.assertTupleEqual(v, (0, 0))

        v = s.pack(5, 3)
        self.assertTupleEqual(v, (0, 4))

        v = s.pack(8, 2)
        self.assertTupleEqual(v, (5, 4))

        v = s.pack(64,1)
        self.assertTupleEqual(v, (0, 7))

        v = s.pack(1,57)
        self.assertIsNone(v)

        v = s.pack(1,56)
        self.assertTupleEqual(v, (0, 8))

    def test_packing_multi(self):
        dims = 4

        s = S.SkyLine(dims, dims)
        ar  = numpy.zeros((dims,dims), numpy.uint8)
        for a,b in [(2,1), (2,2), (3,1), (1,1)]:
            pos = s.pack(a,b)
            #print S.print_skyline(s.first)
            if pos is not None:
                x0, y0 = pos
                x1, y1 = x0 + a, y0 + b
                self.assertFalse((ar[y0:y1, x0:x1] != 0).any())
                ar[y0:y1, x0:x1] = 1


    def test_packing_random(self):
        import random
        r = random.Random()
        r.seed(0)

        dims = 1024

        s = S.SkyLine(dims, dims)
        ar  = numpy.zeros((dims,dims), numpy.uint8)

        while True:
            a = r.randint(1,100)
            b = r.randint(1,100)

            pos = s.pack(a,b)
            #print S.print_skyline(s.first)
            if pos is not None:
                x0, y0 = pos
                x1, y1 = x0 + a, y0 + b
                self.assertFalse((ar[y0:y1, x0:x1] != 0).any())
                ar[y0:y1, x0:x1] = 1
            else:
                break
