from pcbre.model.imagelayer import RectAlignment
from pcbre.ui.undo import undofunc, sig
from pcbre.ui.widgets.lineedit import PLineEdit
from pcbre.ui.widgets.unitedit import UnitLineEdit, UNIT_GROUP_MM

__author__ = 'davidc'

from qtpy import QtCore, QtGui, QtWidgets
from pcbre.ui.tools.basetool import BaseToolController
from pcbre.matrix import translate, scale, Vec2, project_point_line, rotate, line_intersect, INTERSECT_NORMAL, Point2, \
    projectPoint
from pcbre.ui.uimodel import GenModel, mdlacc
from pcbre.ui.gl import VAO, vbobind
from pcbre.util import float_or_None
from OpenGL.arrays.vbo import VBO
import OpenGL.GL as GL
import numpy
import math
import cv2

from pcbre.units import MM

corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]


# Modes for handle behaviours
MODE_NONE = 0
MODE_DRAGGING = 1

# 1/2 of the handle size in pixels
HANDLE_HALF_SIZE = 4

# Key/event modifiers for adding/removing handles with mouse actions
ADD_MODIFIER = QtCore.Qt.ControlModifier
DEL_MODIFIER = QtCore.Qt.ShiftModifier

# Each handle has a unique ID
# Max value for each "class" of anchors
# PERIM handles are those on the corners, Anchors are those on edges that "anchor" the line
# DIM handles are those that set dimensions. May be bound to the corners
PERIM_HANDLE_MAX = 4
ANCHOR_MAX = 12
DIM_HANDLE_MAX = 16

# Helper functions to check the types of handles
def IDX_IS_DIM(x):
    return ANCHOR_MAX <= x < DIM_HANDLE_MAX

def IDX_IS_ANCHOR(x):
    return PERIM_HANDLE_MAX <= x < ANCHOR_MAX

def IDX_IS_HANDLE(x):
    return x < PERIM_HANDLE_MAX

# Comparison function for type Maybe(numpy.ndarray)
def none_compare(old, value):
    if old is None or value is None:
        return old is value
    elif isinstance(old, numpy.ndarray):
        return (old != value).any()
    else:
        return old != value

# cmd pattern objects for updating the model
@undofunc
def cmd_set_dimensions(model, dim_a, dim_b, translate_x, translate_y):
    """
    Command to set the realspace parameters for the dimensions
    """
    av = sig(model.dim_values[0], model.dim_values[1], model.translate_x, model.translate_y)

    with model.edit():
        model.dim_values[0] = dim_a
        model.dim_values[1] = dim_b
        model.translate_x = translate_x
        model.translate_y = translate_y
        model.update_matricies()

    return av

@undofunc
def cmd_set_dimensions_locked(model, locked):
    av = sig(model.dims_locked)
    model.dims_locked = locked
    return av

@undofunc
def cmd_set_origin_reference(model, idx):
    av = sig(model.origin_idx)
    model.origin_idx = idx
    return av

@undofunc
def cmd_set_rotate(model, theta, flip_x, flip_y):
    av = sig(model.rotate_theta, model.flip_x, model.flip_y)
    with model.edit():
        model.rotate_theta = theta
        model.flip_x = flip_x
        model.flip_y = flip_y
    return av

class cmd_set_handle_position(QtWidgets.QUndoCommand):
    def __init__(self, model, index, position, merge=False):
        super(cmd_set_handle_position, self).__init__()

        self.model = model
        self.index = index
        self.position = position
        self.merge = merge


    def id(self):
        return 0x10001

    def redo(self):
        self.old_align_handles = list(self.model.align_handles)
        self.old_dim_handles = list(self.model.dim_handles)

        self.model.set_handle(self.index, self.position)

    def undo(self):
        for n, i in enumerate(self.old_align_handles):
            self.model.align_handles[n] = i

        for n, i in enumerate(self.old_dim_handles):
            self.model.dim_handles[n] = i

    def mergeWith(self, new):
        if (self.merge and new.merge and
                self.model is new.model and
                self.index == new.index and
                (self.position is None) == (new.position is None)):
            self.position = new.position
            return True

        return False


def point2_or_none(p):
    if p is None:
        return None
    else:
        return Point2(p)

class RectAlignmentModel(GenModel):
    def __init__(self, image):
        GenModel.__init__(self)

        self.__image = image
        # 4 corner handles, 2 (potential) anchor handles per line
        ini_shape = image.decoded_image.shape
        max_dim = float(max(ini_shape))
        x = ini_shape[1] / max_dim
        y = ini_shape[0] / max_dim

        self.__align_handles = [Vec2(-x, -y), Vec2(x, -y), Vec2(x, y), Vec2(-x, y)] + [None] * 8

        self.__dim_handles = [self.__align_handles[0],
                              self.__align_handles[1],
                              self.align_handles[1],
                              self.align_handles[2]]

        self.__placeholder_dim_values = [100, 100]
        self.__dim_values = [None, None]
        self.update_matricies()


    translate_x = mdlacc(0)
    translate_y = mdlacc(0)
    origin_idx = mdlacc(0)

    persp_matrix = mdlacc(numpy.identity(3))
    scale_matrix = mdlacc(numpy.identity(3))

    rotate_theta = mdlacc(0.0)
    flip_x = mdlacc(False)
    flip_y = mdlacc(False)

    dims_locked = mdlacc(True, on=lambda self: self.update_matricies)

    def load(self, project):
        ra = self.__image.alignment
        assert isinstance(ra, RectAlignment)
        assert len(ra.dim_handles) == 4
        assert len(ra.handles) == 12

        # Handles
        self.__dim_handles = [point2_or_none(p) for p in ra.dim_handles]
        self.__align_handles = [point2_or_none(p) for p in ra.handles]

        # Dims
        self.dims_locked = ra.dims_locked
        self.dim_values[0] = ra.dims[0]
        self.dim_values[1] = ra.dims[1]

        # Center/Origin
        self.translate_x = ra.origin_center.x
        self.translate_y = ra.origin_center.y
        self.origin_idx = ra.origin_corner

        # Flips
        self.flip_x = ra.flip_x
        self.flip_y = ra.flip_y


    def save(self, project):
        align = RectAlignment(self.__align_handles, self.__dim_handles, self.__active_dims(), self.dims_locked,
                              Point2(self.translate_x, self.translate_y), self.origin_idx, self.flip_x, self.flip_y)
        self.__image.set_alignment(align)

        self.__image.transform_matrix = self.image_matrix

    @property
    def flip_rotate_matrix(self):
        return rotate(self.rotate_theta).dot(scale(-1 if self.flip_x else 1, -1 if self.flip_y else 1))

    @property
    def translate_matrix(self):
        pt = self.scale_matrix.dot(self.persp_matrix.dot(self.align_handles[self.origin_idx].homol()))
        pt /= pt[2]
        return translate(self.translate_x - pt[0], self.translate_y - pt[1])

    @property
    def placeholder_dim_values(self):
        return RectAlignmentModel._lprox(self, self.__placeholder_dim_values, coerce=None)

    @property
    def dim_values(self):
        return RectAlignmentModel._lprox(self, self.__dim_values, coerce=None)

    @property
    def image_matrix(self):
        return self.translate_matrix.dot(self.flip_rotate_matrix.dot(self.scale_matrix.dot(self.persp_matrix)))

    def all_handles(self):
        if self.dims_locked:
            return self.align_handles
        else:
            return self.align_handles + self.dim_handles

    def set_handle(self, handle_id, pos):
        if IDX_IS_ANCHOR(handle_id) or IDX_IS_HANDLE(handle_id):
            if self.align_handles[handle_id] is None:
                self.align_handles[handle_id] = pos

            self.__update_line_pos(handle_id, pos)
        elif IDX_IS_DIM(handle_id):
            idx = handle_id - ANCHOR_MAX
            self.dim_handles[idx] = pos

        self.update_matricies()

    class _lprox(object):
        def __init__(self, par, backing, n = None, start = 0, coerce=Point2):
            self.par = par
            self.backing = backing
            self.n = n
            if n is None:
                self.n = len(self.backing)

            self.start = start
            self.coerce = coerce

        def __getitem__(self, item):
            if isinstance(item, int):
                if item >= self.n or item < 0:
                    raise IndexError("index %s is not valid" % item)
                return self.backing[self.start + item]
            elif isinstance(item, slice):
                if item.start is None:
                    new_start = self.start
                else:
                    new_start = item.start + self.start

                if item.stop is None:
                    new_stop = self.start + self.n
                else:
                    new_stop = item.stop + self.start

                if (new_start < 0 or new_start >= self.n or (item.step != 1 and item.step is not None) or
                    new_stop <= new_start or new_stop > self.n):
                    raise IndexError("slice %s is not valid" % item)
                return RectAlignmentModel._lprox(self.par, self.backing, new_stop - new_start, new_start)

            raise TypeError

        def __setitem__(self, key, value):
            if value is not None and self.coerce is not None:
                value = self.coerce(value)

            if not isinstance(key, int):
                raise TypeError

            old = self.backing[self.start + key]
            self.backing[self.start + key] = value
            if none_compare(old, value):
                self.par.change()

        def __iter__(self):
            return iter(self.backing[self.start : self.start + self.n])

        def __len__(self):
            return self.n

        def __add__(self, other):
            return list(self) + list(other)

    @property
    def align_handles(self):
        return RectAlignmentModel._lprox(self, self.__align_handles)

    @property
    def dim_handles(self):
        if self.dims_locked:
            return [self.__align_handles[0], self.__align_handles[1],
                    self.align_handles[1], self.align_handles[2]]
        else:
            return RectAlignmentModel._lprox(self, self.__dim_handles, 4)

    def line_iter(self):
        return list(zip(self.align_handles[:PERIM_HANDLE_MAX], self.align_handles[1:PERIM_HANDLE_MAX] + self.align_handles[0:1]))

    def get_anchors(self, idx):
        assert IDX_IS_HANDLE(idx)
        base = 2 * idx + PERIM_HANDLE_MAX
        return [i for i in self.align_handles[base:base + 2] if i is not None]

    def __active_dims(self):
        if self.dim_values[0] is not None and self.dim_values[1] is not None:
            return self.dim_values
        return self.placeholder_dim_values

    def __update_line_pos(self, h_idx, pos):
        """
        :param h_idx: index of the moved handle
        :param pos: point it was moved to
        :return:
        """
        if pos is None:
            self.align_handles[h_idx] = None
            return

        pos = Vec2(pos)

        # If we're moving an endpoint
        if h_idx < 4:
            anchors_ahead = self.get_anchors(h_idx)
            anchors_prev = self.get_anchors((h_idx - 1) % 4)

            ahead_idx_2 = (h_idx + 1) % 4
            line_ahead_2 = self.line_iter()[(h_idx + 1) % 4]
            pt_ahead_2 = None

            line_behind_2 = self.line_iter()[(h_idx - 2) % 4]
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


            if len(anchors_ahead) == 1:
                itype, pt_ahead_2 = line_intersect(pos, anchors_ahead[0], line_ahead_2[0], line_ahead_2[1])
                if itype != INTERSECT_NORMAL:
                    return

            if len(anchors_prev) == 1:
                itype, pt_behind_2 = line_intersect(pos, anchors_prev[0], line_behind_2[0], line_behind_2[1])
                if itype != INTERSECT_NORMAL:
                    return


            if pt_ahead_2 is not None:
                self.align_handles[ahead_idx_2] = pt_ahead_2

            if pt_behind_2 is not None:
                self.align_handles[behind_idx_2] = pt_behind_2
            self.align_handles[h_idx] = pos

        else:
            line_idx = (h_idx - 4) // 2
            o_idx = (h_idx & ~1) | (h_idx ^ 1)

            this_anchor = Vec2(self.align_handles[h_idx])
            other_anchor = self.align_handles[o_idx]

            lines = list(self.line_iter())

            this_line = lines[line_idx]
            prev_line = lines[(line_idx - 1) % 4]
            next_line = lines[(line_idx + 1) % 4]

            if other_anchor is None:
                if this_anchor is None:
                    delta = Vec2(0,0)
                else:
                    # One anchor, move the whole line by pos - this_anchor
                    delta = pos - this_anchor
                pt_a = Vec2(this_line[0]) + delta
                pt_b = Vec2(this_line[1]) + delta

            else:
                pt_a = pos
                pt_b = Vec2(other_anchor)

            # Recalculate the endpoints
            intersect_cond, pt_prev = line_intersect(pt_a, pt_b, prev_line[0], prev_line[1])

            if intersect_cond != INTERSECT_NORMAL:
                return

            intersect_cond, pt_next = line_intersect(pt_a, pt_b, next_line[0], next_line[1])

            if intersect_cond != INTERSECT_NORMAL:
                return

            self.align_handles[line_idx] = pt_prev
            self.align_handles[(line_idx + 1) % 4] = pt_next

            # We can always move an anchor
            self.align_handles[h_idx] = pos


    def update_matricies(self):
        # Build compatible arrays for cv2.getPerspectiveTransform
        src = numpy.ones((4,2), dtype=numpy.float32)
        dst = numpy.ones((4,2), dtype=numpy.float32)
        src[:, :2] = self.align_handles[:4]
        dst[:, :2] = corners

        # And update the perspective transform
        self.persp_matrix = cv2.getPerspectiveTransform(src, dst)

        # Now, calculate the scale factor
        da = self.dim_handles[1] - self.dim_handles[0]
        db = self.dim_handles[3] - self.dim_handles[2]

        ma = da.mag()
        mb = db.mag()

        sf = 100.0/max(ma, mb)

        self.placeholder_dim_values[0] = sf * ma * MM
        self.placeholder_dim_values[1] = sf * mb * MM

        dims = self.__active_dims()

        # Perspective transform handles - convert to
        handles_pp = []
        for handle in self.dim_handles:
            p1 = self.persp_matrix.dot(handle.homol())
            p1 /= p1[2]
            handles_pp.append(p1[:2])

        da = handles_pp[1] - handles_pp[0]
        db = handles_pp[3] - handles_pp[2]
        A = numpy.vstack([da**2, db**2])
        B = numpy.array(dims) ** 2
        res = numpy.abs(numpy.linalg.solve(A, B)) ** .5

        self.scale_matrix = scale(res[0], res[1])



def new_anchor_index(mdl, idx):
    assert IDX_IS_HANDLE(idx)
    ii = 2 * idx + 4
    if mdl.align_handles[ii] is None:
        return ii
    elif mdl.align_handles[ii+1] is None:
        return ii + 1
    else:
        assert False

class RectAlignmentControllerView(BaseToolController, GenModel):
    changed = QtCore.Signal()

    def __init__(self, parent, model):
        super(RectAlignmentControllerView, self).__init__()

        self._parent = parent
        self.model_overall = model
        self.model = model.ra

        self.__init_interaction()

        self.gls = None

        self.active = False

    idx_handle_sel = mdlacc(None)
    idx_handle_hover = mdlacc(None)

    #sel_mode = mdlacc(SEL_MODE_NONE)
    behave_mode = mdlacc(MODE_NONE)
    ghost_handle = mdlacc(None)

    def change(self):
        self.changed.emit()

    def __init_interaction(self):
        # Selection / drag handling
        self.idx_handle_sel = None
        #self.sel_mode = SEL_MODE_NONE

        self.behave_mode = MODE_NONE

        # ghost handle for showing placement
        self.ghost_handle = None

    def initialize(self):
        self.__init_interaction()
        self.active = True

    def finalize(self):
        self.active = False

    def initializeGL(self, gls):
        self.gls = gls
        # Basic solid-color program
        self.prog = self.gls.shader_cache.get("vert2", "frag1")
        self.mat_loc = GL.glGetUniformLocation(self.prog, "mat")
        self.col_loc = GL.glGetUniformLocation(self.prog, "color")

        # Build a VBO for rendering square "drag-handles"
        self.vbo_handles_ar = numpy.ndarray(4, dtype=[("vertex", numpy.float32, 2)])
        self.vbo_handles_ar["vertex"] = numpy.array(corners) * HANDLE_HALF_SIZE


        self.vbo_handles = VBO(self.vbo_handles_ar, GL.GL_STATIC_DRAW, GL.GL_ARRAY_BUFFER)

        self.vao_handles = VAO()
        with self.vbo_handles, self.vao_handles:
            vbobind(self.prog, self.vbo_handles_ar.dtype, "vertex").assign()

        # Build a VBO/VAO for the perimeter
        # We don't initialize it here because it is updated every render
        # 4 verticies for outside perimeter
        # 6 verticies for each dim
        self.vbo_per_dim_ar = numpy.zeros(16, dtype=[("vertex", numpy.float32, 2)])

        self.vbo_per_dim = VBO(self.vbo_per_dim_ar, GL.GL_DYNAMIC_DRAW, GL.GL_ARRAY_BUFFER)

        self.vao_per_dim = VAO()
        with self.vao_per_dim, self.vbo_per_dim:
            vbobind(self.prog, self.vbo_per_dim_ar.dtype, "vertex").assign()

    def im2V(self, pt):
        """Translate Image coordinates to viewport coordinates"""

        if self.model_overall.view_mode:
            ph = projectPoint(self.model.image_matrix, pt)
            return self.viewState.tfW2V(ph)
        else:
            return self.viewState.tfW2V(pt)

    def V2im(self, pt):
        """
        Translate viewport coordinates to image coordinates
        :param pt:
        :return:
        """
        world = self.viewState.tfV2W(pt)

        if self.model_overall.view_mode:
            inv = numpy.linalg.inv(self.model.image_matrix)
            return projectPoint(inv, world)
        else:
            return Vec2(world)
        #inv = numpy.linalg.inv(self.model.image_matrix)
        #return Vec2(inv.dot(pt)[:2])

    def gen_dim(self, idx, always_above = True):
        """
        Generate rendering data for the dimension-lines
        :param idx:
        :return:
        """
        a = self.im2V(self.model.dim_handles[0 + idx])
        b = self.im2V(self.model.dim_handles[1 + idx])

        d = b-a

        delta = (b-a).norm()

        normal = Point2(rotate(math.pi / 2)[:2,:2].dot(delta))

        if always_above:
            if numpy.cross(Vec2(1,0), normal) > 0:
                normal = -normal

        res = numpy.array([
            a + normal * 8,
            a + normal * 20,
            a + normal * 15,
            b + normal * 15,
            b + normal * 8,
            b + normal * 20,
            ])

        return res


    def render(self, vs):
        self.viewState = vs

        disabled = not self.active or self.model_overall.view_mode

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
        with self.vao_per_dim, self.prog:
            GL.glUniformMatrix3fv(self.mat_loc, 1, True, self.viewState.glWMatrix.astype(numpy.float32))

            # Draw the outer perimeter
            if disabled:
                GL.glUniform4f(self.col_loc, 0.8, 0.8, 0.8, 1)
            else:
                GL.glUniform4f(self.col_loc, 0.8, 0.8, 0, 1)
            GL.glDrawArrays(GL.GL_LINE_LOOP, 0, 4)

            # Draw the dimensions
            GL.glUniform4f(self.col_loc, 0.8, 0.0, 0.0, 1)
            GL.glDrawArrays(GL.GL_LINES, 4, 6)

            GL.glUniform4f(self.col_loc, 0.0, 0.0, 0.8, 1)
            GL.glDrawArrays(GL.GL_LINES, 10, 6)

        if disabled:
            return

        # Now draw a handle at each corner
        with self.vao_handles, self.prog:
            for n, i in enumerate(self.model.align_handles):
                # skip nonexistent handles
                if i is None:
                    continue

                is_anchor = IDX_IS_ANCHOR(n)

                corner_pos = self.im2V(i)

                if disabled:
                    color = [0.8, 0.8, 0.8, 1]
                elif self.idx_handle_sel == n:
                    color = [1, 1, 1, 1]
                elif self.idx_handle_hover == n:
                    color = [1, 1, 0, 1]
                else:
                    color = [0.8, 0.8, 0, 0.5]

                self.render_handle(corner_pos, color, is_anchor, True)

                if self.idx_handle_sel == n:
                    self.render_handle(corner_pos, [0,0,0,1], is_anchor, False)

            if self.ghost_handle is not None:
                self.render_handle(self.ghost_handle,[0.8, 0.8, 0, 0.5], True)

            if not self.model.dims_locked:
                for n, i in enumerate(self.model.dim_handles):
                    handle_pos = self.im2V(i)
                    if n == self.idx_handle_sel:
                        color = [1, 1, 1, 1]
                    if n < 2:
                        color = [0.8, 0.0, 0.0, 1]
                    else:
                        color = [0.0, 0.0, 0.8, 1]
                    self.render_handle(handle_pos, color, False, True)
                    if self.idx_handle_sel == n:
                        self.render_handle(corner_pos, [0,0,0,1], is_anchor, False)

    def render_handle(self, position, color, diagonal=False, filled=False):
        if diagonal:
            r = rotate(math.pi/4)
        else:
            r = numpy.identity(3)

        m = self.viewState.glWMatrix.dot(translate(*position).dot(r))
        GL.glUniformMatrix3fv(self.mat_loc, 1, True, m.astype(numpy.float32))
        GL.glUniform4f(self.col_loc, *color)
        GL.glDrawArrays(GL.GL_TRIANGLE_FAN if filled else GL.GL_LINE_LOOP, 0, 4)

    def get_handle_for_mouse(self, pos):
        for n, handle in enumerate(self.model.all_handles()):
            if handle is None:
                continue
            # get the pix-wise BBOX of the handle
            p = self.im2V(handle)
            r = QtCore.QRect(p[0], p[1], 0, 0)
            r.adjust(-HANDLE_HALF_SIZE, -HANDLE_HALF_SIZE, HANDLE_HALF_SIZE, HANDLE_HALF_SIZE)

            # If event inside the bbox
            if r.contains(pos):
                return n
        return None

    def get_line_query_for_mouse(self, pos):
        for n, (p1, p2) in enumerate(self.model.line_iter()):
            p1_v = self.im2V(p1)
            p2_v = self.im2V(p2)

            p, d = project_point_line(pos, p1_v, p2_v)
            if p is not None and d < HANDLE_HALF_SIZE:
                return n, p

        return None, None


    def mousePressEvent(self, event):
        disabled = not self.active or self.model_overall.view_mode
        if disabled:
            return False

        handle = self.get_handle_for_mouse(event.pos())

        if event.button() == QtCore.Qt.LeftButton and event.modifiers() & ADD_MODIFIER:
            idx, p = self.get_line_query_for_mouse(event.pos())
            if idx is not None:
                anchors = self.model.get_anchors(idx)
                if len(anchors) < 2:
                    p = self.V2im(p)
                    idx = new_anchor_index(self.model, idx)

                    cmd = cmd_set_handle_position(self.model, idx, p)
                    self._parent.undoStack.push(cmd)

                    self.idx_handle_sel = idx
                    self.idx_handle_hover = None

        elif event.button() == QtCore.Qt.LeftButton and event.modifiers() & DEL_MODIFIER and (
                        handle is not None and handle >= 4):
            cmd = cmd_set_handle_position(self.model, handle, None)
            self._parent.undoStack.push(cmd)
            #self.model.set_handle(handle, None)

            self.idx_handle_sel = None
            self.idx_handle_hover = None

        elif event.button() == QtCore.Qt.LeftButton:
            self.idx_handle_sel = handle
            self.idx_handle_hover = None
            if handle is not None:
                self.behave_mode = MODE_DRAGGING

        else:
            return False

        return True

    def mouseReleaseEvent(self, event):
        disabled = not self.active or self.model_overall.view_mode
        if disabled:
            return False

        if event.button() == QtCore.Qt.LeftButton and self.behave_mode == MODE_DRAGGING:
            self.behave_mode = MODE_NONE
        else:
            return False

        return True

    def mouseMoveEvent(self, event):
        disabled = not self.active or self.model_overall.view_mode
        if disabled:
            return False

        needs_update = False
        idx = self.get_handle_for_mouse(event.pos())

        if self.ghost_handle is not None:
            self.ghost_handle = None

        if self.behave_mode == MODE_NONE:
            if idx is not None:
                self.idx_handle_hover = idx

            else:
                self.idx_handle_hover = None

            if event.modifiers() & ADD_MODIFIER:
                line_idx, pos = self.get_line_query_for_mouse(event.pos())

                if line_idx is not None:
                    self.ghost_handle = pos

        elif self.behave_mode == MODE_DRAGGING:
            w_pos = self.V2im(Vec2(event.pos()))

            cmd = cmd_set_handle_position(self.model, self.idx_handle_sel, w_pos, merge=True)
            self._parent.undoStack.push(cmd)
            #self.model.set_handle(self.idx_handle_sel, w_pos)


        return False

    def focusOutEvent(self, evt):
        self.idx_handle_sel = None

    def keyPressEvent(self, evt):
        disabled = not self.active or self.model_overall.view_mode
        if disabled:
            return False

        if evt.key() == QtCore.Qt.Key_Escape:
            self.idx_handle_sel = None

        elif self.idx_handle_sel is not None:

            if evt.key() in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace) and IDX_IS_ANCHOR(self.idx_handle_sel):

                cmd = cmd_set_handle_position(self.model, self.idx_handle_sel, None)
                self._parent.undoStack.push(cmd)
                #self.model.set_handle(self.idx_handle_sel, None)
                self.idx_handle_sel = None

            # Basic 1-px nudging
            elif evt.key() in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right, QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
                nudge = {
                    QtCore.Qt.Key_Left:  (-1,  0),
                    QtCore.Qt.Key_Right: ( 1,  0),
                    QtCore.Qt.Key_Up:    ( 0, -1),
                    QtCore.Qt.Key_Down:  ( 0,  1),
                }[evt.key()]

                current = Vec2(self.im2V(self.model.align_handles[self.idx_handle_sel]))
                viewspace = self.V2im(current + nudge)
                cmd = cmd_set_handle_position(self.model, self.idx_handle_sel, viewspace)
                self._parent.undoStack.push(cmd)
                #self.model.set_handle(self.idx_handle_sel, viewspace)

                self.ghost_handle = None

    def next_prev_child(self, next):
        all_handles = self.model.all_handles()

        step = -1
        if next:
            step = 1

        if self.behave_mode == MODE_DRAGGING:
            return True
        else:
            idx = self.idx_handle_sel

            if idx == None:
                return False

            while 1:
                idx = (idx + step) % len(all_handles)

                if all_handles[idx] is not None:
                    self.idx_handle_sel = idx
                    return True



class ThetaLineEdit(PLineEdit):
    def sizeHint(self):
        size = super(ThetaLineEdit, self).sizeHint()
        return QtCore.QSize(2.5 * size.height(), size.height())

class RectAlignSettingsWidget(QtWidgets.QWidget):
    def __init__(self, parent, model):
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

        self.flip_x_btn.clicked.connect(self.rotate_changed)
        self.flip_y_btn.clicked.connect(self.rotate_changed)
        self.theta_le.editingFinished.connect(self.rotate_changed)

        layout.addWidget(fr_gb)

        self.model.changed.connect(self.update_controls_ra)
        self.model.update_matricies()
        self.update_controls_ra()

    def update_controls_ra(self):
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


    def rotate_changed(self):
        theta = math.radians(float(self.theta_le.text()))
        cmd = cmd_set_rotate(self.model, theta, self.flip_x_btn.isChecked(), self.flip_y_btn.isChecked())
        self._parent.undoStack.push(cmd)

    def set_dims_locked(self):
        cmd = cmd_set_dimensions_locked(self.model, self.dims_locked_cb.isChecked())
        self._parent.undoStack.push(cmd)

    def changed_dim(self):
        dim_a = self.dims_1.getValue()
        dim_b = self.dims_2.getValue()

        translate_x = float(self.origin_x.text())
        translate_y = float(self.origin_y.text())
        if dim_a != self.model.dim_values[0] or dim_b != self.model.dim_values[1] or \
                        translate_x != self.model.translate_x or translate_y != self.model.translate_y:
            cmd = cmd_set_dimensions(self.model, dim_a, dim_b, translate_x, translate_y)
            self._parent.undoStack.push(cmd)


    def ref_changed(self, idx):
        # Ordering in the combo box isn't pure counterclockwise. Map ordering to CCW
        if idx == 2:
            idx = 3
        elif idx == 3:
            idx = 2

        cmd = cmd_set_origin_reference(self.model, idx)
        self._parent.undoStack.push(cmd)
