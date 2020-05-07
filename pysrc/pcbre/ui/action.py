import enum

import qtpy.QtCore as QtCore
from qtpy.QtCore import Qt
import qtpy.QtGui as QtGui

@enum.unique
class EventID(enum.Enum):
    Key_A = 0x41
    Key_B = 0x42
    Key_C = 0x43
    Key_D = 0x44
    Key_E = 0x45
    Key_F = 0x46
    Key_G = 0x47
    Key_H = 0x48
    Key_I = 0x49
    Key_J = 0x4a
    Key_K = 0x4b
    Key_L = 0x4c
    Key_M = 0x4d
    Key_N = 0x4e
    Key_O = 0x4f
    Key_P = 0x50
    Key_Q = 0x51
    Key_R = 0x52
    Key_S = 0x53
    Key_T = 0x54
    Key_U = 0x55
    Key_V = 0x56
    Key_W = 0x57
    Key_X = 0x58
    Key_Y = 0x59
    Key_Z = 0x60

    Key_Space = 0x20
    Key_Tab = 0x09

    Key_Enter = 0x100
    Key_Return = 0x101
    Key_Escape = 0x102

    Mouse_B1 = 0x211 # Typically left button
    Mouse_B2 = 0x212 # Typically right button
    Mouse_B3 = 0x213 # Typically middle button
    Mouse_B4 = 0x214
    Mouse_B5 = 0x215

    Mouse_B1_DragStart = 0x221 # Typically left button
    Mouse_B2_DragStart = 0x222 # Typically right button
    Mouse_B3_DragStart = 0x223 # Typically middle button
    Mouse_B4_DragStart = 0x224
    Mouse_B5_DragStart = 0x225

    Mouse_WheelUp =     0x231
    Mouse_WheelDown =   0x232
    Mouse_WheelLeft =   0x233
    Mouse_WheelRight =  0x234

    @staticmethod
    def from_key_event(qe):
        qt_key = qe.key()
        if qt_key in _key_map:
            return _key_map[qt_key]

        return None

    @staticmethod
    def from_mouse_event(qe):
        if qe.type() == QtCore.QEvent.MouseButtonRelease:
            if qe.button() == Qt.LeftButton:
                return EventID.Mouse_B1
            elif qe.button() == Qt.RightButton:
                return EventID.Mouse_B2
            elif qe.button() == Qt.MidButton:
                return EventID.Mouse_B3
        elif qe.type() == QtCore.QEvent.MouseButtonPress:
            if qe.button() == Qt.LeftButton:
                return EventID.Mouse_B1_DragStart
            elif qe.button() == Qt.RightButton:
                return EventID.Mouse_B2_DragStart
            elif qe.button() == Qt.MidButton:
                return EventID.Mouse_B3_DragStart

        return None
                


_key_map = {}

for i in EventID:
    if i.name.startswith("Key_"):
        if hasattr(Qt, i.name):
            _key_map[getattr(Qt, i.name)] = i
        

class Modifier(enum.Flag):
    Shift = 0x01
    Ctrl =  0x02
    Alt =   0x04
    Meta =  0x08

    @staticmethod
    def from_qevent(qe):
        if isinstance(qe, QtGui.QInputEvent):
            v = Modifier(0)

            qt_modifiers = qe.modifiers()

            if qt_modifiers & Qt.ShiftModifier:
                v |= Modifier.Shift

            if qt_modifiers & Qt.ControlModifier:
                v |= Modifier.Ctrl

            if qt_modifiers & Qt.AltModifier:
                v |= Modifier.Alt

            if qt_modifiers & Qt.MetaModifier:
                v |= Modifier.Meta
        
        return v

class ActionShortcut:
    def __init__(self, evtid, modifiers=Modifier(0)):
        self.evtid = evtid
        self.modifiers = modifiers

class ActionDescription:
    def __init__(self, default_shortcuts, event_code, description):

        # Take one or more shortcuts as an iterable
        try:
            self.default_shortcuts = list(default_shortcuts)
        except TypeError:
            self.default_shortcuts = [default_shortcuts]

        self.event_code = event_code
        self.description = description
    
class MoveEvent:
    def __init__(self, cursor_pos, 
                            world_pos,):

        # cursor_pos: view area point in pixels
        # world_pos: view area point in world coordinates
        # amount: only set for mouse wheel, otherwise defaults to 1
        self.cursor_pos = cursor_pos
        self.world_pos = world_pos

class ActionEvent:
    def __init__(self, code, cursor_pos, world_pos, amount=1):

        # code: Event code in pixels
        # amount: only set for mouse wheel, otherwise defaults to 1
        self.code = code
        self.cursor_pos = cursor_pos
        self.world_pos = world_pos
        self.amount = amount
