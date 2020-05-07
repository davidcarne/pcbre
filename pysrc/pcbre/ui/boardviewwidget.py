from collections import defaultdict
import math
import time
from pcbre.ui.action import MoveEvent, ActionEvent, EventID, Modifier
from qtpy import QtOpenGL
import qtpy.QtCore as QtCore
import qtpy.QtGui as QtGui
import OpenGL.GL as GL
import numpy
from OpenGL.arrays.vbo import VBO
from pcbre import units
from pcbre.accel.vert_array import VA_thickline, VA_xy, VA_tex
from pcbre.matrix import scale, translate, Point2, projectPoint
from pcbre.model.const import SIDE
from pcbre.model.dipcomponent import DIPComponent
from pcbre.model.pad import Pad
from pcbre.model.passivecomponent import Passive2Component, PassiveSymType, Passive2BodyType
from pcbre.model.smd4component import SMD4Component
from pcbre.model.stackup import Layer, ViaPair

from pcbre.ui.gl import vbobind, VAO, Texture
from pcbre.ui.gl.glshared import GLShared
from pcbre.ui.gl.shadercache import ShaderCache
from pcbre.ui.gl.textrender import TextBatcher, TextBatch
from pcbre.ui.tools.airwiretool import AIRWIRE_COLOR
from pcbre.util import Timer
from pcbre.view.cachedpolygonrenderer import PolygonVBOPair, CachedPolygonRenderer
from pcbre.view.cad_cache import CADCache, StackupRenderCommands, SelectionHighlightCache
from pcbre.view.componenttext import ComponentTextBatcher
from pcbre.view.componentview import cmp_border_va
from pcbre.view.debugrender import DebugRender
from pcbre.view.hairlinerenderer import HairlineRenderer
from pcbre.view.imageview import ImageView
from pcbre.view.layer_render_target import RenderLayer, CompositeManager
from pcbre.view.rendersettings import RENDER_OUTLINES, RENDER_STANDARD, RENDER_SELECTED, RENDER_HINT_NORMAL, \
    RENDER_HINT_ONCE
from pcbre.view.target_const import COL_LAYER_MAIN, COL_CMP_LINE, COL_SEL
from pcbre.view.traceview import TraceRender
from pcbre.view.viaview import THRenderer
from pcbre.view.viewport import ViewPort
from pcbre.model.artwork import Via
from pcbre.model.artwork_geom import Trace, Via, Polygon, Airwire
import pcbre.matrix as M
#from pcbre.view.componentview import DIPRender, SMDRender, PassiveRender
from pcbre.ui.gl import VAO, vbobind, glimports as GLI


MODE_CAD = 0
MODE_TRACE = 1
MOVE_MOUSE_BUTTON = QtCore.Qt.RightButton



EVT_START_DRAG = 0

def fixed_center_dot(viewState, m, view_center=None):

    if view_center is None:
        view_center = Point2(viewState.width/2, viewState.height/2)

    world_center = viewState.tfV2W(view_center)

    proj_orig_center = projectPoint(viewState.transform, world_center)

    viewState.transform = viewState.transform.dot(m)

    proj_new_center = projectPoint(viewState.transform, world_center)

    dx = proj_new_center[0] - proj_orig_center[0]
    dy = proj_new_center[1] - proj_orig_center[1]

    viewState.transform = M.translate(-dx, -dy).dot(viewState.transform)


def QPoint_to_pair(p):
    return Point2(p.x(), p.y())

def getSelectColor(c, selected):
    if not selected:
        return c

    r,g,b = c

    r *= 1.5
    g *= 1.5
    b *= 1.5

    return (r,g,b)

class ViewStateO(QtCore.QObject):
    changed = QtCore.Signal()
    currentLayerChanged = QtCore.Signal()

# Full view state for the multilayer view
class ViewState(ViewPort):

    def __init__(self, x, y):
        super(ViewState,self).__init__(x, y)

        self.obj = ViewStateO()
        self.changed = self.obj.changed
        self.currentLayerChanged = self.obj.currentLayerChanged

        self.__current_layer = None
        self.currentLayerChanged.connect(self.changed)
        self.__show_images = True
        self.layer_permute = 0

    def permute_layer_order(self):
        self.layer_permute += 1
        self.changed.emit()

    def rotate(self, angle):
        self.transform = self.transform.dot(M.rotate(math.radians(angle)))

    def flip(self, axis):
        fixed_center_dot(self, M.flip(axis))

    @property
    def current_layer(self):
        return self.__current_layer

    @current_layer.setter
    def current_layer(self, value):
        assert value is None or isinstance(value, Layer)
        old = self.__current_layer
        self.__current_layer = value

        if old != self.__current_layer:
            self.currentLayerChanged.emit()

    @property
    def transform(self):
        mat = self._transform
        mat.flags.writeable = False
        return mat

    @transform.setter
    def transform(self, value):
        old = self._transform
        self._transform = value

        if (old != value).any():
            self.changed.emit()

    @property
    def show_images(self):
        return self.__show_images

    @show_images.setter
    def show_images(self, value):
        self.__show_images = value
        self.changed.emit()


class MoveDragHandler:
    def __init__(self, vs, start):
        self.vs = vs
        self.last = start

    def move(self, cur):
        lx, ly = self.vs.tfV2P(self.last)
        nx, ny = self.vs.tfV2P(cur)

        delta = nx-lx, ny-ly

        self.vs.transform = M.translate(*delta).dot(self.vs.transform)

        self.last = cur

    def done(self):
        pass


class WheelEmulation:
    def __init__(self):
        pass

    def move(self, evt):
        self.cb_move(evt)

    def done(self):
        pass

class BaseViewWidget(QtOpenGL.QGLWidget):
    def __init__(self, parent=None):
        if hasattr(QtOpenGL.QGLFormat, 'setVersion'):
            f = QtOpenGL.QGLFormat();
            f.setVersion(3, 2)
            f.setProfile(QtOpenGL.QGLFormat.CoreProfile)
            c = QtOpenGL.QGLContext(f)
            QtOpenGL.QGLWidget.__init__(self, c, parent)
        else:
            QtOpenGL.QGLWidget.__init__(self, parent)


        self.__gl_initialized = False

        self.viewState = ViewState(self.width(), self.height())

        self.viewState.changed.connect(self.update)


        self.lastPoint = QtCore.QPoint(0,0)
        # Nav Handling
        self.active_drag = None

        self.mouse_wheel_emu = None

        self.action_log_cb = None
        self.interactionDelegate = None
        self.setMouseTracking(True)

        self.selectionList = set()

        self.open_time = time.time()

        # OpenGL shared resources object. Initialized during initializeGL
        self.gls = GLShared()

        #
        self.local_actions_map = {(EventID.Mouse_B2_DragStart, Modifier(0)): EVT_START_DRAG}

        self.id_actions_map = {}


    def internal_event(self, action_event):
        if action_event.code == EVT_START_DRAG:
            self.active_drag = MoveDragHandler(self.viewState, action_event.cursor_pos)

    def _log_action(self, *args):
        if self.action_log_cb is not None:
            self.action_log_cb(*args)

    def dispatchActionEvent(self, point, event_id, modifiers, amount=1):
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
            cb = self.interactionDelegate.event
        else:
            self._log_action(key, "unhandled")
            return False

        pt = Point2(QPoint_to_pair(point))

        w_pt = self.viewState.tfV2W(pt)

        event = ActionEvent(code, pt, w_pt, amount)


        cb(event)
        return True


    def eventFilter(self, target, qevent):
        if self.interactionDelegate is None:
            return False

        if qevent.type() == QtCore.QEvent.KeyPress:
            event_id = EventID.from_key_event(qevent)
            modifiers = Modifier.from_qevent(qevent)
            
            ate_event = self.dispatchActionEvent(self.lastPoint, event_id, modifiers)
            if ate_event:
                self.update()

            return ate_event

        return False


    def setSelectionList(self, l):
        old = self.selectionList
        if l is None:
            self.selectionList = set()
        else:
            self.selectionList = set(l)

        if old != self.selectionList:
            self.update()

    def setInteractionDelegate(self, ed):
        """

        :param ed:
        :type ed: pcbre.ui.tools.basetool.BaseToolController
        """
        self.selectionList = set()

        if self.interactionDelegate == ed:
            return

        if self.interactionDelegate:
            self.interactionDelegate.finalize()

        # Build a map of internal event IDs to actions on the delegate
        self.id_actions_map = {}
        for action in ed.actions:
            # TODO: customized shortcuts
            for shortcut in action.default_shortcuts:
                self.id_actions_map[(shortcut.evtid, shortcut.modifiers)] = action

        self.interactionDelegate = ed
        ed.initialize()

        # If we have an overlay, GLinit it only if we've initialized shared state
        # If we haven't, self.initializeGL will be called anyways before render, which will end up calling
        # overlay.initializeGL
        if ed.overlay is not None and self.gls:
            self.makeCurrent()
            ed.overlay.initializeGL(self.gls)

        self.update()

    def mousePressEvent(self, event):
        self.lastPoint = event.pos()

        #if event.button() == MOVE_MOUSE_BUTTON:
        #    self.active_drag = MoveDragHandler(self.viewState,
        #        Point2(QPoint_to_pair(self.lastPoint)))

        #elif event.button() == QtCore.Qt.MiddleButton:
        #    self.mouse_wheel_emu = QPoint_to_pair(event.pos())

        #elif not self.active_drag and self.mouse_wheel_emu is None:
        #    if self.interactionDelegate is not None:

        event_id = EventID.from_mouse_event(event)
        modifiers = Modifier.from_qevent(event)

        self.dispatchActionEvent(event.pos(), event_id, modifiers)

        self.update()

    def mouseMoveEvent(self, qevent):

        #delta_px = qevent.pos() - self.lastPoint

        #lx, ly = self.viewState.tfV2P(Point2(self.lastPoint))
        #nx, ny = self.viewState.tfV2P(Point2(qevent.pos()))

        #delta = nx-lx, ny-ly

        #self.lastPoint = qevent.pos()



        if self.active_drag:
            self.active_drag.move(Point2(QPoint_to_pair(qevent.pos())))

        #elif qevent.buttons() & QtCore.Qt.MiddleButton and self.mouse_wheel_emu is not None:
        #    self.zoom(-delta_px.y()/6, self.mouse_wheel_emu)

        elif self.active_drag is None and not self.mouse_wheel_emu:
            if self.interactionDelegate is not None:

                pos = Point2(QPoint_to_pair(qevent.pos()))

                event = MoveEvent(
                    pos,
                    self.viewState.tfV2W(pos))

                self.interactionDelegate.mouseMoveEvent(event)
        
        self.update()

    def mouseReleaseEvent(self, event):
        #if event.button() == MOVE_MOUSE_BUTTON and self.active_drag:
        #    self.active_drag.done()
        #    self.active_drag = None

        # Middle mouse button events are mapped to mouse wheel
        #elif event.button() == QtCore.Qt.MiddleButton:
        #    self.mouse_wheel_emu = None
        #    return

        #elif self.mouse_wheel_emu is None and self.active_drag is not None:
        #    if self.interactionDelegate is not None:
        #        pass
        event_id = EventID.from_mouse_event(event)
        modifiers = Modifier.from_qevent(event)

        self.dispatchActionEvent(event.pos(), event_id, modifiers)

        self.update()


    def zoom(self, step, around_point):
        sf = 1.1 ** step
        fixed_center_dot(self.viewState, M.scale(sf), around_point)

    def wheelEvent(self, event):
        """
        :param event:
        :type event: QtGui.MouseWheelEvent
        :return:
        """
        if not event.modifiers():
            step = event.angleDelta().y()/120.0
            cpt = QPoint_to_pair(event.pos())
            self.zoom(step, cpt)
        else:
            if self.interactionDelegate:
                #self.interactionDelegate.mouseWheelEvent(event)
                # FIXME
                pass

        self.update()

    def initializeGL(self):
        assert not self.__gl_initialized

        self.__gl_initialized = True

        GL.glClearColor(0,0,0,1)

        self.gls.initializeGL()
        GL.glGetError()

        GL.glEnable(GL.GL_BLEND)

        # Additive Blending
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE)

        self.reinit()

        if self.interactionDelegate is not None and self.interactionDelegate.overlay is not None:
            self.interactionDelegate.overlay.initializeGL(self.gls)
            pass

    def reinit(self):
        pass

    def paintGL(self):
        if not self.__gl_initialized:
            self.initializeGL()

        GL.glClear(GL.GL_COLOR_BUFFER_BIT, GL.GL_DEPTH_BUFFER_BIT)

        self.render()



    def render_tool(self):
        if self.interactionDelegate and self.interactionDelegate.overlay:
            self.interactionDelegate.overlay.render(self.viewState, self.compositor)



    def resizeGL(self, width, height):
        if width == 0 or height == 0:
            return

        size = max(width, height)

        GL.glViewport((width - size)// 2, (height - size) // 2, size, size)
        self.viewState.resize(width, height)

        # Allocate a new image buffer
        #self.image = NPBackedImage(self.width(), self.height())
        #super(BoardViewWidget, self).resizeEvent(event)

    def isModified(self):
        return self.modified


class BoardViewWidget(BaseViewWidget):
    def __init__(self, project):
        BaseViewWidget.__init__(self)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.project = project

        self.image_view_cache = { }

        self.compositor = CompositeManager()

        self.trace_renderer = TraceRender(self)
        self.via_renderer = THRenderer(self)
        self.hairline_renderer = HairlineRenderer(self)

        self.debug_renderer = DebugRender(self)

        self.render_commands = StackupRenderCommands()
        self.__cad_cache = CADCache(self.project)
        self.__sel_cache = SelectionHighlightCache(self.project)

        # TODO, currently broken
        self.poly_renderer = CachedPolygonRenderer(self)








        # Initial view is a normalized 1-1-1 area.
        # Shift to be 10cm max
        self.viewState.transform = translate(-0.9, -0.9).dot(scale(1./100000))


        self.render_mode = MODE_CAD





    def resizeGL(self, width, height):
        super(BoardViewWidget, self).resizeGL(width, height)

        self.compositor.resize(width, height)

    def text_color(self):
        return [1,1,1]

    def current_layer_hack(self):
        return self.viewState.current_layer

    def color_for_pad(self, pad):
        if pad.th_diam != 0:
            return [0.5, 0.5, 0.5]

        return self.color_for_layer(pad.layer)

    def color_for_trace(self, trace):
        return self.color_for_layer(trace.layer)

    def color_for_layer(self, layer):
        return list(layer.color)

    def sel_colormod(self, t, oldcolor):
        if t:
            return [1,1,1,1]
        return oldcolor



    def image_view_cache_load(self, il):
        key = id(il)
        if key not in self.image_view_cache:
            iv = ImageView(il)
            iv.initGL(self.gls)
            self.image_view_cache[key] = iv

        return self.image_view_cache[key]

    def reinit(self):
        self.trace_renderer.initializeGL(self.gls)
        self.via_renderer.initializeGL(self.gls)
        self.poly_renderer.initializeGL()
        self.hairline_renderer.initializeGL()
        self.debug_renderer.initializeGL(self.gls)

        self.compositor.initializeGL(self.gls, self.width(), self.height())

        for i in list(self.image_view_cache.values()):
            i.initGL()

    def current_side(self):
        side = self.project.stackup.side_for_layer(self.viewState.current_layer)
        return side

    def vp_is_visible(self, via_pair):
        if self.viewState.current_layer is None:
            return False

        if self.render_mode == MODE_CAD:
            return True
        else:
            # In layer mode, viapair is visible if we're on any layer
            layer = self.viewState.current_layer
            f, s = via_pair.layers
            return f.order <= layer.order <= s.order

    def getVisible(self):
        objects = []

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
            if self.layer_visible(polygon):
                objects.append(polygon)

        if self.render_mode == MODE_CAD:
            objects.extend(self.project.artwork.components)
            for cmp in self.project.artwork.components:
                objects.extend(cmp.get_pads())
        elif self.viewState.current_layer is None:
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


    def _layer_visible(self, l):
        if self.render_mode == MODE_CAD:
            return True
        else:
            return l is self.viewState.current_layer

    def layer_visible(self, l):
        return self.__layer_visible_lut[l.number]

    def layer_visible_m(self, l):
        return self.viewState.current_layer in l


    def query_point(self, pt):
        all_aw = self.project.artwork.query_point(pt)

        vis_aw = set(self.getVisible())

        # Todo: return multiple
        if all_aw in vis_aw:
            return all_aw



    def __render_top_half(self):
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

        for k, v in self.render_commands.layers.items():
            with self.compositor.get(k):
                self.trace_renderer.render_va(v.va_traces, self.viewState.glMatrix, COL_LAYER_MAIN)
                # TODO: Render Text

        # Draw all the viapairs
        for k, v in self.render_commands.vias.items():
            with self.compositor.get(k):
                self.via_renderer.render_filled(self.viewState.glMatrix, v.va_vias)

        # Draw the multilayer components
        with self.compositor.get("MULTI"):
            self.via_renderer.render_filled(self.viewState.glMatrix, self.render_commands.multi.va_vias)
            # TODO: Render text

        # Draw the front and back sides
        for k, v in self.render_commands.sides.items():
            with self.compositor.get(("LINEART", k)):
                self.hairline_renderer.render_va(self.viewState.glMatrix, v.va_outlines, COL_CMP_LINE)
                # TODO: Render text


        # Just create (don't actually bind) the overlay layer
        with self.compositor.get("OVERLAY"):
            self.hairline_renderer.render_va(self.viewState.glMatrix, self.__sel_cache.thinline_va, COL_SEL)
            self.trace_renderer.render_va(self.__sel_cache.thickline_va, self.viewState.glMatrix, COL_SEL)
            self.via_renderer.render_filled(self.viewState.glMatrix, self.__sel_cache.via_va, COL_SEL)

        self.render_tool()

    def render_mode_cad(self):

        # Composite all the layers
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)

        draw_things = [ ]


        # Prepare to draw all the layers
        for i in self.project.stackup.layers:
            if not self.layer_visible(i):
                continue

            draw_things.append((i, self.color_for_layer(i)))

        # and the via pairs
        for i in self.project.stackup.via_pairs:
            if not self.vp_is_visible(i):
                continue

            draw_things.append((i, (255,0, 255)))

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

            # We always draw the current layer last
            if a_l == self.viewState.current_layer:
                a = 1
            else:
                a = -a_l.order

            return (a,b)


        draw_things.sort(key=layer_key)
        draw_things.insert(0, (("LINEART", SIDE.Top), (255,255,255)))
        draw_things.append(("MULTI", (255,255,255)))
        draw_things.append((("LINEART", SIDE.Bottom), (255,255,255)))

        with self.compositor.composite_prebind() as pb:
            for key, color in draw_things:
                pb.composite(key, color)

            pb.composite("OVERLAY", (255,255,255))

        return



    def render_mode_trace(self):

        # Composite all the layers
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)

        layer = self.viewState.current_layer
        if layer is None:
            return

        # Draw the imagery
        stackup_layer = self.viewState.current_layer

        if stackup_layer is not None and self.viewState.show_images and (len(stackup_layer.imagelayers) > 0):
            images = list(stackup_layer.imagelayers)
            i = self.viewState.layer_permute % len(images)
            images_cycled = images[i:] + images[:i]
            for l in images_cycled:
                self.image_view_cache_load(l).render(self.viewState.glMatrix)

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
            pb.composite(("LINEART", side), (255,255,255))

            # Multilayer through-holes
            pb.composite("MULTI", (255,255,255))

            # And the tool overlay
            pb.composite("OVERLAY", (255,255,255))


    def render(self):
        with Timer() as t_render:
            # Update the layer-visible check
            self.__layer_visible_lut = [self._layer_visible(i) for i in self.project.stackup.layers]

            # zero accuum buffers for restarts
            self.trace_renderer.restart()
            self.poly_renderer.restart()

            # Update the Compositor
            self.compositor.restart()

            # Fill colors
            self.compositor.set_color_table(
                [
                    (255,255,255,255),  # Color 0 is always the Layer current color (ignored)
                    (255,255,255,255),  # Color of Text
                    (255,255,255,255),  # Color of Selection
                    (128, 128, 128, 255),  # Color of Vias
                    (128,128,0,255),  # Color of Airwires
                    (190, 190, 0, 255),
                ]
            )

            self.__render_top_half()

            if self.render_mode == MODE_CAD:
                # Render layer stack bottom to top
                self.render_mode_cad()

            elif self.render_mode == MODE_TRACE:
                # Render a single layer for maximum contrast
                self.render_mode_trace()

            self.debug_renderer.render()

