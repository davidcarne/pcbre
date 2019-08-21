from PySide2 import QtGui, QtCore, QtWidgets
import math
from pcbre.matrix import Point2
from pcbre.ui.widgets.unitedit import UnitLineEdit


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self):
        super(SettingsDialog, self).__init__()

        vl = QtWidgets.QVBoxLayout()

        self.layout = QtWidgets.QFormLayout()

        self.setLayout(vl)
        vl.addLayout(self.layout)

        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        vl.addWidget(bb)

        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)

        self.__saved_pos = QtGui.QCursor.pos()

    @QtCore.Slot()
    def done(self, r):
        super(SettingsDialog, self).done(r)
        QtGui.QCursor.setPos(self.__saved_pos)


class FloatTrait:
    @staticmethod
    def validator():
        return QtGui.QDoubleValidator()

    @staticmethod
    def fmt(value):
        return "%g" % value

    @staticmethod
    def parse(value):
        return float(value)


class IntTrait:
    @staticmethod
    def validator():
        return QtGui.QIntValidator()

    @staticmethod
    def fmt(value):
        return "%d" % value

    @staticmethod
    def parse(value):
        return int(value)


class LineEditable(object):
    def __init__(self, model, attr, traits):
        self.widget = QtGui.QLineEdit()
        self.model = model
        self.attr = attr
        self.traits = traits

        self.widget.setText(self.traits.fmt(getattr(self.model, self.attr)))
        self.widget.setValidator(self.traits.validator())

    def save(self):
        v = self.value
        setattr(self.model, self.attr, v)

    @property
    def value(self):
        return self.traits.parse(self.widget.text())

    @value.setter
    def value(self, v):
        self.widget.setText(self.traits.fmt(v))

class DegreeEditable(object):
    def __init__(self, model, attr):
        self.widget = QtGui.QLineEdit()
        self.model = model
        self.attr = attr

        self.value = getattr(self.model, self.attr)
        self.widget.setValidator(QtGui.QIntValidator())

    def save(self):
        v = self.value
        setattr(self.model, self.attr, v)

    @property
    def value(self):
        return math.radians(float(self.widget.text())) % (math.pi * 2)

    @value.setter
    def value(self, val):
        self.widget.setText("%f" % math.degrees(val))

class UnitEditable(object):
    def __init__(self, model, attr, unitgroup, defaultunit=None):
        self.widget = UnitLineEdit(unitgroup)
        self.widget.suppress_enter = False

        self.model = model
        self.attr = attr
        path = self.attr.split('.')
        self.path = path[:-1]
        self.subattr = path[-1]

        self.load()


    def _get_par_obj(self):
        obj = self.model
        for p_cmp in self.path:
            obj = getattr(obj, p_cmp)

        return obj

    def load(self):
        par =  self._get_par_obj()
        elem = getattr(par, self.subattr)

        self.widget.setValue(elem)

    def save(self):
        v = self.value
        par = self._get_par_obj()
        setattr(par, self.subattr, v)

    @property
    def value(self):
        return self.widget.getValue()

    @value.setter
    def value(self, v):
        self.widget.setValue(v)

class PointUnitEditable(UnitEditable):
    def __init__(self, model, attr, axis, unitgroup, defaultunit = None):
        self.axis = axis
        super(PointUnitEditable, self).__init__(model, attr, unitgroup, defaultunit)

    def load(self):
        par =  self._get_par_obj()
        elem = getattr(getattr(par, self.subattr), self.axis)
        self.widget.setValue(elem)

    def save(self):
        par =  self._get_par_obj()
        cur = getattr(par, self.subattr)
        kw = {'x':cur.x, 'y':cur.y }
        kw[self.axis] = self.value
        v = Point2(**kw)
        setattr(par, self.subattr, v)


class CheckedEditable(object):
    def __init__(self, model, attr):
        self.widget = QtGui.QCheckBox()
        self.model = model
        self.attr = attr
        self.widget.setChecked(getattr(self.model, self.attr))

    def save(self):
        setattr(self.model, self.attr, self.widget.isChecked())


class AutoSettingsDialog(SettingsDialog):
    def __init__(self):
        super(AutoSettingsDialog, self).__init__()
        self.editables = []

    def addEdit(self, name, editor):
        self.layout.addRow(name, editor.widget)
        self.editables.append(editor)
        return editor

    @QtCore.Slot()
    def accept(self):
        for i in self.editables:
            i.save()
        super(AutoSettingsDialog, self).accept()


class AutoSettingsWidget(QtWidgets.QWidget):
    """
    Widget similar to AutoSettingsDialog; for use with MultiAutoSettingsDialog
    """

    def __init__(self):
        super(AutoSettingsWidget, self).__init__()
        self.editables = []
        self.layout = QtGui.QFormLayout()
        self.setLayout(self.layout)

    def addEdit(self, name, editor):
        self.layout.addRow(name, editor.widget)
        self.editables.append(editor)
        return editor

    def save(self):
        for i in self.editables:
            i.save()

class MultiAutoSettingsDialog(QtWidgets.QDialog):
    def __init__(self):
        super(MultiAutoSettingsDialog, self).__init__()

        vl = QtGui.QVBoxLayout()
        self.setLayout(vl)


        self.headerWidget = QtWidgets.QWidget()
        vl.addWidget(self.headerWidget)

        self.__qsw = QtGui.QStackedLayout()
        self.__autoWidgets = []

        vl.addLayout(self.__qsw)

        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        vl.addWidget(bb)

        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)

        self.__saved_pos = QtGui.QCursor.pos()

    @QtCore.Slot()
    def done(self, r):
        super(MultiAutoSettingsDialog, self).done(r)
        QtGui.QCursor.setPos(self.__saved_pos)

    @QtCore.Slot()
    def accept(self):
        super(MultiAutoSettingsDialog, self).accept()

    def addAutoWidget(self, w):
        self.__autoWidgets.append(w)
        return self.__qsw.addWidget(w)

    def selectWidget(self, idx):
        self.__qsw.setCurrentIndex(idx)
        self.currentWidget = self.__autoWidgets[idx]

