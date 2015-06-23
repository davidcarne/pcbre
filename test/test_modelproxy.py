from PySide import QtCore
from pcbre.ui.uimodel import mdlacc, GenModel
import unittest
from mock import Mock

class FakeModel(GenModel):
    j = mdlacc(3)

class FakeOther(object):
    j = mdlacc(3)

class test_mdlaccs(unittest.TestCase):

    def setUp(self):
        self.m = Mock()
        self.mdl = FakeModel()
        self.mdl.changed.connect(self.m)

    def testBasicChanged(self):
        self.assertEqual(self.m.call_count, 0)

        self.mdl.changed.emit()
        self.m.assert_called_once_with()

    def test_j_set(self):
        self.assertEqual(self.m.call_count, 0)
        self.mdl.j = 3
        self.assertEqual(self.m.call_count, 0)
        self.mdl.j = 4
        self.m.assert_called_once_with()

    def test_suppression(self):
        with self.mdl.edit():
            self.mdl.j = 5
            self.mdl.j = 6
        self.m.assert_called_once_with()

    def test_autodetect(self):
        self.mdl.sub = FakeModel()

        self.mdl.sub.j = 13

        self.m.assert_called_once_with()

    def test_instance_bug(self):
        a = FakeModel()
        b = FakeModel()

        a.j = 5
        b.j = 7
        self.assertEqual(a.j, 5)
        self.assertEqual(b.j, 7)

    def test_bad_set(self):
        o = FakeOther()
        def fun():
            o.j = 3
        self.assertRaises(NotImplementedError,fun)

    def test_bad_get(self):
        o = FakeOther()
        def fun():
            x = o.j
        self.assertRaises(NotImplementedError,fun)
