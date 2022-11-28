import math
import time
from collections import defaultdict
from typing import List, Set, Any, Optional, TYPE_CHECKING, Sequence, cast, Callable

import OpenGL.GL as GL  # type: ignore
import numpy
from OpenGL.arrays.vbo import VBO  # type: ignore
from qtpy import QtOpenGL, QtCore, QtWidgets, QtGui

import pcbre.matrix as M
from pcbre.matrix import scale, translate, Point2, project_point, Vec2
from pcbre.model.artwork_geom import Trace, Geom
from pcbre.model.const import SIDE
from pcbre.model.stackup import Layer, ViaPair
from pcbre.ui.gl.glshared import GLShared
from pcbre.ui.tool_action import MoveEvent, ToolActionEvent, EventID, Modifier
from pcbre.util import Timer
from pcbre.view.cachedpolygonrenderer import PolygonRenderer
from pcbre.view.cad_cache import CADCache, StackupRenderCommands, SelectionHighlightCache
from pcbre.view.debugrender import DebugRender
from pcbre.view.hairlinerenderer import HairlineRenderer
from pcbre.view.imageview import ImageView
from pcbre.view.layer_render_target import CompositeManager
from pcbre.view.target_const import COL_LAYER_MAIN, COL_CMP_LINE, COL_SEL
from pcbre.view.traceview import TraceRender
from pcbre.view.viaview import THRenderer
from pcbre.view.viewport import ViewPort

# from pcbre.view.componentview import DIPRender, SMDRender, PassiveRender

if TYPE_CHECKING:
    from pcbre.ui.tools.basetool import BaseToolController
    from pcbre.model.project import Project
    from pcbre.model.imagelayer import ImageLayer
    from mypy_extensions import VarArg

MODE_CAD = 0
MODE_TRACE = 1

EVT_START_FIELD_DRAG = 0
EVT_STOP_FIELD_DRAG = 1


def QPoint_to_point(p: QtCore.QPoint) -> Point2:
    return Point2(p.x(), p.y())


def getSelectColor(c: Sequence[float], selected: bool):
    if not selected:
        return c

    r, g, b = c

    r *= 1.5
    g *= 1.5
    b *= 1.5

    return (r, g, b)




class MoveDragHandler:
    def __init__(self, vs: 'ViewPort', start: Point2):
        self.vs = vs
        self.last = start

    def move(self, cur: Point2) -> None:
        lx, ly = project_point(self.vs.revMatrix, self.last)
        nx, ny = project_point(self.vs.revMatrix, cur)

        self.vs.translate(Vec2(nx - lx, ny - ly))

        self.last = cur

    def done(self) -> None:
        pass


class BaseViewWidget(QtOpenGL.QGLWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super(BaseViewWidget, self).__init__(parent)
        if hasattr(QtOpenGL.QGLFormat, 'setVersion'):
            f = QtOpenGL.QGLFormat()
            f.setVersion(3, 2)
            f.setProfile(QtOpenGL.QGLFormat.CoreProfile)
            c = QtOpenGL.QGLContext(f)
            QtOpenGL.QGLWidget.__init__(self, c, parent)
        else:
            QtOpenGL.QGLWidget.__init__(self, parent)

        self.__gl_initialized = False

        self.viewState = ViewPort(self.width(), self.height())
        self.viewState.changed.connect(self.update)

        self.lastPoint = QtCore.QPoint(0, 0)
        # Nav Handling
        self.active_drag = None

        self.mouse_wheel_emu = None

        self.action_log_cb: 'Optional[Callable[[VarArg(Any)], None]]' = None
        self.interactionDelegate = None
        self.setMouseTracking(True)

        # TODO refine type
        self.selectionList: Set[Any] = set()

        self.open_time = time.time()

        # OpenGL shared resources object. Initialized during initializeGL
        self.gls = GLShared()

        #
        self.local_actions_map = {
            (EventID.Mouse_B2_DragStart, Modifier(0)): EVT_START_FIELD_DRAG,
            (EventID.Mouse_B2, Modifier(0)): EVT_STOP_FIELD_DRAG,
        }

        self.id_actions_map = {}
        self.notify_changed_actions = []

    def internal_event(self, action_event: ToolActionEvent) -> None:
        if action_event.code == EVT_START_FIELD_DRAG:
            self.active_drag = MoveDragHandler(self.viewState, action_event.cursor_pos)
        elif action_event.code == EVT_STOP_FIELD_DRAG:
            self.active_drag = None

    def _log_action(self, *args: Any) -> None:
        if self.action_log_cb is not None:
            self.action_log_cb(*args)

    def dispatchActionEvent(self, point: QtCore.QPoint, event_id: int, modifiers: Modifier, amount: int = 1) -> bool:
        key = (event_id, modifiers)

        if key in self.local_actions_map:
            code = self.local_actions_map[key]
            cb = self.internal_event
            self._log_action(key, "local")

        elif key in self.id_actions_map:
            if self.interactionDelegate is None:
                self._log_action(key, "noid")
                return False

            self._log_action(key, "delegate", self.id_actions_map[key].description)
            code = self.id_actions_map[key].event_code
            cb = self.interactionDelegate.tool_event
        else:
            self._log_action(key, "unhandled")
            return False

        pt = QPoint_to_point(point)
        w_pt = self.viewState.tfV2W(pt)

        event = ToolActionEvent(code, pt, w_pt, amount)

        cb(event)
        return True

    def eventFilter(self, target: Any, qevent: QtCore.QEvent) -> bool:
        if self.interactionDelegate is None:
            return False

        if qevent.type() == QtCore.QEvent.KeyPress:
            q_key_event = cast(QtGui.QKeyEvent, qevent)
            event_id = EventID.from_key_event(q_key_event)
            modifiers = Modifier.from_qevent(qevent)

            ate_event = self.dispatchActionEvent(self.lastPoint, event_id, modifiers)
            if ate_event:
                self.update()

            return ate_event

        return False

    def setSelectionList(self, l: Optional[Sequence[Geom]]) -> None:
        old = self.selectionList
        if l is None:
            self.selectionList = set()
        else:
            self.selectionList = set(l)

        if old != self.selectionList:
            self.update()

    def setInteractionDelegate(self, ed: 'BaseToolController') -> None:
        self.selectionList = set()

        if self.interactionDelegate == ed:
            return

        if self.interactionDelegate:
            self.interactionDelegate.finalize()

        # Build a map of internal event IDs to actions on the delegate
        self.id_actions_map = {}
        for action in ed.tool_actions:
            # TODO: customized shortcuts
            for shortcut in action.default_shortcuts:
                self.id_actions_map[(shortcut.evtid, shortcut.modifiers)] = action

        for notify_changed in self.notify_changed_actions:
            notify_changed()

        self.interactionDelegate = ed
        ed.initialize()

        # If we have an overlay, GLinit it only if we've initialized shared state
        # If we haven't, self.initializeGL will be called anyways before render, which will end up calling
        # overlay.initializeGL
        if ed.overlay is not None and self.gls:
            self.makeCurrent()
            ed.overlay.initializeGL(self.gls)

        self.update()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        self.lastPoint = event.pos()

        event_id = EventID.from_mouse_event(event)
        modifiers = Modifier.from_qevent(event)

        self.dispatchActionEvent(event.pos(), event_id, modifiers)

        self.update()

    def mouseMoveEvent(self, qevent: QtGui.QMouseEvent) -> None:
        self.lastPoint = qevent.pos()

        if self.active_drag:
            self.active_drag.move(QPoint_to_point(qevent.pos()))

        elif self.active_drag is None and not self.mouse_wheel_emu:
            if self.interactionDelegate is not None:

                pos = QPoint_to_point(qevent.pos())

                # TODO - revisit behaviour?
                potential_actions = []
                for (event_id, modifiers), act in self.id_actions_map.items():
                    if event_id.mouse_triggered():
                        potential_actions.append(act)

                event = MoveEvent(
                    pos,
                    self.viewState.tfV2W(pos),
                    potential_actions)

                self.interactionDelegate.mouseMoveEvent(event)

        self.update()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        event_id = EventID.from_mouse_event(event)
        modifiers = Modifier.from_qevent(event)

        self.dispatchActionEvent(event.pos(), event_id, modifiers)

        self.update()

    def zoom(self, step: int, around_point: Point2) -> None:
        sf = 1.1 ** step
        self.viewState.zoom_at(around_point, sf)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        cpt = QPoint_to_point(event.pos())

        if not event.modifiers():
            step = event.angleDelta().y() / 120.0
            self.zoom(step, cpt)
        else:
            if self.interactionDelegate:
                step = event.angleDelta().y() / 120.0
                if step < 0:
                    step = - step
                    code = EventID.Mouse_WheelDown
                else:
                    code = EventID.Mouse_WheelUp

                self.dispatchActionEvent(event.pos(), code, Modifier.from_qevent(event), step)


        self.update()

    def initializeGL(self) -> None:
        assert not self.__gl_initialized

        self.__gl_initialized = True

        GL.glClearColor(0, 0, 0, 1)

        self.gls.initializeGL()
        GL.glGetError()

        GL.glEnable(GL.GL_BLEND)

        # Additive Blending
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE)

        self.reinit()

        if self.interactionDelegate is not None and self.interactionDelegate.overlay is not None:
            self.interactionDelegate.overlay.initializeGL(self.gls)
            pass

    def reinit(self) -> None:
        pass

    def paintGL(self) -> None:
        if not self.__gl_initialized:
            self.initializeGL()

        GL.glClear(GL.GL_COLOR_BUFFER_BIT, GL.GL_DEPTH_BUFFER_BIT)

        self.render()

    def render_tool(self) -> None:
        if self.interactionDelegate and self.interactionDelegate.overlay:
            self.interactionDelegate.overlay.render(self.viewState, self.compositor)

    def resizeGL(self, width: int, height: int) -> None:
        if width == 0 or height == 0:
            return

        size = max(width, height)

        GL.glViewport((width - size) // 2, (height - size) // 2, size, size)
        self.viewState.resize(width, height)

    def isModified(self) -> bool:
        return self.modified


class BoardViewState(QtCore.QObject):
    changed = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()

        self.__current_layer = None
        self.__render_mode = MODE_CAD
        self.__show_images = True
        self.__show_trace_mode_geom = True
        self.per_layer_permute = defaultdict(lambda: 0)

    def permute_layer_order(self) -> None:
        if self.__current_layer is not None:
            self.per_layer_permute[self.__current_layer] += 1

        self.changed.emit()

    @property
    def show_trace_mode_geom(self) -> bool:
        return self.__show_trace_mode_geom

    @show_trace_mode_geom.setter
    def show_trace_mode_geom(self, value: bool) -> None:
        old = self.__show_trace_mode_geom
        self.__show_trace_mode_geom = value
        if old != value:
            self.changed.emit()

    @property
    def current_layer(self) -> Layer:
        return self.__current_layer

    @current_layer.setter
    def current_layer(self, value: Layer) -> None:
        assert value is None or isinstance(value, Layer)
        old = self.__current_layer
        self.__current_layer = value

        if old != self.__current_layer:
            self.changed.emit()

    @property
    def show_images(self) -> bool:
        return self.__show_images

    @show_images.setter
    def show_images(self, value: bool) -> None:
        issue_update = value != self.__show_images

        self.__show_images = value
        self.changed.emit()

        if issue_update:
            self.changed.emit()

    @property
    def render_mode(self):
        return self.__render_mode

    @render_mode.setter
    def render_mode(self, value) -> None:
        issue_update = value != self.__render_mode
        self.__render_mode = value

        if issue_update:
            self.changed.emit()

class BoardViewWidget(BaseViewWidget):
    def __init__(self, project: 'Project') -> None:
        BaseViewWidget.__init__(self)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.project = project

        self.image_view_cache = {}

        self.compositor = CompositeManager()

        self.trace_renderer = TraceRender(self)
        self.via_renderer = THRenderer(self)
        self.hairline_renderer = HairlineRenderer(self)

        self.debug_renderer = DebugRender(self)

        self.render_commands = StackupRenderCommands()
        self.__cad_cache = CADCache(self.project)
        self.__sel_cache = SelectionHighlightCache(self.project)

        self.poly_renderer = PolygonRenderer(self)

        # Initial view is a normalized 1-1-1 area.
        # Shift to be 10cm max
        self.viewState.set_scale(1./100000)

        self.boardViewState = BoardViewState()
        self.boardViewState.changed.connect(self.update)

        self.__check_current_layer()
        self.project.stackup.changed.connect(self.__check_current_layer)

    def __check_current_layer(self):
        current_layer = self.boardViewState.current_layer

        # If currently selected layer has been deleted
        if current_layer is not None and current_layer not in self.project.stackup.layers:
                current_layer = None

        # Force select the first layer if the project has more than one layer
        if current_layer is None and len(self.project.stackup.layers) != 0:
            current_layer = self.project.stackup.top_layer

        self.boardViewState.current_layer = current_layer

    def resizeGL(self, width: int, height: int) -> None:
        super(BoardViewWidget, self).resizeGL(width, height)

        self.compositor.resize(width, height)

    def text_color(self) -> List[float]:
        return [1, 1, 1]

    def current_layer_hack(self) -> 'Layer':
        return self.boardViewState.current_layer

    def color_for_pad(self, pad) -> List[float]:
        if pad.th_diam != 0:
            return [0.5, 0.5, 0.5]

        return self.color_for_layer(pad.layer)

    def color_for_trace(self, trace: Trace) -> List[float]:
        return self.color_for_layer(trace.layer)

    def color_for_layer(self, layer: Layer) -> List[float]:
        return list(layer.color)

    def sel_colormod(self, t: bool, oldcolor: List[float]) -> List[float]:
        if t:
            return [1, 1, 1, 1]
        return oldcolor

    def image_view_cache_load(self, il: 'ImageLayer') -> ImageView:
        key = id(il)
        if key not in self.image_view_cache:
            iv = ImageView(il)
            iv.initGL(self.gls)
            self.image_view_cache[key] = iv

        return self.image_view_cache[key]

    def reinit(self) -> None:
        self.trace_renderer.initializeGL(self.gls)
        self.via_renderer.initializeGL(self.gls)
        self.poly_renderer.initializeGL()
        self.hairline_renderer.initializeGL()
        self.debug_renderer.initializeGL(self.gls)

        self.compositor.initializeGL(self.gls, self.width(), self.height())

        for i in list(self.image_view_cache.values()):
            i.initGL()

    def current_side(self) -> None:
        side = self.project.stackup.side_for_layer(self.boardViewState.current_layer)
        return side

    def vp_is_visible(self, via_pair: ViaPair) -> bool:
        if self.boardViewState.current_layer is None:
            return False

        if self.boardViewState.render_mode == MODE_CAD:
            return True
        else:
            # In layer mode, viapair is visible if we're on any layer
            layer = self.boardViewState.current_layer
            f, s = via_pair.layers
            return f.order <= layer.order <= s.order

    def get_visible_point_cloud(self) -> List[Vec2]:
        bboxes = [i.bbox for i in self.getVisible()]
        points = []

        # Create points from the AABB corners of geometry
        # TODO: stop using AABB details, use convex hull points
        for bb in bboxes:
            points.append(bb.tl)
            points.append(bb.tr)
            points.append(bb.bl)
            points.append(bb.br)

        if self.boardViewState.render_mode == MODE_TRACE and self.boardViewState.show_images and len(self.boardViewState.current_layer.imagelayers) > 0:
            for i in self.boardViewState.current_layer.imagelayers:
                points.extend(i.get_corner_points())

        if not points:
            return

        return points

    def getVisible(self) -> Sequence[Geom]:
        objects = []

        if self.boardViewState.render_mode == MODE_CAD and not self.boardViewState.show_trace_mode_geom:
            return

        # Add visible vias
        vp_visible = {}
        for i in self.project.stackup.via_pairs:
            vp_visible[i] = self.vp_is_visible(i)

        for via in self.project.artwork.vias:
            if vp_visible[via.viapair]:
                objects.append(via)

        # Traces
        for trace in self.project.artwork.traces:
            if self.layer_visible(trace.layer):
                objects.append(trace)

        for polygon in self.project.artwork.polygons:
            if self.layer_visible(polygon.layer):
                objects.append(polygon)

        if self.boardViewState.render_mode == MODE_CAD:
            objects.extend(self.project.artwork.components)
            for cmp in self.project.artwork.components:
                objects.extend(cmp.get_pads())
        elif self.boardViewState.current_layer is None:
            pass
        else:
            cur_side = self.current_side()
            for cmp in self.project.artwork.components:
                if cmp.side == cur_side:
                    objects.append(cmp)

                for pad in cmp.get_pads():
                    if pad.is_through():
                        objects.append(pad)
                    elif pad.side == cur_side:
                        objects.append(pad)

        # TODO: Airwires are always visible
        objects += self.project.artwork.airwires

        return objects

    def _layer_visible(self, l: Layer) -> bool:
        if self.boardViewState.render_mode == MODE_CAD:
            return True
        else:
            return l is self.boardViewState.current_layer

    def layer_visible(self, l: Layer) -> bool:
        return self.__layer_visible_lut[l.number]

    def layer_visible_m(self, l: Layer) -> bool:
        return self.boardViewState.current_layer in l

    def query_point(self, pt: Point2) -> Optional[Geom]:
        # todo: don't use this function anywhere, or introduce some picking heuristic
        all_aw = self.query_point_multiple(pt)
        if not all_aw:
            return None

        # Return an arbitrary element
        return all_aw.pop()

    def query_point_multiple(self, pt: Point2) -> Sequence[Geom]:
        all_aw = set(self.project.artwork.query_point_multiple(pt))

        l_vis_aw = self.getVisible()
        if l_vis_aw is None:
            return

        vis_aw = set(self.getVisible())
        return vis_aw.intersection(all_aw)

    def __render_top_half(self) -> None:
        """
        :return:
        """

        # Forcibly init all layers
        for l in self.project.stackup.layers:
            self.render_commands.layers[l]

        for v in self.project.stackup.via_pairs:
            self.render_commands.vias[v]

        self.render_commands.clear()

        # Update CAD cache
        self.__cad_cache.update_if_necessary()
        self.__cad_cache.extendTo(self.render_commands)

        # Update Selection cache
        self.__sel_cache.update_if_necessary(self.selectionList)

        # Render all artwork that renders to an individual layer
        # Component pads are rendered into either traces or polygons
        for k, v in self.render_commands.layers.items():
            GL.glPushDebugGroup(GL.GL_DEBUG_SOURCE_APPLICATION, 0, -1, "Layer %r" % k)
            with self.compositor.get(k):
                self.trace_renderer.render_va(v.va_traces, self.viewState.glMatrix, COL_LAYER_MAIN)
                self.poly_renderer.render_prepare(self.__cad_cache.polygon_cache_for_layer(k))
                self.poly_renderer.render_solid(self.viewState.glMatrix, COL_LAYER_MAIN)
            GL.glPopDebugGroup()

                # TODO: Render Text

        # Render all viapairs into via layers
        for k, v in self.render_commands.vias.items():
            GL.glPushDebugGroup(GL.GL_DEBUG_SOURCE_APPLICATION, 0, -1, "ViaPair %r" % k)
            with self.compositor.get(k):
                self.via_renderer.render_filled(self.viewState.glMatrix, v.va_vias)
            GL.glPopDebugGroup()

        # Render multilayer components onto the MULTI layer
        GL.glPushDebugGroup(GL.GL_DEBUG_SOURCE_APPLICATION, 0, -1, "Multi Cmp")
        with self.compositor.get("MULTI"):
            self.via_renderer.render_filled(self.viewState.glMatrix, self.render_commands.multi.va_vias)
            # TODO: Render text
        GL.glPopDebugGroup()

        # Draw the front and back sides to the side art
        for k, v in self.render_commands.sides.items():
            GL.glPushDebugGroup(GL.GL_DEBUG_SOURCE_APPLICATION, 0, -1, "Cmp %r" % k)
            with self.compositor.get(("LINEART", k)):
                self.hairline_renderer.render_va(self.viewState.glMatrix, v.va_outlines, COL_CMP_LINE)
                # TODO: Render text
            GL.glPopDebugGroup()

        # Just create (don't actually bind) the overlay/selection layer
        # TODO - All selection logic should probably move to the Select tool
        GL.glPushDebugGroup(GL.GL_DEBUG_SOURCE_APPLICATION, 1, -1, "Overlay")
        with self.compositor.get("OVERLAY"):
            self.hairline_renderer.render_va(self.viewState.glMatrix, self.__cad_cache.airwire_va, COL_SEL)
            self.hairline_renderer.render_va(self.viewState.glMatrix, self.__sel_cache.thinline_va, COL_SEL)
            self.trace_renderer.render_va(self.__sel_cache.thickline_va, self.viewState.glMatrix, COL_SEL)
            self.via_renderer.render_filled(self.viewState.glMatrix, self.__sel_cache.via_va, COL_SEL)

            self.poly_renderer.render_prepare(self.__sel_cache.polygon_cache)
            self.poly_renderer.render_solid(self.viewState.glMatrix, COL_SEL)
        GL.glPopDebugGroup()

        # Render the tool layer
        GL.glPushDebugGroup(GL.GL_DEBUG_SOURCE_APPLICATION, 1, -1, "Tool")
        self.render_tool()
        GL.glPopDebugGroup()

    def render_mode_cad(self) -> None:

        # Composite all the layers
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)

        draw_things = []

        # Prepare to draw all the layers
        for i in self.project.stackup.layers:
            if not self.layer_visible(i):
                continue

            draw_things.append((i, self.color_for_layer(i)))

        # and the via pairs
        for i in self.project.stackup.via_pairs:
            if not self.vp_is_visible(i):
                continue

            draw_things.append((i, (255, 0, 255)))

        # Now, sort them based on an order in which layers are drawn from bottom-to-top
        # (unless the board is flipped, in which case, top-to-bottom), followed by the currently selected layer
        # Via pairs are draw immediately _after_ the artwork of the layer

        def layer_key(a):
            lt, _ = a
            if isinstance(lt, Layer):
                a_l = lt
                b = 0
            elif isinstance(lt, ViaPair):
                a_l = lt.layers[0]
                b = 1
            else:
                raise ValueError("Unknown layer key type for %r" % type(a))

            # We always draw the current layer last
            if a_l == self.boardViewState.current_layer:
                a = 1
            else:
                a = -a_l.order

            return (a, b)

        draw_things.sort(key=layer_key)
        draw_things.insert(0, (("LINEART", SIDE.Top), (255, 255, 255)))
        draw_things.append(("MULTI", (255, 255, 255)))
        draw_things.append((("LINEART", SIDE.Bottom), (255, 255, 255)))

        with self.compositor.composite_prebind() as pb:
            for key, color in draw_things:
                pb.composite(key, color)

            pb.composite("OVERLAY", (255, 255, 255))

        return

    def render_mode_trace(self) -> None:

        # Composite all the layers
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)

        layer = self.boardViewState.current_layer
        if layer is None:
            return

        # Draw the imagery
        stackup_layer = self.boardViewState.current_layer

        if stackup_layer is not None and self.boardViewState.show_images and (len(stackup_layer.imagelayers) > 0):
            images = list(stackup_layer.imagelayers)
            i = self.boardViewState.per_layer_permute[self.boardViewState.current_layer] % len(images)
            images_cycled = images[i:] + images[:i]
            for l in images_cycled:
                self.image_view_cache_load(l).render(self.viewState.glMatrix)

        if not self.boardViewState.show_trace_mode_geom:
            return

        with self.compositor.composite_prebind() as pb:

            # Render the traced geometry
            color = self.color_for_layer(layer)
            pb.composite(layer, color)

            # Render any viapairs on this layer
            for via_pair in self.project.stackup.via_pairs:
                if self.vp_is_visible(via_pair):
                    pb.composite(via_pair, (255, 0, 255))

            # Render the line-art
            side = self.project.stackup.side_for_layer(layer)
            pb.composite(("LINEART", side), (255, 255, 255))

            # Multilayer through-holes
            pb.composite("MULTI", (255, 255, 255))

            # And the tool overlay
            pb.composite("OVERLAY", (255, 255, 255))

    def render(self) -> None:
        with Timer() as t_render:
            # Update the layer-visible check
            self.__layer_visible_lut = [self._layer_visible(i) for i in self.project.stackup.layers]

            # zero accuum buffers for restarts
            self.trace_renderer.restart()

            # Update the Compositor
            self.compositor.restart()

            # Fill colors
            self.compositor.set_color_table(
                [
                    (255, 255, 255, 255),  # Color 0 is always the Layer current color (ignored)
                    (255, 255, 255, 255),  # Color of Text
                    (255, 255, 255, 255),  # Color of Selection
                    (128, 128, 128, 255),  # Color of Vias
                    (128, 128, 0, 255),  # Color of Airwires
                    (190, 190, 0, 255),
                ]
            )

            self.__render_top_half()

            if self.boardViewState.render_mode == MODE_CAD:
                # Render layer stack bottom to top
                self.render_mode_cad()

            elif self.boardViewState.render_mode == MODE_TRACE:
                # Render a single layer for maximum contrast
                self.render_mode_trace()

            self.debug_renderer.render()
