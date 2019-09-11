__author__ = 'davidc'


import unittest
import pcbre.ui.undo as U
from qtpy import QtGui, QtCore


if QtGui.qApp == None: QtGui.QApplication([])


@U.undofunc
def cmd_no_merge(target, value):
    old_value = target.value
    target.value = value
    return U.sig(old_value)

@U.undofunc(True)
def cmd_merge(target, value):
    old_value = target.value
    target.value = value
    return U.sig(old_value)

@U.undofunc(True)
def cmd_merge_2(target, value):
    old_value = target.value
    target.value = value
    return U.sig(old_value)

class SomethingElse(object):
    pass

class test_undo(unittest.TestCase):
    def setUp(self):
        self.stack = U.UndoStack()
        self.value = 0
        self.value2 = 11
        self.value3 = 14

    def test_basic(self):
        self.stack.push(cmd_no_merge(self, 1))
        self.assertEqual(self.value, 1)
        self.stack.push(cmd_no_merge(self, 2))
        self.assertEqual(self.value, 2)
        self.stack.push(cmd_merge(self, 3))
        self.assertFalse(self.stack.canRedo())
        self.assertEqual(self.value, 3)
        self.stack.undo()
        self.assertTrue(self.stack.canRedo())
        self.assertEqual(self.value, 2)
        self.stack.undo()
        self.assertEqual(self.value, 1)
        self.assertTrue(self.stack.canUndo())
        self.stack.undo()
        self.assertEqual(self.value, 0)
        self.assertFalse(self.stack.canUndo())

    def test_func_no_merge(self):
        self.stack.push(cmd_no_merge(self, 1))
        self.stack.push(cmd_no_merge(self, 2))
        self.stack.push(cmd_no_merge(self, 3))
        self.stack.undo()
        self.assertEqual(self.value,2)
        self.stack.undo()
        self.assertEqual(self.value,1)
        self.stack.undo()
        self.assertEqual(self.value,0)

    def test_func_merge(self):
        self.stack.push(cmd_no_merge(self, 1))
        self.stack.push(cmd_merge(self, 2, merge=True))
        self.stack.push(cmd_merge(self, 3, merge=True))
        self.stack.push(cmd_no_merge(self, 4))

        self.assertEqual(self.stack.count(), 3)
        self.stack.undo()
        self.assertEqual(self.value,3)
        self.stack.undo()
        self.assertEqual(self.value,1)
        self.stack.redo()
        self.assertEqual(self.value,3)
        self.stack.undo()
        self.assertEqual(self.value,1)
        self.stack.undo()
        self.assertEqual(self.value,0)

    def test_func_wrong_fn(self):
        self.stack.push(cmd_merge(self, 2))
        self.stack.push(cmd_merge_2(self, 3))
        self.assertEqual(self.stack.count(), 2)

    def test_func_wrong_obj(self):
        a = SomethingElse()
        a.value = 9
        self.stack.push(cmd_merge(self, 2))
        self.stack.push(cmd_merge(a, 3))
        self.assertEqual(self.stack.count(), 2)
        self.stack.undo()
        self.stack.undo()

        self.assertEqual(a.value, 9)
        self.assertEqual(self.value, 0)

    def test_kwargs(self):
        a = SomethingElse()
        a.value = 9
        self.stack.push(U.undo_set_params(self, value=3, value2=7))
        self.stack.push(U.undo_set_params(self, value3=9))

        self.assertEqual(self.value, 3)
        self.assertEqual(self.value2, 7)
        self.assertEqual(self.value3, 9)

        self.stack.undo()

        self.assertEqual(self.value, 3)
        self.assertEqual(self.value2, 7)
        self.assertEqual(self.value3, 14)

        self.stack.undo()

        self.assertEqual(self.value, 0)
        self.assertEqual(self.value2, 11)
        self.assertEqual(self.value3, 14)

    def test_kwargs_merge(self):
        self.stack.push(U.undo_set_params(self, value=6, merge=True))
        self.stack.push(U.undo_set_params(self, value=7, merge=True))




