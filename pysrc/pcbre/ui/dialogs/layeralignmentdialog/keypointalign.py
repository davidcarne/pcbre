from PySide import QtCore, QtGui
from pcbre.model.imagelayer import KeyPointAlignment, KeyPoint
from pcbre.ui.tools.basetool import BaseToolController
from pcbre.matrix import translate, scale, Vec2, project_point_line, rotate, line_intersect, INTERSECT_NORMAL, Point2, \
    Rect, projectPoint
from pcbre.ui.uimodel import GenModel, mdlacc
from pcbre.ui.gl import VAO, vbobind
from pcbre.ui.widgets.lineedit import PLineEdit
from pcbre.ui.widgets.unitedit import UnitLineEdit, UNIT_GROUP_MM, UNIT_GROUP_PX
from pcbre.util import float_or_None
from OpenGL.arrays.vbo import VBO
import OpenGL.GL as GL
import numpy
import cv2
import colorsys

ADD_MODIFIER = QtCore.Qt.ControlModifier
DEL_MODIFIER = QtCore.Qt.ShiftModifier

MODE_NONE = 0
MODE_DRAGGING = 1

# Type-of-constraint constants - used to determine what kind of constraint solution was calculated
CONS_UNCONSTRAINED = 0
CONS_TRANSLATION = 1
CONS_ROTATE_SCALE = 2
CONS_ORTHOGONAL = 3
CONS_PERSPECTIVE = 4
CONS_OVERCONSTRAINED = 5
CONS_SINGULAR = 6

class AlignKeypoint(object):
    """
    Alignment keypoints - distinct from the more full-featured Keypoints in the project data-model
    in that these only care about the world-space coordinates of the keypoint, and the layer-space coords
    of the layer that is currently being aligned
    """
    def __init__(self, is_new=True):
        # World-space coordinates of the keypoint
        self.world = Point2(0,0)

        # Current align-layer-space coordinates of the keypoint (in pixels, not in normalized image coords)
        self.layer = Point2(0,0)

        # Keypoint created for this layer or existing?
        # if existing, keypoint should not be moved in worldspace or deleted
        # since the alignment solution for other layers may rely on it
        # AlignKeypoint.is_new may also be true if it existed before, but no other layer
        # ever used it for alignment (since then it may be safely moved or deleted)
        self.is_new = is_new

        # Use this keypoint for the alignment solution
        self.use = False

def NAME_FOR_KPT(idx, kpt):
    """
    Get the full name of a keypoint
    :param idx: Index of the keypoint to get the name for
    :param kpt: the actual keypoint object
    :return:
    """
    lbl = ""
    if kpt.is_new:
        lbl = " (new)"
    return "Keypoint %d%s" %  ((idx + 1), lbl)

class KeypointAlignmentModelQAI(QtCore.QAbstractListModel):
    """
    Adapter for the keypoint alignment index
    """
    def __init__(self, mdl):
        super(KeypointAlignmentModelQAI, self).__init__()
        self.mdl = mdl

    def rowCount(self, idx):
        if not idx.isValid():
            l = len(self.mdl.keypoints)
            return l
        return 0

    def index(self, row, col, parent):
        assert not parent.isValid()
        return self.createIndex(row, col)

    def data(self, idx, role):
        if role == QtCore.Qt.DisplayRole:
            return NAME_FOR_KPT(idx.row(), self.mdl.keypoints[idx.row()])
        return None

class KeypointAlignmentModel(GenModel):
    """ Full model including the keypoint alignment state
    """
    def __init__(self, image):
        GenModel.__init__(self)
        self.combo_adapter = KeypointAlignmentModelQAI(self)
        self.__keypoints = []
        self.__image = image

    # Currently selected keypoint index. None for no selection
    selected_idx = mdlacc(None)

    def load(self, project):
        # Initialize all the known keypoints
        for pkp in project.imagery.keypoints:
            idx = self.add_keypoint()
            obj = self.keypoints[idx]

            # Link to existing keypoint
            obj._orig_kp = pkp

            # World position = copy of existing position (allocate new mutable obj)
            obj.world = Point2(pkp.world_position)

            for kp_layer, position in pkp.layer_positions:
                if kp_layer is self.__image:
                    obj.layer = Point2(position)
                    obj.use = True
                else:
                    obj.is_new = False

    def save(self, project):
        al = KeyPointAlignment()

        # Remove all keypoints that were deleted
        still_exist_pkp = set(i._orig_kp for i in self.keypoints if hasattr(i, "_orig_kp"))
        for pkp in list(project.imagery.keypoints):
            if not pkp in still_exist_pkp:
                project.imagery.del_keypoint(pkp)

        # Now for all remaining keypoints, recreate
        for kp in self.keypoints:
            # Create or update the world kp
            if not hasattr(kp, "_orig_kp"):
                pkp = KeyPoint(kp.world)
                kp._orig_kp = pkp
                project.imagery.add_keypoint(pkp)
            else:
                pkp = kp._orig_kp
                pkp.world_position = kp.world

        for kp in self.keypoints:
            if kp.use:
                al.set_keypoint_position(kp._orig_kp, kp.layer)

        # Now, save the changes to the layer
        self.__image.set_alignment(al)
        self.__image.transform_matrix = self.image_matrix


    def set_keypoint_world(self, idx, pos):
        """
        set the world coordinates of a keypoint by index
        idx must be within the range of known keypoints
        :param idx:
        :param pos:
        :return:
        """

        # Refuse to move existing keypoints in world-space
        if not self.keypoints[idx].is_new:
            return

        self.__keypoints[idx].world = pos
        self.change()

    def set_keypoint_px(self, idx, pos):
        """
        set the keypoint position on a layer. Pos=None to remove
        :param idx:
        :param pos:
        :param layer:
        :return:
        """
        self.__keypoints[idx].layer = pos

        self.change()

    def set_keypoint_used(self, idx, use):
        """
        Set whether a keypoint is used in the current layer solution
        :param idx:
        :param use:
        :return:
        """
        self.__keypoints[idx].use = use
        self.change()

    def insert_keypoint(self, idx):
        """
        Returns a new keypoint inserted at index idx. Used for undos

        :param idx:
        :return:
        """
        self.combo_adapter.beginInsertRows(QtCore.QModelIndex(), idx, idx)
        self.__keypoints.insert(idx, AlignKeypoint())
        self.combo_adapter.endInsertRows()
        self.change()

    def add_keypoint(self):
        """
        Adds a new keypoint. Returns the index of the new keypoint

        :return:
        """
        idx = len(self.__keypoints)
        self.combo_adapter.beginInsertRows(QtCore.QModelIndex(), idx, idx)
        self.__keypoints.append(AlignKeypoint())
        self.combo_adapter.endInsertRows()

        self.change()

        return idx

    def del_keypoint(self, idx):
        """
        Delete a keypoint by index
        :param idx:
        :return:
        """
        # Refuse to delete existing keypoints
        if not self.keypoints[idx].is_new:
            return

        self.combo_adapter.beginRemoveRows(QtCore.QModelIndex(), idx, idx)
        del self.__keypoints[idx]
        self.combo_adapter.endRemoveRows()
        self.change()

    @property
    def keypoints(self):
        """
        View-only copy of the keypoints. Do not edit the objects returned by this property
        Use the model-level getter/setter functions
        :return: list of keypoints
        """
        return list(self.__keypoints)

    @property
    def _image_transform_info(self):
        """
        Calculate the constraint level and the transform (if possible)
        :return: constraint_level, transform_matrix
        """
        relevant_keypoints = [i for i in self.keypoints if i.use]

        # Num keypoints = 0 - can't compute a transform
        if len(relevant_keypoints) == 0:
            return CONS_UNCONSTRAINED, numpy.identity(3)

        # Num keypoints = 1, just do a simple translate
        elif len(relevant_keypoints) == 1:
            kp = relevant_keypoints[0]

            # Pixel in worldspace
            layer_world = self.__image.p2n(kp.layer)

            # Just basic translation in worldspace
            vec = kp.world - layer_world
            return CONS_TRANSLATION, translate(vec.x, vec.y)

        # Calculate either translate-rotate, or translate-rotate-scale transforms
        elif len(relevant_keypoints) in (2,3):
            # Construct a system of equations to solve the positioning
            # Basic Ax = b, where x is the non-homologous terms of the translation matrix
            # 'A' is made from "rows"

            rows = []
            b = []

            # Add all of the keypoints as constraints
            for kp in relevant_keypoints:
                # normalized image / world coordinates for the keypoint
                lw = self.__image.p2n(kp.layer)
                w = kp.world

                #            a       b       c       d       e       f        #
                rows.append([lw.x,   lw.y,   1,      0,      0,      0,      ])
                rows.append([0,      0,      0,      lw.x,   lw.y,   1,      ])

                b.append(w.x)
                b.append(w.y)

            # If we only have two keypoints, constrain scale to equal on both axes
            if len(relevant_keypoints) == 2:
                rows.append([1,      0,      0,      0,      -1,     0       ])
                rows.append([0,      1,      0,      1,      0,      0       ])
                b.extend((0, 0))

            # Try to solve the system of equations
            a = numpy.vstack(rows)
            try:
                x = numpy.linalg.solve(a, b)

            except numpy.linalg.linalg.LinAlgError:
                # Cant solve, constructed matrix is singular
                return CONS_SINGULAR, numpy.identity(3)

            # Depending on the number of keypoints, we're either constrainted to translate/rotate/equal-scale
            # or full Orthogonal projection
            constraint = CONS_ORTHOGONAL
            if len(relevant_keypoints) == 2:
                constraint = CONS_ROTATE_SCALE

            return constraint, numpy.vstack((x.reshape(2, 3), (0,0,1)))

        elif len(relevant_keypoints) == 4:
            # Perspective transform
            # TODO: replace this with a LMS solver for overconstrained cases
            #       plus provide error estimations and visualize
            src = numpy.ones((4,2), dtype=numpy.float32)
            dst = numpy.ones((4,2), dtype=numpy.float32)
            src[:, :2] = [self.__image.p2n(kp.layer) for kp in relevant_keypoints]
            dst[:, :2] = [kp.world for kp in relevant_keypoints]

            return CONS_PERSPECTIVE, cv2.getPerspectiveTransform(src, dst)

        else:
            # Temporarily refuse to solve overconstrained alignments
            return CONS_OVERCONSTRAINED, numpy.identity(3)

    @property
    def image_matrix(self):
        """
        return the transform matrix (from normalized image coordinates to world space)
        :return:
        """
        _, matrix = self._image_transform_info
        return matrix

    @property
    def image_matrix_inv(self):
        """
        returns the world-space to normalized image coordinate matrix
        :return:
        """
        return numpy.linalg.inv(self.image_matrix)

    @property
    def constraint_info(self):
        """
        Get the constraint info for the current solution (IE, one of the CONS_* constants)
        :return:
        """
        constraint, _ = self._image_transform_info
        return constraint


# Command objects for undo.

class cmd_add_keypoint(QtGui.QUndoCommand):
    def __init__(self, model):
        super(cmd_add_keypoint, self).__init__()
        self.index = None
        self.model = model

    def redo(self):
        self.index = self.model.add_keypoint()

    def undo(self):
        self.model.del_keypoint(self.index)

class cmd_set_keypoint_world(QtGui.QUndoCommand):
    def __init__(self, model, index, world, merge=False, final=False):
        super(cmd_set_keypoint_world, self).__init__()
        self.world =  world
        self.index = index
        self.model = model
        self.merge = merge
        self.final = final

    def id(self):
        return 0x20000

    def mergeWith(self, new):
        if (self.merge and new.merge and
                    self.model is new.model and
                    self.index == new.index and
                    (self.world is None) == (new.world is None)):

            self.world = new.world
            if new.final:
                self.merge = False
            return True
        return False

    def redo(self):
        self.old_world = self.model.keypoints[self.index].world
        self.model.set_keypoint_world(self.index, self.world)

    def undo(self):
        self.model.set_keypoint_world(self.index, self.old_world)


class cmd_set_keypoint_px(QtGui.QUndoCommand):
    def __init__(self, model, index, pxpos, merge=False, final=False):
        super(cmd_set_keypoint_px, self).__init__()
        self.model = model
        self.index = index
        self.pxpos = pxpos

        self.merge = merge
        self.final = final

        self.oldpos = None

    def id(self):
        return 0x20001

    def mergeWith(self, new):
        if (self.merge and new.merge and
            self.model is new.model and
            self.index == new.index and
            (self.pxpos is None) == (new.pxpos is None)):

            self.pxpos = new.pxpos
            if new.final:
                self.merge = False
            return True
        return False

    def redo(self):
        self.oldpos = self.model.keypoints[self.index].layer
        self.model.set_keypoint_px(self.index, self.pxpos)

    def undo(self):
        self.model.set_keypoint_px(self.index, self.oldpos)


class cmd_set_keypoint_used(QtGui.QUndoCommand):
    def __init__(self, model, idx, use):
        super(cmd_set_keypoint_used, self).__init__()
        self.model = model
        self.idx = idx
        self.use = use

    def redo(self):
        self.used = self.model.keypoints[self.idx].use
        self.model.set_keypoint_used(self.idx, self.use)

    def undo(self):
        self.model.set_keypoint_used(self.idx, self.used)

class cmd_del_keypoint(QtGui.QUndoCommand):
    def __init__(self, model, idx):
        super(cmd_del_keypoint, self).__init__()
        self.model = model
        self.idx = idx

    def redo(self):
        self.save = self.model.keypoints[self.idx]
        self.model.del_keypoint(self.idx)

    def undo(self):
        with self.model.edit():
            self.model.insert_keypoint(self.idx)
            self.model.set_keypoint_used(self.idx, self.save.use)
            self.model.set_keypoint_px(self.idx, self.save.layer)
            self.model.set_keypoint_world(self.idx, self.save.world)
            self.save = None


# View-area interaction controller and overlay
class KeypointAlignmentControllerView(BaseToolController):
    def __init__(self, parent, model):
        super(KeypointAlignmentControllerView, self).__init__()
        self.model = model
        self._parent = parent
        self.initialize()

    def initialize(self):
        self.behave_mode = MODE_NONE

    def finalize(self):
        self.behave_mode = MODE_NONE

    def initializeGL(self, gls):
        self.gls = gls

        # zap the cached text on GL reinitialize (VBO handles / etc are likely invalid)
        self.textCached = {}

        # basic solid-color shader
        self.prog = gls.shader_cache.get("vert2", "frag1")

        # Construct a VBO containing all the points we need for rendering
        dtype = numpy.dtype([("vertex", numpy.float32, 2)])
        points = numpy.ndarray((16,), dtype=dtype)

        # keypoint display: edge half-dimension in pixels
        self.d1 = d1 = 20

        # keypoint display: text-area "flag" height in pixels
        th = 16

        # keypoint display: right-edge offset of text flag in pixels
        tw = 6

        points["vertex"] = [
            # Lines making up keypoint cross (rendered with GL_LINES)
            (-d1, -d1), (-d1,  d1),
            (-d1,  d1), ( d1,  d1),
            ( d1,  d1), ( d1, -d1),
            ( d1, -d1), (-d1, -d1),
            ( 0,  -d1), ( 0,   d1),
            (-d1,   0), ( d1,   0),

            # flag (rendered with GL_TRIANGLE_STRIP)
            (-d1, -d1), (-d1, -d1 - th), (-tw, -d1), (-tw,  -d1 - th)
        ]

        # Pack it all into a VBO
        self.handle_vbo = VBO(points, GL.GL_STATIC_DRAW, GL.GL_ARRAY_BUFFER)

        # and bind the program for rendering
        self.handle_vao = VAO()
        with self.handle_vao, self.handle_vbo:
            vbobind(self.prog, dtype, "vertex").assign()

    def render(self, vs):
        self.vs = vs

        # Standard alpha-blending. We emit alpha=1 or alpha=0 (no real blending),
        # but the text rendering needs transparency for font rendering
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)

        # transform from center of keypoint to edge-of-text
        tmove = translate(-self.d1 + 2, -self.d1 - 3).dot(scale(14, -14))

        count = len(self.model.kp.keypoints)
        for n, kp in enumerate(self.model.kp.keypoints):

            # In unaligned view mode we don't need to show any keypoints that aren't in use
            if self.model.view_mode == 0 and not kp.use:
                continue

            # Generate a number of colors, separated by as far in hue-space as possible
            color = colorsys.hsv_to_rgb(float(n) / count, 1,0.8) + (1,)

            # use colors based on current selection
            selected = n == self.model.kp.selected_idx
            frame_color = [1,1,1,1] if selected else color
            text_color = [0,0,0,1] if selected else [1,1,1,1]

            p = self.get_keypoint_viewport_center(kp)

            # Coordinates in view-space
            center_point = vs.glWMatrix.dot(translate(p.x, p.y))
            text_point = center_point.dot(tmove)

            with self.prog, self.handle_vao:
                GL.glUniformMatrix3fv(self.prog.uniforms.mat, 1, True, center_point.astype(numpy.float32))
                GL.glUniform4f(self.prog.uniforms.color, *frame_color)
                # Render the frame
                GL.glDrawArrays(GL.GL_LINES, 0, 12)

                # and the text flag background
                GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 12, 4)

            # Render the text for the flag
            s = self._parent.view.text_batch.get_string("%d" % (n+1))
            self._parent.view.text_batch.submit(s, text_point, text_color)

    def im2V(self, pt):
        """Translate normalized image coordinates to viewport coordinates.
           If in align mode, normalized-image coords == world coordinates"""
        pt = Point2(pt)

        if self.model.view_mode == 0:
            self._parent.il.p2n(pt)

        return Point2(vs.tfW2V(pt))

    def V2im(self, pt):
        pt = Point2(pt)

        world = Point2(self.vs.tfV2W(pt))

        if self.model.view_mode == 0:
            im = self._parent.il.n2p(world)
        else:
            im = world

        return im

    def get_keypoint_viewport_center(self, keypoint):
        """
        Return the x/y center (in viewport coordinates) of a keypoint, depending on the view mode
        In view-mode-unaligned, "World" coordinates are just normalized image coordinates
        In view-mode-aligned, "world coordinates" are the keypoint world coord
        :param keypoint:
        :return:
        """
        if self.model.view_mode == 1:
            pw = keypoint.world
        else:
            pw = self._parent.il.p2n(keypoint.layer)

        return Point2(self.vs.tfW2V(pw))

    def get_keypoint_viewport_box(self, keypoint):
        """
        Get a bbox rect in view coordinates for a keypoint
        :param keypoint:
        :return:
        """
        p = self.get_keypoint_viewport_center(keypoint)

        return Rect.fromCenterSize(p, width=self.d1 * 2, height=self.d1 * 2)

    def get_keypoint_for_mouse(self, pos):
        """
        Pick keypoints by mouse position
        :param pos:
        :return:
        """
        pos = Point2(pos)

        potential = []
        for n, kp in enumerate(self.model.kp.keypoints):
            box = self.get_keypoint_viewport_box(kp)
            if box.point_test(pos) and (self.model.view_mode == 1 or kp.use):
                potential.append((n, kp))


        if self.model.view_mode == 1:
            potential.sort(key=lambda n_x: (not n_x[1].is_new, -n_x[0]))
        else:
            potential.sort(key=lambda n_x1: (-n_x1[0]))

        if potential:
            return potential[0][0]

        return None

    def do_set_cmd(self, pos, final=False):
        """
        Keypoint-position-set command helper. Sets the position of a key point depending to pos (view coordinates)
        :param pos:
        :param final:
        :return:
        """
        w_pos = self.V2im(pos)
        if self.model.view_mode == 0:
            cmd = cmd_set_keypoint_px(self.model.kp, self.model.kp.selected_idx, w_pos, merge=True, final=final)
        else:
            cmd = cmd_set_keypoint_world(self.model.kp, self.model.kp.selected_idx, w_pos, merge=True, final=final)

        self._parent.undoStack.push(cmd)

    def mousePressEvent(self, event):
        handle = self.get_keypoint_for_mouse(event.pos())

        if event.button() == QtCore.Qt.LeftButton and event.modifiers() & ADD_MODIFIER:
            # If we're in world view mode, we need to figure out where this keypoint would be in image space as well
            if self.model.view_mode == 1:
                # World coords of event
                world = Point2(self.vs.tfV2W(event.pos()))
                # Normalized image coords of event
                im_norm = projectPoint(self.model.kp.image_matrix_inv, world)
                # Pixel coords of event
                im_px = self._parent.il.n2p(im_norm)

            # Do all ops as a single macro
            self._parent.undoStack.beginMacro("Add/Set Keypoint")

            cmd = cmd_add_keypoint(self.model.kp)
            self._parent.undoStack.push(cmd)

            # Since we added it manually, we want to use it as part of the alignment
            cmd2 = cmd_set_keypoint_used(self.model.kp, cmd.index, True)
            self._parent.undoStack.push(cmd2)

            # If adding a keypoint in world space, setup the im-space version as well
            if self.model.view_mode == 1:
                cmd2 = cmd_set_keypoint_px(self.model.kp, cmd.index, im_px)
                self._parent.undoStack.push(cmd2)

            # select the keypoint
            self.model.kp.selected_idx = cmd.index

            # and move it to where the click was
            self.do_set_cmd(event.pos(), True)

            self._parent.undoStack.endMacro()

            return

        elif event.button() == QtCore.Qt.LeftButton and event.modifiers() & DEL_MODIFIER and (
                        handle is not None):
            cmd = cmd_del_keypoint(self.model.kp, self.model.kp.selected_idx)
            self._parent.undoStack.push(cmd)
            self.model.kp.selected_idx = None

        elif event.button() == QtCore.Qt.LeftButton:
            self.model.kp.selected_idx = handle
            if handle is not None:
                self.has_dragged = False
                self.behave_mode = MODE_DRAGGING

        else:
            return False

        return True

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.behave_mode == MODE_DRAGGING:
            self.behave_mode = MODE_NONE

            # only update position if we've dragged the handle
            if self.has_dragged:
                self.do_set_cmd(event.pos(), True)
        else:
            return False
        return True

    def mouseMoveEvent(self, event):
        if self.behave_mode == MODE_DRAGGING:
            self.has_dragged = False
            self.do_set_cmd(event.pos())

        return False

    def keyPressEvent(self, evt):
        if evt.key() == QtCore.Qt.Key_Escape:
            self.model.kp.selected_idx = None

        elif self.model.kp.selected_idx is not None:

            if evt.key() in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace):
                cmd = cmd_del_keypoint(self.model.kp, self.model.kp.selected_idx)
                self._parent.undoStack.push(cmd)
                self.model.kp.selected_idx = None

            # Basic 1-px nudging
            elif evt.key() in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right, QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
                nudge = Point2({
                    QtCore.Qt.Key_Left:  (-1,  0),
                    QtCore.Qt.Key_Right: ( 1,  0),
                    QtCore.Qt.Key_Up:    ( 0, -1),
                    QtCore.Qt.Key_Down:  ( 0,  1),
                    }[evt.key()])

                current = self.get_keypoint_viewport_center(self.model.kp.keypoints[self.model.kp.selected_idx])
                self.do_set_cmd(current + nudge, True)


class KeypointAlignmentWidget(QtGui.QWidget):
    def __init__(self, parent, model):
        super(KeypointAlignmentWidget, self).__init__()
        self.model = model
        self._parent = parent

        layout = QtGui.QFormLayout()
        self.setLayout(layout)

        keypoint_gb = QtGui.QGroupBox("Keypoint")
        layout.addWidget(keypoint_gb)

        edit_layout = QtGui.QFormLayout()
        keypoint_gb.setLayout(edit_layout)


        self.kpts_sel = QtGui.QComboBox()
        self.kpts_sel.setModel(self.model.combo_adapter)
        self.kpts_sel.currentIndexChanged.connect(self.kptChanged)
        edit_layout.addRow("Keypoint:", self.kpts_sel)

        self.wx = UnitLineEdit(UNIT_GROUP_MM)
        self.wy = UnitLineEdit(UNIT_GROUP_MM)
        edit_layout.addRow("World X", self.wx)
        edit_layout.addRow("World Y", self.wy)
        self.wx.edited.connect(self.update_world)
        self.wy.edited.connect(self.update_world)

        self.px = UnitLineEdit(UNIT_GROUP_PX)
        self.py = UnitLineEdit(UNIT_GROUP_PX)
        edit_layout.addRow("Image X", self.px)
        edit_layout.addRow("Image Y", self.py)
        self.px.edited.connect(self.update_layer)
        self.py.edited.connect(self.update_layer)


        self.use_for_alignment = QtGui.QCheckBox()
        edit_layout.addRow("Use", self.use_for_alignment)
        self.use_for_alignment.clicked.connect(self.update_used)

        self.add_btn = QtGui.QPushButton("Add New")
        self.add_btn.clicked.connect(self.addKeypoint)
        self.del_btn = QtGui.QPushButton("Remove Current")
        self.del_btn.clicked.connect(self.delKeypoint)
        bhl = QtGui.QHBoxLayout()
        bhl.addWidget(self.add_btn)
        bhl.addWidget(self.del_btn)
        edit_layout.addRow(bhl)


        self.constraint_status_lbl = QtGui.QLabel("")
        self.constraint_status_lbl.setWordWrap(True)
        layout.addRow(self.constraint_status_lbl)

        self.model.changed.connect(self.modelChanged)
        self.modelChanged()

    def addKeypoint(self):
        cmd = cmd_add_keypoint(self.model)
        self._parent.undoStack.push(cmd)
        self.kpts_sel.setCurrentIndex(cmd.index)

    def delKeypoint(self):
        cmd = cmd_del_keypoint(self.model, self.model.selected_idx)
        self._parent.undoStack.push(cmd)

    def modelChanged(self):
        cmb_index = -1 if self.model.selected_idx is None else self.model.selected_idx
        self.kpts_sel.blockSignals(True)
        self.kpts_sel.setCurrentIndex(cmb_index)
        self.kpts_sel.blockSignals(False)
        self.updateTextViews()

    def kptChanged(self):
        """
        Called when keypoint combo-box drop down changed
        :return:
        """
        idx = self.kpts_sel.currentIndex()
        if idx == -1:
            idx = None
        self.model.selected_idx = idx

    def update_world(self):
        idx = self.kpts_sel.currentIndex()
        p = Point2(self.wx.getValue(), self.wy.getValue())
        cmd = cmd_set_keypoint_world(self.model, idx, p)
        self._parent.undoStack.push(cmd)

    def update_layer(self):
        idx = self.kpts_sel.currentIndex()
        p = Point2(self.px.getValue(), self.py.getValue())
        cmd = cmd_set_keypoint_px(self.model, idx, p)
        self._parent.undoStack.push(cmd)

    def update_used(self):
        idx = self.kpts_sel.currentIndex()
        cmd = cmd_set_keypoint_used(self.model, idx, self.use_for_alignment.isChecked())
        self._parent.undoStack.push(cmd)

    def updateTextViews(self):
        idx = self.model.selected_idx

        # Disable keypoint delete when we selected a prior-existing keypoint
        # Also disable delete button when no kp is selected
        self.del_btn.setEnabled(idx is not None and self.model.keypoints[idx].is_new)

        self.updateConstraintLabel()

        # If nothing is selected, clear-out all the edit fields
        if idx is None:
            self.wx.setValue(None)
            self.wy.setValue(None)
            self.px.setValue(None)
            self.py.setValue(None)
            self.wx.setEnabled(False)
            self.wy.setEnabled(False)
            self.px.setEnabled(False)
            self.py.setEnabled(False)
            self.use_for_alignment.setEnabled(False)
            self.use_for_alignment.setChecked(False)
            return

        kpt = self.model.keypoints[idx]

        # Disable editing of old keypoints
        self.wx.setEnabled(kpt.is_new)
        self.wy.setEnabled(kpt.is_new)

        self.wx.setValue(kpt.world.x)
        self.wy.setValue(kpt.world.y)

        self.use_for_alignment.setEnabled(True)
        self.use_for_alignment.setChecked(kpt.use)

        self.px.setEnabled(kpt.use)
        self.py.setEnabled(kpt.use)

        self.px.setValue(kpt.layer.x)
        self.py.setValue(kpt.layer.y)

    def updateConstraintLabel(self):
        cs = self.model.constraint_info

        if cs == CONS_UNCONSTRAINED:
            self.constraint_status_lbl.setText("Image is unconstrained. Will not be aligned in world space. " +
                                               "This is probably not what you want")
        elif cs == CONS_TRANSLATION:
            self.constraint_status_lbl.setText("Image is constrained only by one keypoint. This will only position " +
                                               "the image in space, but not provide scale or alignment information. " +
                                               "This is probably not what you want")
        elif cs == CONS_ROTATE_SCALE:
            self.constraint_status_lbl.setText("Image is constrained by two keypoints. This will only position, " +
                                               "proportionally scale and rotate the image. That may be OK for " +
                                               "scanned images")
        elif cs == CONS_ORTHOGONAL:
            self.constraint_status_lbl.setText("Image is constrained by three keypoints. This allows alignment of " +
                                               "scale, rotation, translation and shear. This is probably not what " +
                                               "you want, but may be useful for synthetically transformed images")
        elif cs == CONS_PERSPECTIVE:
            self.constraint_status_lbl.setText("Image is constrained by four keypoints. This allows for full recovery" +
                                               " of the perspective transform. This is probably what you want " +
                                               "for camera imagery.")
        elif cs == CONS_SINGULAR:
            self.constraint_status_lbl.setText("Can't solve for these constraints. Are keypoints overlapping or "+
                                               "colinear in either world or image space?")
        elif cs == CONS_OVERCONSTRAINED:
            self.constraint_status_lbl.setText("Too many constraints to solve for. " +
                                               "Max 4 enabled keypoints for alignment.")










