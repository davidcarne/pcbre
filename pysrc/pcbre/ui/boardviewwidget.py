from collections import defaultdict
import math
import time

from PySide import QtOpenGL
import PySide.QtCore as QtCore
import PySide.QtGui as QtGui
import OpenGL.GL as GL
import OpenGL.arrays.vbo as VBO
import numpy
from pcbre import units
from pcbre.matrix import scale, translate, Point2, projectPoint
from pcbre.model.const import SIDE
from pcbre.model.dipcomponent import DIPComponent
from pcbre.model.pad import Pad
from pcbre.model.passivecomponent import PassiveComponent, PassiveSymType, PassiveBodyType
from pcbre.model.smd4component import SMD4Component
from pcbre.model.stackup import Layer

from pcbre.ui.gl import vbobind
from pcbre.ui.gl.glshared import GLShared
from pcbre.ui.gl.shadercache import ShaderCache
from pcbre.ui.gl.textrender import TextBatcher
from pcbre.ui.tools.airwiretool import AIRWIRE_COLOR
from pcbre.util import Timer
from pcbre.view.cachedpolygonrenderer import PolygonVBOPair, CachedPolygonRenderer
from pcbre.view.hairlinerenderer import HairlineRenderer
from pcbre.view.imageview import ImageView
from pcbre.view.rendersettings import RENDER_OUTLINES, RENDER_STANDARD, RENDER_SELECTED, RENDER_HINT_NORMAL, \
    RENDER_HINT_ONCE
from pcbre.view.traceview import TraceRender
from pcbre.view.viaview import THRenderer
from pcbre.view.viewport import ViewPort
from pcbre.model.artwork import Via
from pcbre.model.artwork_geom import Trace, Via, Polygon, Airwire
import pcbre.matrix as M
from pcbre.view.componentview import PadRender, DIPRender, SMDRender, PassiveRender


MOVE_MODIFIER_KEY = QtCore.Qt.Key_Space
MOVE_MOUSE_BUTTON = QtCore.Qt.LeftButton


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

# Full view state for the multilayer view
class ViewState(QtCore.QObject, ViewPort):
    changed = QtCore.Signal()
    currentLayerChanged  = QtCore.Signal()

    def __init__(self, x, y):
        ViewPort.__init__(self, x, y)
        QtCore.QObject.__init__(self)

        self.__current_layer = None
        self.currentLayerChanged.connect(self.changed)
        self.__show_images = True
        self.__draw_other_layers = True
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

    @property
    def draw_other_layers(self):
        return self.__draw_other_layers

    @draw_other_layers.setter
    def draw_other_layers(self, value):
        self.__draw_other_layers = value
        self.changed.emit()

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

        self.viewState = ViewState(self.width(), self.height())

        self.viewState.changed.connect(self.update)

        # Nav Handling
        self.move_key_pressed = False
        self.move_dragging = False
        self.move_dragged = False
        self.mwemu = False
        self.lastPoint = None

        self.interactionDelegate = None
        self.setMouseTracking(True)

        self.selectionList = set()

        self.open_time = time.time()

        # OpenGL shared resources object. Initialized during initializeGL
        self.gls = GLShared()



    def eventFilter(self, target, event):
        if self.interactionDelegate is None:
            return False

        if (event.type() == QtCore.QEvent.ShortcutOverride and
                MOVE_MODIFIER_KEY and
                event.key() == MOVE_MODIFIER_KEY):
            self.move_key_pressed = True

        if event.type() == QtCore.QEvent.KeyRelease:
            if MOVE_MODIFIER_KEY and event.key() == MOVE_MODIFIER_KEY:
                self.move_key_pressed = False

            s = self.interactionDelegate.keyReleaseEvent(event)
            self.update()
            return s

        if event.type() == QtCore.QEvent.KeyPress:
            s = self.interactionDelegate.keyPressEvent(event)
            self.update()
            return s

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
            self.interactionDelegate.changed.disconnect(self.update)
            self.interactionDelegate.finalize()

        self.interactionDelegate = ed
        ed.changed.connect(self.update)
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
        self.move_dragged = False

        if (event.button() == MOVE_MOUSE_BUTTON and
                (MOVE_MODIFIER_KEY is None or self.move_key_pressed)):
            self.move_dragging = True
            return

        elif event.button() == QtCore.Qt.MiddleButton:
            self.mwemu = True
            return

        elif not self.move_dragging and not self.mwemu:
            if self.interactionDelegate is not None:
                self.interactionDelegate.mousePressEvent(event)

        self.update()

    def mouseMoveEvent(self, event):
        if self.lastPoint is None:
            self.lastPoint = event.pos()
            return

        delta_px = event.pos() - self.lastPoint
        lastpoint_real = self.viewState.tfV2P(Point2(self.lastPoint))
        newpoint_real = self.viewState.tfV2P(Point2(event.pos()))
        lx,ly = lastpoint_real
        nx,ny = newpoint_real
        delta = nx-lx, ny-ly

        self.lastPoint = event.pos()

        needs_update = False
        if (event.buttons() & MOVE_MOUSE_BUTTON) and self.move_dragging:
            self.move_dragged = True

            self.viewState.transform = M.translate(*delta).dot(self.viewState.transform)
            needs_update = True

        elif (event.buttons() & QtCore.Qt.MiddleButton):
            delta = -10 * delta_px.y()

            self.wheelEvent(QtGui.QWheelEvent(event.pos(),delta, event.buttons(), event.modifiers()))
            needs_update = True
        elif not self.move_dragging and not self.mwemu:
            if self.interactionDelegate is not None:
                self.interactionDelegate.mouseMoveEvent(event)
                needs_update = True

        if needs_update:
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == MOVE_MOUSE_BUTTON and self.move_dragging:
            self.move_dragging = False
            return

        # Middle mouse button events are mapped to mouse wheel
        elif event.button() == QtCore.Qt.MiddleButton:
            self.mwemu = False
            return

        if not self.move_dragged and not self.move_dragging and not self.mwemu:
            if self.interactionDelegate is not None:
                self.interactionDelegate.mouseReleaseEvent(event)

        self.update()


    def wheelEvent(self, event):
        """
        :param event:
        :type event: QtGui.MouseWheelEvent
        :return:
        """
        if not event.modifiers():
            step = event.delta()/120.0

            sf = 1.1 ** step
            fixed_center_dot(self.viewState, M.scale(sf), QPoint_to_pair(event.pos()))
        else:
            if self.interactionDelegate:
                self.interactionDelegate.mouseWheelEvent(event)

    def initializeGL(self):
        GL.glClearColor(0,0,0,1)

        self.gls.initializeGL()
        GL.glGetError()

        GL.glEnable(GL.GL_BLEND)

        # Additive Blending
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE)

        self.reinit()

        if self.interactionDelegate is not None and self.interactionDelegate.overlay is not None:
            self.interactionDelegate.overlay.initializeGL(self.gls)

    def reinit(self):
        pass

    def paintGL(self):
        GL.glClear(GL.GL_COLOR_BUFFER_BIT, GL.GL_DEPTH_BUFFER_BIT)

        self.render()



    def render(self):
        if self.interactionDelegate and self.interactionDelegate.overlay:
            self.interactionDelegate.overlay.render(self.viewState)



    def resizeGL(self, width, height):
        if width == 0 or height == 0:
            return

        GL.glViewport(0, 0, width, height)
        self.viewState.resize(self.width(), self.height())

        # Allocate a new image buffer
        #self.image = NPBackedImage(self.width(), self.height())
        #super(BoardViewWidget, self).resizeEvent(event)

    def isModified(self):
        return self.modified


class BoardViewWidget(BaseViewWidget):
    def __init__(self, project):
        BaseViewWidget.__init__(self)
        self.project = project

        self.image_view_cache = { }

        self.pad_renderer = PadRender(self)
        self.dip_renderer = DIPRender(self)
        self.smd_renderer = SMDRender(self)
        self.trace_renderer = TraceRender(self)
        self.via_renderer = THRenderer(self)
        self.text_batch = TextBatcher(self.gls.text)
        self.poly_renderer = CachedPolygonRenderer(self)
        self.hairline_renderer = HairlineRenderer(self)
        self.passive_renderer = PassiveRender(self)

        # Initial view is a normalized 1-1-1 area.
        # Shift to be 10cm max
        self.viewState.transform = translate(-0.9, -0.9).dot(scale(1./100000))



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
        self.pad_renderer.initializeGL(self, self.gls)
        self.dip_renderer.initializeGL(self.gls)
        self.smd_renderer.initializeGL(self.gls)
        self.trace_renderer.initializeGL(self.gls)
        self.via_renderer.initializeGL(self.gls)
        self.text_batch.initializeGL()
        self.poly_renderer.initializeGL()
        self.hairline_renderer.initializeGL()

        for i in list(self.image_view_cache.values()):
            i.initGL()

    def getVisibleArtwork(self):
        objects = []
        objects += self.project.artwork.vias
        objects += self.project.artwork.traces
        objects += self.project.artwork.polygons
        objects += self.project.artwork.airwires
        return objects


    def render_component(self, mat, cmp, render_mode=RENDER_STANDARD, render_hint=RENDER_HINT_NORMAL):
        if not self.layer_visible_m(cmp.on_layers()):
            return

        if isinstance(cmp, DIPComponent):
            self.dip_renderer.render(mat, cmp, render_mode, render_hint)
        elif isinstance(cmp, SMD4Component):
            self.smd_renderer.render(mat, cmp, render_mode, render_hint)
        elif isinstance(cmp, PassiveComponent):
            self.passive_renderer.render(mat, cmp, render_mode, render_hint)
        else:
            pass
            #raise TypeError("Can't render %s" % cmp)

        cm = mat.dot(cmp.matrix)

        for pad in cmp.get_pads():
            pad_render_mode = render_mode
            if not pad.is_through() and not self.layer_visible(pad.layer):
                continue

            if pad in self.selectionList:
                pad_render_mode |= RENDER_SELECTED
            self.pad_renderer.render(cm, pad, pad_render_mode, render_hint)


    def layer_visible(self, l):
        return l is self.viewState.current_layer or self.viewState.draw_other_layers

    def layer_visible_m(self, l):
        return self.viewState.current_layer in l or self.viewState.draw_other_layers

    def render(self):
        t_render_start = time.time()

        # zero accuum buffers for restarts
        self.trace_renderer.restart()
        self.via_renderer.restart()
        self.text_batch.restart()
        self.poly_renderer.restart()
        self.hairline_renderer.restart()

        stackup_layer = self.viewState.current_layer
        if stackup_layer is None:
            return

        # Render all images down onto the layer
        with Timer() as il_timer:
            if self.viewState.show_images:
                images = list(stackup_layer.imagelayers)
                i = self.viewState.layer_permute % len(images)
                images_cycled = images[i:] + images[:i]
                for l in images_cycled:
                    self.image_view_cache_load(l).render(self.viewState.glMatrix)

        # Now render features
        self.lt = time.time()


        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)

        artwork = self.getVisibleArtwork()

        # Build rendering batches
        with Timer() as t_aw:
            for i in artwork:
                rs = RENDER_SELECTED if i in self.selectionList else 0

                if isinstance(i, Trace):
                    if self.layer_visible(i.layer):
                        self.trace_renderer.deferred(i, rs, RENDER_HINT_NORMAL)
                elif isinstance(i, Via):
                    if self.layer_visible_m(i.viapair.all_layers):
                        self.via_renderer.deferred(i.pt, i.r, 0, rs, RENDER_HINT_NORMAL)
                elif isinstance(i, Polygon):
                    if self.layer_visible(i.layer):
                        self.poly_renderer.deferred(i, rs, RENDER_HINT_NORMAL)
                elif isinstance(i, Airwire):
                    self.hairline_renderer.deferred(i.p0, i.p1, AIRWIRE_COLOR, None, RENDER_HINT_NORMAL)
                else:
                    raise NotImplementedError()


        with Timer() as cmp_timer:
            for cmp in self.project.artwork.components:
                render_state = 0
                if cmp in self.selectionList:
                    render_state |= RENDER_SELECTED
                self.render_component(self.viewState.glMatrix, cmp, render_state)

        with Timer() as other_timer:
            super(BoardViewWidget, self).render()

        def ly_order_func(layer):
            # We always draw the current layer last
            if layer is self.viewState.current_layer:
                return 1

            return -layer.order

        with Timer() as t:
            # Draw all the layers
            layers = sorted(self.project.stackup.layers, key=ly_order_func)
            for layer in layers:
                self.trace_renderer.render_deferred_layer(self.viewState.glMatrix, layer)
                self.poly_renderer.render(self.viewState.glMatrix, layer)
                self.text_batch.render(key=layer)
                self.hairline_renderer.render_group(self.viewState.glMatrix, layer)

            self.via_renderer.render(self.viewState.glMatrix)

            # Render the non-layer text
            self.text_batch.render()
            self.hairline_renderer.render_group(self.viewState.glMatrix, None)

            self.hairline_renderer.render_group(self.viewState.glWMatrix, "OVERLAY_VS")
            #self.hairline_renderer.render_group(self.viewState.glMatrix, "OVERLAY_VS")

            GL.glFinish()

        all_time = time.time() - t_render_start
        print("Render time all: %f ot: %f cmp: %f aw: %f gl: %f" % (all_time, other_timer.interval, cmp_timer.interval, t_aw.interval, t.interval))



