import enum
from typing import Union, List, Iterable, Any, Optional

import qtpy.QtCore as QtCore
import qtpy.QtGui as QtGui
from qtpy.QtCore import Qt

from pcbre.matrix import Vec2, Point2


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

    Key_Backspace = 0x103
    Key_Delete = 0x104

    Mouse_B1 = 0x211  # Typically left button
    Mouse_B2 = 0x212  # Typically right button
    Mouse_B3 = 0x213  # Typically middle button
    Mouse_B4 = 0x214
    Mouse_B5 = 0x215

    Mouse_B1_DragStart = 0x221  # Typically left button
    Mouse_B2_DragStart = 0x222  # Typically right button
    Mouse_B3_DragStart = 0x223  # Typically middle button
    Mouse_B4_DragStart = 0x224
    Mouse_B5_DragStart = 0x225

    Mouse_WheelUp = 0x231
    Mouse_WheelDown = 0x232
    Mouse_WheelLeft = 0x233
    Mouse_WheelRight = 0x234

    @staticmethod
    def from_key_event(qe: QtGui.QKeyEvent) -> 'Optional[EventID]':
        qt_key = qe.key()
        if qt_key in _key_map:
            return _key_map[qt_key]

        return None

    @staticmethod
    def from_mouse_event(qe: QtGui.QMouseEvent) -> 'Optional[EventID]':
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

    def mouse_triggered(self) -> bool:
        return self in (
            EventID.Mouse_B1,
            EventID.Mouse_B2,
            EventID.Mouse_B3,
            EventID.Mouse_B4,
            EventID.Mouse_B5,
            EventID.Mouse_B1_DragStart,
            EventID.Mouse_B2_DragStart,
            EventID.Mouse_B3_DragStart,
            EventID.Mouse_B4_DragStart,
            EventID.Mouse_B5_DragStart)


_key_map = {}

for i in EventID:
    if i.name.startswith("Key_"):
        if hasattr(Qt, i.name):
            _key_map[getattr(Qt, i.name)] = i


class Modifier(enum.Flag):
    Shift = 0x01
    Ctrl = 0x02
    Alt = 0x04
    Meta = 0x08

    @staticmethod
    def from_qevent(qe: QtCore.QEvent) -> 'Modifier':
        v = Modifier(0)

        if isinstance(qe, QtGui.QInputEvent):
            qt_modifiers = int(qe.modifiers())

            if qt_modifiers & Qt.ShiftModifier:
                v |= Modifier.Shift

            if qt_modifiers & Qt.ControlModifier:
                v |= Modifier.Ctrl

            if qt_modifiers & Qt.AltModifier:
                v |= Modifier.Alt

            if qt_modifiers & Qt.MetaModifier:
                v |= Modifier.Meta

        return v


class ToolActionShortcut:
    def __init__(self, evtid: EventID, modifiers: Modifier = Modifier(0)):
        self.evtid = evtid
        self.modifiers = modifiers


class ToolActionDescription:
    def __init__(self, default_shortcuts: Union[ToolActionShortcut, Iterable[ToolActionShortcut]],
                 event_code: Any, description: str):

        # Take one or more shortcuts as an iterable
        if isinstance(default_shortcuts, Iterable):
            self.default_shortcuts = list(default_shortcuts)
        else:
            self.default_shortcuts = [default_shortcuts]

        self.event_code = event_code
        self.description = description


class MoveEvent:
    def __init__(self, cursor_pos: Vec2,
                 world_pos: Vec2, potential_events: List[Any]):
        # cursor_pos: view area point in pixels
        # world_pos: view area point in world coordinates
        # potential_events: Event that would be generated if the primary interaction
        # (typically mouse-press/enter/return) were triggered
        self.cursor_pos = cursor_pos
        self.world_pos = world_pos

        self.potential_events = potential_events

    def __repr__(self) -> str:
        return "<MoveEvent cursor=%r world=%r potential=%r>" % (
            self.cursor_pos, self.world_pos, self.potential_events)


class ToolActionEvent:
    def __init__(self, code: Any, cursor_pos: Point2, world_pos: Point2, amount: float = 1.0) -> None:
        # code: Event code
        # amount: only set for mouse wheel, otherwise defaults to 1
        self.code = code
        self.cursor_pos = cursor_pos
        self.world_pos = world_pos
        self.amount = amount

    def __repr__(self) -> str:
        return "<ToolAction code=%r cursor=%r world=%r amount=%f>" % (
            self.code, self.cursor_pos, self.world_pos, self.amount)
