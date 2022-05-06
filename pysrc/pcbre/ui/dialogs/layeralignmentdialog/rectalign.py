import contextlib
import typing

from pcbre.model.imagelayer import RectAlignment, ImageLayer
from pcbre.ui.undo import UndoFunc, sig, SigType
from pcbre.ui.widgets.lineedit import PLineEdit
from pcbre.ui.widgets.unitedit import UnitLineEdit, UNIT_GROUP_MM

__author__ = 'davidc'

from qtpy import QtCore, QtWidgets, QtGui
from pcbre.ui.tools.basetool import BaseToolController
from pcbre.matrix import translate, scale, Vec2, project_point_line, rotate, line_intersect, Intersect, \
    project_point, Rect
from pcbre.ui.gl import VAO, VBOBind
from OpenGL.arrays.vbo import VBO  # type: ignore
import OpenGL.GL as GL  # type: ignore
import numpy
import math
import cv2  # type: ignore

from pcbre.units import MM

from typing import List, Optional, Any, TYPE_CHECKING, TypeVar, \
    Sequence, Tuple, cast, Dict
from pcbre.ui.tool_action import ToolActionShortcut, ToolActionDescription, EventID, Modifier
import pcbre.ui.dialogs.layeralignmentdialog.dialog

import enum

CornerHandleType = Tuple[Vec2, Vec2, Vec2, Vec2]
LineHandleType = Tuple[Optional[Vec2], Optional[Vec2],
                       Optional[Vec2], Optional[Vec2],
                       Optional[Vec2], Optional[Vec2],
                       Optional[Vec2], Optional[Vec2]]
AlignHandleType = Tuple[Vec2, Vec2, Vec2, Vec2, Optional[Vec2], Optional[Vec2],
                        Optional[Vec2], Optional[Vec2],
                        Optional[Vec2], Optional[Vec2],
                        Optional[Vec2], Optional[Vec2]]
AllHandleType = Tuple[Vec2, Vec2, Vec2, Vec2, Optional[Vec2], Optional[Vec2],
                        Optional[Vec2], Optional[Vec2],
                        Optional[Vec2], Optional[Vec2],
                        Optional[Vec2], Optional[Vec2],
                        Vec2, Vec2, Vec2, Vec2]
DimHandleType = Tuple[Vec2, Vec2, Vec2, Vec2]

U = TypeVar('U')
if TYPE_CHECKING:
    from pcbre.ui.dialogs.layeralignmentdialog.dialog import LayerAlignmentDialog
    from pcbre.model.project import Project
    import numpy.typing as npt
    from pcbre.ui.gl.glshared import GLShared
    from pcbre.view.viewport import ViewPort
    from pcbre.ui.tool_action import MoveEvent, ToolActionEvent


    class HasChange(typing.Protocol):
        def change(self) -> None:
            ...

corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]


class EventCode(enum.Enum):
    RemoveFromLine = 0
    AddToLine = 1
    Select = 2
    Release = 3


# Modes for handle behaviours
class DM(enum.Enum):
    NONE = 0
    DRAGGING = 1


# 1/2 of the handle size in pixels
HANDLE_HALF_SIZE = 4

# Key/event modifiers for adding/removing handles with mouse actions
ADD_MODIFIER = QtCore.Qt.ControlModifier
DEL_MODIFIER = QtCore.Qt.ShiftModifier

# Each handle has a unique ID
# Max value for each "class" of anchors
# PERIM handles are those on the corners, Anchors are those on edges that "anchor" the line
# DIM handles are those that set dimensions. May be bound to the corners
CORNER_MAX = 4
ANCHOR_MAX = 12
DIM_HANDLE_MAX = 16


# Helper functions to check the types of handles
def IDX_IS_DIM(x: int) -> bool:
    return ANCHOR_MAX <= x < DIM_HANDLE_MAX


def IDX_IS_LINE(x: int) -> bool:
    return CORNER_MAX <= x < ANCHOR_MAX


def IDX_IS_CORNER(x: int) -> bool:
    return x < CORNER_MAX


# Comparison function for type Optional[numpy.ndarray]
def none_compare(old: 'Optional[npt.NDArray[numpy.float64]]', value: 'Optional[npt.NDArray[numpy.float64]]') -> bool:
    if old is None or value is None:
        return old is value
    elif isinstance(old, numpy.ndarray):
        return bool((old != value).any())
    else:
        return bool(old != value)


# cmd pattern objects for updating the model
@UndoFunc
def cmd_set_dimensions(model: 'RectAlignmentModel', dim_a: float, dim_b: float, translate_x: float,
                       translate_y: float) -> SigType:
    """
    Command to set the realspace parameters for the dimensions
    """
    av = sig(model.dim_values[0], model.dim_values[1], model.translate_x, model.translate_y)

    model.set_dim_values(dim_a, dim_b)
    model.translate_x = translate_x
    model.translate_y = translate_y
    model.update_matricies()

    return av


@UndoFunc
def cmd_set_dimensions_locked(model: 'RectAlignmentModel', locked: bool) -> SigType:
    av = sig(model.dims_locked)
    model.dims_locked = locked
    return av


@UndoFunc
def cmd_set_origin_reference(model: 'RectAlignmentModel', idx: int) -> SigType:
    av = sig(model.origin_idx)
    model.origin_idx = idx
    return av


@UndoFunc
def cmd_set_rotate(model: 'RectAlignmentModel', theta: float, flip_x: bool, flip_y: bool) -> SigType:
    av = sig(model.rotate_theta, model.flip_x, model.flip_y)
    model.rotate_theta = theta
    model.flip_x = flip_x
    model.flip_y = flip_y
    return av


class cmd_set_handle_position(QtWidgets.QUndoCommand):
    def __init__(self, model: 'RectAlignmentModel', index: int, position: Optional[Vec2], merge: bool = False) -> None:
        super(cmd_set_handle_position, self).__init__()

        self.model = model
        self.index = index
        self.position = position
        self.merge = merge

        self.old_handles: List[Optional[Vec2]] = []

    def id(self) -> int:
        return 0x10001

    def redo(self) -> None:
        self.old_handles = list(self.model.all_handles())

        self.model.move_handle(self.index, self.position)

    def undo(self) -> None:
        for n, i in enumerate(self.old_handles):
            self.model.move_handle(n, i)

    def mergeWith(self, new: QtWidgets.QUndoCommand) -> bool:
        new_ = cast('cmd_set_handle_position', new)
        if (self.merge and new_.merge and
                self.model is new_.model and
                self.index == new_.index and
                (self.position is None) == (new_.position is None)):
            self.position = new_.position
            return True

        return False


def point2_or_none(p: Optional[Any]) -> Optional[Vec2]:
    if p is None:
        return None
    else:
        return Vec2(p[0], p[1])


class RectAlignmentModel:
    def __init__(self, image: 'ImageLayer'):
        self.__image = image
        # 4 corner handles, 2 (potential) anchor handles per line
        ini_shape = image.decoded_image.shape
        max_dim = float(max(ini_shape))
        x = ini_shape[1] / max_dim
        y = ini_shape[0] / max_dim

        # print("Initial shape:", x, y)

        # Expressed in a way that mypy static type checking likes
        self.__corner_handles: CornerHandleType = (
            Vec2(-x, -y), Vec2(x, -y), Vec2(x, y), Vec2(-x, y),
        )
        self.__line_handles: LineHandleType = (None, None, None, None, None, None, None, None)

        self.__dim_handles = (self.__corner_handles[0],
                              self.__corner_handles[1],
                              self.__corner_handles[1],
                              self.__corner_handles[2])

        self.__dims_locked = True

        self.__placeholder_dim_values: List[float] = [100, 100]
        self.__dim_values: List[Optional[float]] = [None, None]

        self.update_matricies()

        self.translate_x : float = 0
        self.translate_y : float = 0
        self.origin_idx : int = 0

        self.persp_matrix = numpy.identity(3)
        self.scale_matrix = numpy.identity(3)
        self.rotate_theta = 0.0
        self.flip_x = False
        self.flip_y = False


    @property
    def dims_locked(self) -> bool:
        return self.__dims_locked

    @dims_locked.setter
    def dims_locked(self, v: bool) -> None:
        needs_update = v != self.dims_locked
        self.__dims_locked = v
        if needs_update:
            self.update_matricies()


    def load(self, project: 'Project') -> None:
        ra = self.__image.alignment
        assert isinstance(ra, RectAlignment)
        assert len(ra.dim_handles) == 4
        assert len(ra.handles) == 12

        # Handles
        self.__dim_handles = ra.dim_handles
        self.__corner_handles = ra.handles[:4]
        self.__line_handles = ra.handles[4:12]

        # Dims
        self.dims_locked = ra.dims_locked
        self.__dim_values[0] = ra.dims[0]
        self.__dim_values[1] = ra.dims[1]

        # Center/Origin
        self.translate_x = ra.origin_center.x
        self.translate_y = ra.origin_center.y
        self.origin_idx = ra.origin_corner

        # Flips
        self.flip_x = ra.flip_x
        self.flip_y = ra.flip_y

    def save(self, project: 'Project') -> None:
        align = RectAlignment(self.__corner_handles + self.__line_handles, self.__dim_handles, self.__active_dims(), self.dims_locked,
                              Vec2(self.translate_x, self.translate_y), self.origin_idx, self.flip_x, self.flip_y)
        self.__image.set_alignment(align)

        self.__image.transform_matrix = self.image_matrix

    @property
    def flip_rotate_matrix(self) -> 'npt.NDArray[numpy.float64]':
        return cast('npt.NDArray[numpy.float64]',
                    rotate(self.rotate_theta).dot(scale(-1 if self.flip_x else 1, -1 if self.flip_y else 1))
                    )

    @property
    def translate_matrix(self) -> 'npt.NDArray[numpy.float64]':
        pt = self.scale_matrix.dot(self.persp_matrix.dot(self.__corner_handles[self.origin_idx].homol()))
        pt /= pt[2]
        return translate(self.translate_x - pt[0], self.translate_y - pt[1])

    @property
    def placeholder_dim_values(self) -> Tuple[float, float]:
        return (self.__placeholder_dim_values[0], self.__placeholder_dim_values[1])

    @property
    def dim_values(self) -> Tuple[Optional[float], Optional[float]]:
        return self.__dim_values[0], self.__dim_values[1]

    def set_dim_values(self, a: float, b: float) -> None:
        self.__dim_values = [a, b]
        self.change()

    @property
    def image_matrix(self) -> 'npt.NDArray[numpy.float64]':
        return cast('npt.NDArray[numpy.float64]',
                    self.translate_matrix.dot(self.flip_rotate_matrix.dot(self.scale_matrix.dot(self.persp_matrix))))

    def all_handles(self) -> 'Sequence[Optional[Vec2]]':
        if self.dims_locked:
            return self.align_handles
        else:
            return list(self.align_handles) + list(self.dim_handles)

    def set_handle(self, handle_id: int, pos: Optional[Vec2]) -> None:
        if IDX_IS_CORNER(handle_id):
            assert pos is not None
            self.__corner_handles = self.__corner_handles[:handle_id] + (pos,) + self.__corner_handles[handle_id + 1:]
        elif IDX_IS_LINE(handle_id):
            idx = handle_id - CORNER_MAX
            self.__line_handles = self.__line_handles[:idx] + (pos,) + self.__line_handles[idx + 1:]

        elif IDX_IS_DIM(handle_id):
            idx = handle_id - ANCHOR_MAX
            self.__dim_handles = self.__dim_handles[:idx] + (pos,) + self.__dim_handles[idx + 1:]

        self.update_matricies()

    def move_handle(self, handle_id: int, pos: Optional[Vec2]) -> None:
        if IDX_IS_CORNER(handle_id):
            assert pos is not None
            self.__corner_handles = self.__corner_handles[:handle_id] + (pos,) + self.__corner_handles[handle_id + 1:]
            self.__update_line_pos(handle_id, pos)
        elif IDX_IS_LINE(handle_id):
            idx = handle_id - CORNER_MAX
            self.__line_handles = self.__line_handles[:idx] + (pos,) + self.__line_handles[idx + 1:]
            self.__update_line_pos(handle_id, pos)
        elif IDX_IS_DIM(handle_id):
            idx = handle_id - ANCHOR_MAX
            self.__dim_handles = self.__dim_handles[:idx] + (pos,) + self.__dim_handles[idx + 1:]

        self.update_matricies()

    def set_handles(self, s: AllHandleType) -> None:
        assert len(s) == 16
        self.__corner_handles = s[:CORNER_MAX]
        self.__line_handles = s[CORNER_MAX:ANCHOR_MAX]
        self.__dim_handles = s[ANCHOR_MAX:]

        self.update_matricies()

    @property
    def align_handles(self) -> AlignHandleType:
        return self.__corner_handles + self.__line_handles

    @property
    def dim_handles(self) -> DimHandleType:
        if self.dims_locked:
            return (self.__corner_handles[0], self.__corner_handles[1],
                    self.__corner_handles[1], self.__corner_handles[2])
        else:
            return self.__dim_handles

    def lines(self) -> Tuple[Tuple[Vec2, Vec2], Tuple[Vec2, Vec2], Tuple[Vec2, Vec2], Tuple[Vec2, Vec2]]:
        return (
            (self.__corner_handles[0], self.__corner_handles[1]),
            (self.__corner_handles[1], self.__corner_handles[2]),
            (self.__corner_handles[2], self.__corner_handles[3]),
            (self.__corner_handles[3], self.__corner_handles[0]),
        )

    def get_anchors(self, idx: int) -> List[Vec2]:
        assert IDX_IS_CORNER(idx)
        base = 2 * idx
        return [i for i in self.__line_handles[base:base + 2] if i is not None]

    def __active_dims(self) -> Tuple[float, float]:
        d1, d2 = self.dim_values
        if d1 is not None and d2 is not None:
            return (d1, d2)
        return self.placeholder_dim_values

    def __update_line_pos(self, h_idx: int, _pos: Optional[Vec2]) -> None:
        """
        :param h_idx: index of the moved handle
        :param pos: point it was moved to
        :return:
        """
        if _pos is None:
            self.move_handle(h_idx, None)
            return

        pos = _pos.dup()

        # If we're moving an endpoint
        if h_idx < 4:
            anchors_ahead = self.get_anchors(h_idx)
            anchors_prev = self.get_anchors((h_idx - 1) % 4)

            ahead_idx_2 = (h_idx + 1) % 4
            line_ahead_2 = self.lines()[(h_idx + 1) % 4]
            pt_ahead_2 = None

            line_behind_2 = self.lines()[(h_idx - 2) % 4]
            behind_idx_2 = (h_idx - 1) % 4
            pt_behind_2 = None

            if len(anchors_ahead) == 2 and len(anchors_prev) == 2:
                # Our lines are anchored on both sides by double-anchors, so we can't move at all
                return

            # If the ahead of prev line constrain us, then project the point to the line for motion
            elif len(anchors_ahead) == 2:
                pos, _ = project_point_line(pos, anchors_ahead[0], anchors_ahead[1], False)
            elif len(anchors_prev) == 2:
                pos, _ = project_point_line(pos, anchors_prev[0], anchors_prev[1], False)

            assert pos is not None

            if len(anchors_ahead) == 1:
                itype, pt_ahead_2 = line_intersect(pos, anchors_ahead[0], line_ahead_2[0], line_ahead_2[1])
                if itype != Intersect.NORMAL:
                    return

            if len(anchors_prev) == 1:
                itype, pt_behind_2 = line_intersect(pos, anchors_prev[0], line_behind_2[0], line_behind_2[1])
                if itype != Intersect.NORMAL:
                    return

            if pt_ahead_2 is not None:
                self.move_handle(ahead_idx_2, pt_ahead_2)

            if pt_behind_2 is not None:
                self.move_handle(behind_idx_2, pt_behind_2)

            self.move_handle(h_idx, pos)

        else:
            line_idx = (h_idx - 4) // 2
            o_idx = (h_idx & ~1) | (h_idx ^ 1)

            this_anchor = self.align_handles[h_idx].dup()
            other_anchor = self.align_handles[o_idx]

            lines = list(self.lines())

            this_line = lines[line_idx]
            prev_line = lines[(line_idx - 1) % 4]
            next_line = lines[(line_idx + 1) % 4]

            if other_anchor is None:
                if this_anchor is None:
                    delta = Vec2(0, 0)
                else:
                    # One anchor, move the whole line by pos - this_anchor
                    delta = pos - this_anchor
                pt_a = this_line[0].dup() + delta
                pt_b = this_line[1].dup() + delta

            else:
                pt_a = pos
                pt_b = other_anchor.dup()

            # Recalculate the endpoints
            intersect_cond, pt_prev = line_intersect(pt_a, pt_b, prev_line[0], prev_line[1])

            if intersect_cond != Intersect.NORMAL:
                return

            intersect_cond, pt_next = line_intersect(pt_a, pt_b, next_line[0], next_line[1])

            if intersect_cond != Intersect.NORMAL:
                return

            self.move_handle(line_idx, pt_prev)
            self.move_handle((line_idx + 1) % 4, pt_next)

            # We can always move an anchor
            self.move_handle(h_idx, pos)

    def update_matricies(self) -> None:
        # Build compatible arrays for cv2.getPerspectiveTransform
        src = numpy.ones((4, 2), dtype=numpy.float32)
        dst = numpy.ones((4, 2), dtype=numpy.float32)
        src[:, :2] = self.align_handles[:4]
        dst[:, :2] = corners

        # And update the perspective transform
        self.persp_matrix = cv2.getPerspectiveTransform(src, dst)

        # Now, calculate the scale factor
        da = self.dim_handles[1] - self.dim_handles[0]
        db = self.dim_handles[3] - self.dim_handles[2]

        ma = da.mag()
        mb = db.mag()

        sf = 100.0 / max(ma, mb)

        self.__placeholder_dim_values[0] = sf * ma * MM
        self.__placeholder_dim_values[1] = sf * mb * MM

        dims = self.__active_dims()

        # Perspective transform handles - convert to
        handles_pp = []
        for handle in self.dim_handles:
            p1 = self.persp_matrix.dot(handle.homol())
            p1 /= p1[2]
            handles_pp.append(p1[:2])

        da = handles_pp[1] - handles_pp[0]
        db = handles_pp[3] - handles_pp[2]
        A = numpy.vstack([da ** 2, db ** 2])
        B = numpy.array(dims) ** 2
        res = numpy.abs(numpy.linalg.solve(A, B)) ** .5

        self.scale_matrix = scale(res[0], res[1])


def new_anchor_index(mdl: 'RectAlignmentModel', idx: int) -> int:
    assert IDX_IS_CORNER(idx)
    ii = 2 * idx + 4
    if mdl.align_handles[ii] is None:
        return ii
    elif mdl.align_handles[ii + 1] is None:
        return ii + 1
    else:
        assert False


class RectAlignmentControllerView(BaseToolController):
    changed = QtCore.Signal()

    def __init__(self, parent,
                 model: 'pcbre.ui.dialogs.layeralignmentdialog.dialog.AlignmentViewModel'):
        super(RectAlignmentControllerView, self).__init__()

        self._parent = parent
        self.model_overall = model
        self.model = model.ra

        self.__idx_handle_sel: Optional[int] = None
        self.__idx_handle_hover: Optional[int] = None

        self.__behave_mode = DM.NONE
        self.__ghost_handle = None

        self.__init_interaction()

        self.gls: Optional[Any] = None

        self.active = False

    def change(self) -> None:
        self.changed.emit()

    @property
    def tool_actions(self) -> 'Sequence[ToolActionDescription]':
        return g_ACTIONS

    def __init_interaction(self) -> None:
        # Selection / drag handling
        self.__idx_handle_sel = None

        self.__behave_mode = DM.NONE

        # ghost handle for showing placement
        self.__ghost_handle = None

    def initialize(self) -> None:
        self.__init_interaction()
        self.active = True

    def finalize(self) -> None:
        self.active = False

    def initializeGL(self, gls: 'GLShared') -> None:
        self.gls = gls

        assert self.gls is not None

        # Basic solid-color program
        self.prog = self.gls.shader_cache.get("vert2", "frag1")
        self.mat_loc = GL.glGetUniformLocation(self.prog.program, "mat")
        self.col_loc = GL.glGetUniformLocation(self.prog.program, "color")

        # Build a VBO for rendering square "drag-handles"
        self.vbo_handles_ar = numpy.ndarray((4, ), dtype=[("vertex", numpy.float32, 2)])
        self.vbo_handles_ar["vertex"] = numpy.array(corners) * HANDLE_HALF_SIZE

        self.vbo_handles = VBO(self.vbo_handles_ar, GL.GL_STATIC_DRAW, GL.GL_ARRAY_BUFFER)

        self.vao_handles = VAO()
        with self.vbo_handles, self.vao_handles:
            VBOBind(self.prog.program, self.vbo_handles_ar.dtype, "vertex").assign()

        # Build a VBO/VAO for the perimeter
        # We don't initialize it here because it is updated every render
        # 4 verticies for outside perimeter
        # 6 verticies for each dim
        self.vbo_per_dim_ar = numpy.zeros(16, dtype=[("vertex", numpy.float32, 2)])

        self.vbo_per_dim = VBO(self.vbo_per_dim_ar, GL.GL_DYNAMIC_DRAW, GL.GL_ARRAY_BUFFER)

        self.vao_per_dim = VAO()
        with self.vao_per_dim, self.vbo_per_dim:
            VBOBind(self.prog.program, self.vbo_per_dim_ar.dtype, "vertex").assign()

    def im2V(self, pt: Vec2) -> Vec2:
        """Translate Image coordinates to viewport coordinates"""

        if self.model_overall.view_mode.is_aligned():
            ph = project_point(self.model.image_matrix, pt)
            return self.viewPort.tfW2V(ph)
        else:
            return self.viewPort.tfW2V(pt)

    def V2im(self, pt: Vec2) -> Vec2:
        """
        Translate viewport coordinates to image coordinates
        :param pt:
        :return:
        """
        world = self.viewPort.tfV2W(pt)

        if self.model_overall.view_mode.is_aligned():
            inv = numpy.linalg.inv(self.model.image_matrix)
            return project_point(inv, world)
        else:
            return world
        # inv = numpy.linalg.inv(self.model.image_matrix)
        # return Vec2(inv.dot(pt)[:2])

    def gen_dim(self, idx: int, always_above: bool = True) -> 'npt.NDArray[numpy.float64]':
        """
        Generate rendering data for the dimension-lines
        :param idx:
        :return:
        """
        a = self.im2V(self.model.dim_handles[0 + idx])
        b = self.im2V(self.model.dim_handles[1 + idx])

        d = b - a

        delta = (b - a).norm()

        normal = Vec2.from_mat(rotate(math.pi / 2)[:2, :2].dot(delta))

        if always_above:
            if numpy.cross(Vec2(1, 0), normal) > 0:
                normal = -normal

        res = numpy.array([
            a + normal * 8,
            a + normal * 20,
            a + normal * 15,
            b + normal * 15,
            b + normal * 8,
            b + normal * 20,
        ], dtype=numpy.float64)

        return res

    @property
    def disabled(self) -> bool:
        # When the we're showing the aligned view; or if we are using keypoint align
        # don't render any handles
        return not self.active or self.model_overall.view_mode.is_aligned()

    def render(self, viewPort: 'ViewPort') -> None:
        self.viewPort = viewPort

        # Perimeter is defined by the first 4 handles
        self.vbo_per_dim_ar["vertex"][:4] = [self.im2V(pt) for pt in self.model.align_handles[:4]]

        # Generate the dimension lines. For ease of use, we always draw the dim-lines above when dims are manual
        # or below when dims are unlocked
        self.vbo_per_dim_ar["vertex"][4:10] = self.gen_dim(0, not self.model.dims_locked)
        self.vbo_per_dim_ar["vertex"][10:16] = self.gen_dim(2, not self.model.dims_locked)

        self.vbo_per_dim.set_array(self.vbo_per_dim_ar)

        # Ugh..... PyOpenGL isn't smart enough to bind the data when it needs to be copied
        with self.vbo_per_dim:
            self.vbo_per_dim.copy_data()

        GL.glDisable(GL.GL_BLEND)

        # ... and draw the perimeter
        with self.vao_per_dim, self.prog.program:
            GL.glUniformMatrix3fv(self.mat_loc, 1, True, self.viewPort.glWMatrix.astype(numpy.float32))

            # Draw the outer perimeter
            if self.disabled:
                GL.glUniform4f(self.col_loc, 0.8, 0.8, 0.8, 1)
            else:
                GL.glUniform4f(self.col_loc, 0.8, 0.8, 0, 1)
            GL.glDrawArrays(GL.GL_LINE_LOOP, 0, 4)

            # Draw the dimensions
            GL.glUniform4f(self.col_loc, 0.8, 0.0, 0.0, 1)
            GL.glDrawArrays(GL.GL_LINES, 4, 6)

            GL.glUniform4f(self.col_loc, 0.0, 0.0, 0.8, 1)
            GL.glDrawArrays(GL.GL_LINES, 10, 6)

        if self.disabled:
            return

        # Now draw a handle at each corner
        with self.vao_handles, self.prog.program:
            for n, i in enumerate(self.model.align_handles):
                # skip nonexistent handles
                if i is None:
                    continue

                is_anchor = IDX_IS_LINE(n)

                corner_pos = self.im2V(i)

                if self.disabled:
                    color = [0.8, 0.8, 0.8, 1]
                elif self.__idx_handle_sel == n:
                    color = [1, 1, 1, 1]
                elif self.__idx_handle_hover == n:
                    color = [1, 1, 0, 1]
                else:
                    color = [0.8, 0.8, 0, 0.5]

                self.render_handle(corner_pos, color, is_anchor, True)

                if self.__idx_handle_sel == n:
                    self.render_handle(corner_pos, [0, 0, 0, 1], is_anchor, False)

            if self.__ghost_handle is not None:
                self.render_handle(self.__ghost_handle, [0.8, 0.8, 0, 0.5], True)

            if not self.model.dims_locked:
                for n, i in enumerate(self.model.dim_handles):
                    handle_pos = self.im2V(i)
                    if n == self.__idx_handle_sel:
                        color = [1, 1, 1, 1]
                    if n < 2:
                        color = [0.8, 0.0, 0.0, 1]
                    else:
                        color = [0.0, 0.0, 0.8, 1]
                    self.render_handle(handle_pos, color, False, True)
                    if self.__idx_handle_sel == n:
                        self.render_handle(corner_pos, [0, 0, 0, 1], is_anchor, False)

    def render_handle(self, position: Vec2, color: Sequence[float],
                      diagonal: bool = False, filled: bool = False) -> None:
        if diagonal:
            r = rotate(math.pi / 4)
        else:
            r = numpy.identity(3)

        m = self.viewPort.glWMatrix.dot(translate(*position).dot(r))
        GL.glUniformMatrix3fv(self.mat_loc, 1, True, m.astype(numpy.float32))
        GL.glUniform4f(self.col_loc, *color)
        GL.glDrawArrays(GL.GL_TRIANGLE_FAN if filled else GL.GL_LINE_LOOP, 0, 4)

    def get_handle_index_for_mouse(self, pos: Vec2) -> Optional[int]:
        """ Returns the index of a handle (or None if one isn't present) given
            a MoveEvent"""
        for n, handle in enumerate(self.model.all_handles()):
            if handle is None:
                continue

            # get the pix-wise BBOX of the handle
            p = self.im2V(handle)

            # Rect encompassing the handle
            r = Rect.from_center_size(p, HANDLE_HALF_SIZE * 2, HANDLE_HALF_SIZE * 2)

            # If event inside the bbox
            if r.point_test(pos) != 0:
                return n
        return None

    def get_line_query_for_mouse(self, pos: Vec2) -> Tuple[Optional[int], Optional[Vec2]]:
        for n, (p1, p2) in enumerate(self.model.lines()):
            p1_v = self.im2V(p1)
            p2_v = self.im2V(p2)

            p, d = project_point_line(pos, p1_v, p2_v)
            if d is not None and d < HANDLE_HALF_SIZE:
                return n, p

        return None, None

    def event_add_constraint(self, event: 'ToolActionEvent') -> None:
        idx, p = self.get_line_query_for_mouse(event.cursor_pos)
        if idx is not None:
            anchors = self.model.get_anchors(idx)
            if len(anchors) < 2:
                p = self.V2im(p)
                idx = new_anchor_index(self.model, idx)

                cmd = cmd_set_handle_position(self.model, idx, p)
                self._parent.undoStack.push(cmd)

                self.__idx_handle_sel = idx
                self.__idx_handle_hover = None

    def event_remove_constraint(self, event: 'ToolActionEvent') -> None:
        handle = self.get_handle_index_for_mouse(event.cursor_pos)

        if handle is not None and handle >= 4:
            cmd = cmd_set_handle_position(self.model, handle, None)
            self._parent.undoStack.push(cmd)

        self.__idx_handle_sel = None
        self.__idx_handle_hover = None

    def event_select(self, event: 'ToolActionEvent') -> None:
        handle = self.get_handle_index_for_mouse(event.cursor_pos)

        self.__idx_handle_sel = handle
        self.__idx_handle_hover = None

        if handle is not None:
            self.__behave_mode = DM.DRAGGING

    def event_release(self, event: 'ToolActionEvent') -> None:
        if self.__behave_mode == DM.DRAGGING:
            self.__behave_mode = DM.NONE

    def tool_event(self, event: 'ToolActionEvent') -> None:
        if self.disabled:
            return

        if event.code == EventCode.Select:
            self.event_select(event)
        elif event.code == EventCode.Release:
            self.event_release(event)
        elif event.code == EventCode.AddToLine:
            self.event_add_constraint(event)
        elif event.code == EventCode.RemoveFromLine:
            self.event_remove_constraint(event)

    def mouseMoveEvent(self, event: 'MoveEvent') -> None:
        if self.disabled:
            return

        needs_update = False
        idx = self.get_handle_index_for_mouse(event.cursor_pos)

        if self.__ghost_handle is not None:
            self.__ghost_handle = None

        if self.__behave_mode == DM.NONE:
            if idx is not None:
                self.__idx_handle_hover = idx

            else:
                self.__idx_handle_hover = None

            # if event.modifiers() & ADD_MODIFIER:
            #    line_idx, pos = self.get_line_query_for_mouse(event.cursor_pos)

            #    if line_idx is not None:
            #        self.__ghost_handle = pos

        elif self.__behave_mode == DM.DRAGGING:
            w_pos = self.V2im(event.cursor_pos)
            # print(w_pos, event.world_pos)

            cmd = cmd_set_handle_position(self.model, self.__idx_handle_sel, w_pos, merge=True)
            self._parent.undoStack.push(cmd)

    def focusOutEvent(self, evt: QtCore.QEvent) -> None:
        self.__idx_handle_sel = None

    def keyPressEvent(self, evt: QtGui.QKeyEvent) -> bool:
        if self.disabled:
            return False

        if evt.key() == QtCore.Qt.Key_Escape:
            self.__idx_handle_sel = None

        elif self.__idx_handle_sel is not None:

            if evt.key() in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace) and IDX_IS_LINE(self.__idx_handle_sel):

                cmd = cmd_set_handle_position(self.model, self.__idx_handle_sel, None)
                self._parent.undoStack.push(cmd)
                # self.model.set_handle(self.__idx_handle_sel, None)
                self.__idx_handle_sel = None

            # Basic 1-px nudging
            elif evt.key() in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right, QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
                _nudgetab: Dict[int,Tuple[int, int]] = {
                    QtCore.Qt.Key_Left: (-1, 0),
                    QtCore.Qt.Key_Right: (1, 0),
                    QtCore.Qt.Key_Up: (0, -1),
                    QtCore.Qt.Key_Down: (0, 1),
                }

                nudge = _nudgetab[evt.key()]

                current = self.im2V(self.model.align_handles[self.__idx_handle_sel])
                viewspace = self.V2im(current + Vec2.from_mat(nudge))
                cmd = cmd_set_handle_position(self.model, self.__idx_handle_sel, viewspace)
                self._parent.undoStack.push(cmd)
                # self.model.set_handle(self.__idx_handle_sel, viewspace)

                self.__ghost_handle = None

    def next_prev_child(self, next: bool) -> bool:
        all_handles = self.model.all_handles()

        step = -1
        if next:
            step = 1

        if self.__behave_mode == DM.DRAGGING:
            return True
        else:
            idx = self.__idx_handle_sel

            if idx is None:
                return False

            while 1:
                idx = (idx + step) % len(all_handles)

                if all_handles[idx] is not None:
                    self.__idx_handle_sel = idx
                    return True


g_ACTIONS: List[ToolActionDescription] = [
    ToolActionDescription(
        ToolActionShortcut(EventID.Mouse_B1, Modifier.Shift),
        EventCode.RemoveFromLine,
        "Remove constraint from line"),
    ToolActionDescription(
        ToolActionShortcut(EventID.Mouse_B1, Modifier.Ctrl),
        EventCode.AddToLine,
        "Add constraint to line"),
    ToolActionDescription(
        ToolActionShortcut(EventID.Mouse_B1_DragStart),
        EventCode.Select,
        "Select event"),
    ToolActionDescription(
        ToolActionShortcut(EventID.Mouse_B1),
        EventCode.Release,
        "Release"),
]


class ThetaLineEdit(PLineEdit):
    def sizeHint(self) -> QtCore.QSize:
        size = super(ThetaLineEdit, self).sizeHint()
        return QtCore.QSize(int(2.5 * size.height()), size.height())


class RectAlignSettingsWidget(QtWidgets.QWidget):
    def __init__(self, parent: 'LayerAlignmentDialog', model: RectAlignmentModel) -> None:
        super(RectAlignSettingsWidget, self).__init__()
        self._parent = parent
        self.model = model

        layout = QtWidgets.QFormLayout()
        self.setLayout(layout)

        dims_gb = QtWidgets.QGroupBox("Scale")
        dims_gb_layout = QtWidgets.QFormLayout()
        dims_gb.setLayout(dims_gb_layout)
        layout.addWidget(dims_gb)

        self.dims_locked_cb = QtWidgets.QCheckBox()
        self.dims_locked_cb.clicked.connect(self.set_dims_locked)
        self.dims_1 = UnitLineEdit(UNIT_GROUP_MM)
        self.dims_2 = UnitLineEdit(UNIT_GROUP_MM)

        self.dims_1.edited.connect(self.changed_dim)
        self.dims_2.edited.connect(self.changed_dim)

        dims_gb_layout.addRow("Dims on perimeter", self.dims_locked_cb)
        dims_gb_layout.addRow("Dimension 1", self.dims_1)
        dims_gb_layout.addRow("Dimension 2", self.dims_2)

        origin_gb = QtWidgets.QGroupBox("Origin")
        origin_gb_layout = QtWidgets.QFormLayout()
        origin_gb.setLayout(origin_gb_layout)
        layout.addWidget(origin_gb)

        self.origin_ref = QtWidgets.QComboBox()
        self.origin_ref.addItem("Lower-left")
        self.origin_ref.addItem("Lower-right")
        self.origin_ref.addItem("Upper-left")
        self.origin_ref.addItem("Upper-right")
        origin_gb_layout.addRow(self.origin_ref)
        self.origin_ref.currentIndexChanged.connect(self.ref_changed)

        self.origin_x = PLineEdit()
        self.origin_y = PLineEdit()

        self.origin_x.editingFinished.connect(self.changed_dim)
        self.origin_y.editingFinished.connect(self.changed_dim)

        origin_gb_layout.addRow("Offset X:", self.origin_x)
        origin_gb_layout.addRow("Offset Y:", self.origin_y)

        layout.addWidget(origin_gb)

        fr_gb = QtWidgets.QGroupBox("Flip/Rotate")
        fr_gb_layout = QtWidgets.QHBoxLayout()
        fr_gb.setLayout(fr_gb_layout)

        self.flip_x_btn = QtWidgets.QPushButton("Flip X")
        self.flip_x_btn.setCheckable(True)
        fr_gb_layout.addWidget(self.flip_x_btn)

        self.flip_y_btn = QtWidgets.QPushButton("Flip Y")
        self.flip_y_btn.setCheckable(True)
        fr_gb_layout.addWidget(self.flip_y_btn)

        fr_gb_layout.addStretch()
        fr_gb_layout.addWidget(QtWidgets.QLabel("Rotate:"))
        self.theta_le = ThetaLineEdit()
        fr_gb_layout.addWidget(self.theta_le)
        fr_gb_layout.addWidget(QtWidgets.QLabel("\u00b0"))

        self.flip_x_btn.clicked.connect(self.rotate_flip_changed)
        self.flip_y_btn.clicked.connect(self.rotate_flip_changed)
        self.theta_le.editingFinished.connect(self.rotate_flip_changed)

        layout.addWidget(fr_gb)

        self.model.update_matricies()
        self.update_from_model()

    def update_from_model(self) -> None:
        self.dims_1.setPlaceholderValue(self.model.placeholder_dim_values[0])
        self.dims_2.setPlaceholderValue(self.model.placeholder_dim_values[1])

        self.dims_1.setValue(self.model.dim_values[0])
        self.dims_2.setValue(self.model.dim_values[1])

        self.dims_locked_cb.setChecked(self.model.dims_locked)

        self.origin_x.setText("%f" % self.model.translate_x)
        self.origin_y.setText("%f" % self.model.translate_y)

        # Updated the box index without forcing a retrigger
        self.origin_ref.blockSignals(True)
        self.origin_ref.setCurrentIndex(self.model.origin_idx)
        self.origin_ref.blockSignals(False)

        self.flip_x_btn.setChecked(self.model.flip_x)
        self.flip_y_btn.setChecked(self.model.flip_y)
        self.theta_le.setText("%4.1f" % math.degrees(self.model.rotate_theta))

    def rotate_flip_changed(self) -> None:
        theta = math.radians(float(self.theta_le.text()))
        cmd = cmd_set_rotate(self.model, theta, self.flip_x_btn.isChecked(), self.flip_y_btn.isChecked())
        self._parent.undoStack.push(cmd)

    def set_dims_locked(self) -> None:
        cmd = cmd_set_dimensions_locked(self.model, self.dims_locked_cb.isChecked())
        self._parent.undoStack.push(cmd)

    def changed_dim(self) -> None:
        dim_a = self.dims_1.getValue()
        dim_b = self.dims_2.getValue()

        translate_x = float(self.origin_x.text())
        translate_y = float(self.origin_y.text())
        if dim_a != self.model.dim_values[0] or dim_b != self.model.dim_values[1] or \
                translate_x != self.model.translate_x or translate_y != self.model.translate_y:
            cmd = cmd_set_dimensions(self.model, dim_a, dim_b, translate_x, translate_y)
            self._parent.undoStack.push(cmd)

    def ref_changed(self, idx: int) -> None:
        # Ordering in the combo box isn't pure counterclockwise. Map ordering to CCW
        if idx == 2:
            idx = 3
        elif idx == 3:
            idx = 2

        cmd = cmd_set_origin_reference(self.model, idx)
        self._parent.undoStack.push(cmd)
