from collections import defaultdict
from pcbre.accel.vert_array import VA_via
from pcbre.model.artwork_geom import Via
from pcbre.model.component import Component
from pcbre.model.pad import Pad
from pcbre.view.rendersettings import RENDER_SELECTED, RENDER_OUTLINES, RENDER_HINT_NORMAL
import weakref
from pcbre.view.target_const import COL_VIA, COL_SEL, COL_CMP_LINE

__author__ = 'davidc'
import math
from OpenGL import GL
from OpenGL.arrays.vbo import VBO
import numpy
from pcbre import units
from pcbre.matrix import Rect, translate, rotate, Point2, scale, Vec2
from pcbre.ui.gl import VAO, vbobind, glimports as GLI
import ctypes

N_OUTLINE_SEGMENTS = 100

class ViaBatch:
    def __init__(self):
        self.nonsel = VA_via(1024)
        self.sel = VA_via(1024)

class ViaBoardBatcher:
    """
    The ViaBoardBatcher manages via draw batches (per-layer). It automatically updates the draw batches on-demand and
    only when necessary
    """
    def __init__(self, via_renderer, project):
        self.project = project
        self.renderer = via_renderer
        self.__batch_for_vp = defaultdict(ViaBatch)

        self.__selected_set = set()
        self.__last_via_generation = None
        self.__last_component_generation = None

    def update_if_necessary(self, selection_list):

        # Evaluate if we need to redraw
        ok = True

        # Todo: check via_pairs the same

        if self.__last_via_generation != self.project.artwork.vias_generation:
            ok = False

        via_sel_list = set(i for i in selection_list if isinstance(i, (Pad, Via, Component)))

        if via_sel_list != self.__selected_set:
            ok = False

        if self.__last_component_generation != self.project.artwork.components_generation:
            ok = False

        if ok:
            return

        self.__last_via_generation = self.project.artwork.vias_generation
        self.__last_component_generation = self.project.artwork.components_generation
        self.__selected_set = via_sel_list

        # Clear the batches and create a new batch<->viapair mapping
        self.__batch_for_vp.clear()

        # Batch vias by viapair
        for via in self.project.artwork.vias:
            vpb = self.__batch_for_vp[via.viapair]
            if via in via_sel_list:
                dest = vpb.sel
            else:
                dest = vpb.nonsel

            dest.add_via(via)


        # TODO MOVE
        component_batch = self.__batch_for_vp["CMP"]

        for component in self.project.artwork.components:

            for pad in component.get_pads():
                if component in selection_list or pad in selection_list:
                    dest = component_batch.sel
                else:
                    dest = component_batch.nonsel
                if pad.is_through():
                    dest.add_donut(pad.center.x, pad.center.y, pad.w/2, pad.th_diam/2)



    def render_viapair(self, mat, viapair):
        self.renderer._render_filled(mat, self.__batch_for_vp[viapair])

    def render_component_pads(self, mat):
        self.renderer._render_filled(mat, self.__batch_for_vp["CMP"])


class THRenderer:
    def __init__(self, parent_view):
        self.parent = parent_view
        self.__batches = weakref.WeakSet()

    def batch(self):
        batch = _THBatch(self)
        self.__batches.add(batch)
        return batch

    def initializeGL(self, glshared):

        self._filled_shader = glshared.shader_cache.get(
            "via_filled_vertex_shader", "via_filled_fragment_shader")

        self._outline_shader = glshared.shader_cache.get(
            "via_outline_vertex_shader", "frag1"
        )

        # Build geometry for filled rendering using the frag shader for circle borders
        filled_points = [
            ((-1, -1), ),
            ((1, -1), ),
            ((-1, 1), ),
            ((1,  1), ),
        ]
        ar = numpy.array(
            filled_points, dtype=[("vertex", numpy.float32, 2)])

        self._sq_vbo = VBO(ar, GL.GL_STATIC_DRAW)


        # Build geometry for outline rendering
        outline_points = []
        for i in numpy.linspace(0, math.pi * 2, N_OUTLINE_SEGMENTS, False):
            outline_points.append(((math.cos(i), math.sin(i)), ))

        outline_points_array = numpy.array(
            outline_points, dtype=[("vertex", numpy.float32, 2)])

        self._outline_vbo = VBO(outline_points_array, GL.GL_STATIC_DRAW)

        self._filled_instance_dtype = numpy.dtype([
            ("pos", numpy.float32, 2),
            ("r", numpy.float32, 1),
            ("r_inside_frac_sq", numpy.float32, 1),
        ])

        self._outline_instance_dtype = numpy.dtype([
            ("pos", numpy.float32, 2),
            ("r", numpy.float32, 1),
        ])


        self.__filled_vao = VAO()
        self.__outline_vao = VAO()

        with self.__filled_vao, self._sq_vbo:
            vbobind(self._filled_shader, self._sq_vbo.data.dtype, "vertex").assign()

        # Use a fake array to get a zero-length VBO for initial binding
        filled_instance_array = numpy.ndarray(0, dtype=self._filled_instance_dtype)
        self.filled_instance_vbo = VBO(filled_instance_array)

        with self.__filled_vao, self.filled_instance_vbo:
            vbobind(self._filled_shader, self._filled_instance_dtype, "pos", div=1).assign()
            vbobind(self._filled_shader, self._filled_instance_dtype, "r", div=1).assign()
            vbobind(self._filled_shader, self._filled_instance_dtype, "r_inside_frac_sq", div=1).assign()

        with self.__outline_vao, self._outline_vbo:
            vbobind(self._outline_shader, self._outline_vbo.data.dtype, "vertex").assign()

        # Build instance for outline rendering
        # We don't have an inner 'r' for this because we just do two instances per vertex

        # Use a fake array to get a zero-length VBO for initial binding
        outline_instance_array = numpy.ndarray(0, dtype=self._outline_instance_dtype)
        self.outline_instance_vbo = VBO(outline_instance_array)

        with self.__outline_vao, self.outline_instance_vbo:
            vbobind(self._outline_shader, self._outline_instance_dtype, "pos", div=1).assign()
            vbobind(self._outline_shader, self._outline_instance_dtype, "r", div=1).assign()

    def _render_filled(self, mat, va):
        filled_count = va.sel.count() + va.nonsel.count()

        if not filled_count:
            return


        filled_selected_start = va.nonsel.count()

        self.filled_instance_vbo.set_array(va.nonsel.buffer()[:] + va.sel.buffer()[:])


        with self._filled_shader, self.__filled_vao, self.filled_instance_vbo, self._sq_vbo:
            GL.glUniformMatrix3fv(self._filled_shader.uniforms.mat, 1, True, mat.ctypes.data_as(GLI.c_float_p))

            if filled_selected_start > 0:
                GL.glUniform1ui(self._filled_shader.uniforms.color, COL_VIA)
                GL.glDrawArraysInstancedBaseInstance(GL.GL_TRIANGLE_STRIP, 0, 4, filled_selected_start, 0)

            if filled_count - filled_selected_start > 0:
                GL.glUniform1ui(self._filled_shader.uniforms.color, COL_SEL)
                GL.glDrawArraysInstancedBaseInstance(GL.GL_TRIANGLE_STRIP, 0, 4,
                                                     filled_count - filled_selected_start, filled_selected_start)

    def render_outline(self, mat, va):
        raise NotImplementedError()

        if not va.count():
            return

        with self._outline_shader, self.__outline_vao, self.outline_instance_vbo, self._sq_vbo:
            GL.glUniformMatrix3fv(self._outline_shader.uniforms.mat, 1, True, mat.ctypes.data_as(GLI.c_float_p))
            GL.glDrawArraysInstanced(GL.GL_LINE_LOOP, 0, N_OUTLINE_SEGMENTS, self.__outline_count)
