from collections import defaultdict
from pcbre.model.artwork_geom import Via
from pcbre.view.rendersettings import RENDER_SELECTED, RENDER_OUTLINES, RENDER_HINT_NORMAL
import weakref

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


class ViaBoardBatcher:
    """
    The ViaBoardBatcher manages via draw batches (per-layer). It automatically updates the draw batches on-demand and
    only when necessary
    """
    def __init__(self, via_renderer, project):
        self.project = project
        self.renderer = via_renderer
        self.batches = []
        self.__batch_for_vp = {}
        self.__selected_set = set()
        self.__last_via_generation = None

    def update_if_necessary(self, selection_list):

        # Evaluate if we need to redraw
        ok = True

        # Todo: check via_pairs the same

        if self.__last_via_generation != self.project.artwork.vias_generation:
            ok = False

        via_sel_list = set(i for i in selection_list if isinstance(i, Via))
        if via_sel_list != self.__selected_set:
            ok = False

        if ok:
            return

        self.__last_via_generation = self.project.artwork.vias_generation
        self.__selected_set = via_sel_list

        # One batch per via_pair
        while len(self.batches) < len(self.project.stackup.via_pairs):
            self.batches.append(self.renderer.batch())

        # Clear the batches and create a new batch<->viapair mapping
        self.__batch_for_vp = {}
        for i, vp in zip(self.batches, self.project.stackup.via_pairs):
            i.restart()
            self.__batch_for_vp[vp] = i

        # Batch vias by viapair
        for via in self.project.artwork.vias:
            self.__batch_for_vp[via.viapair].deferred(via.pt, via.r, 0,
                RENDER_SELECTED if via in via_sel_list else 0, RENDER_HINT_NORMAL)

        for i in self.batches:
            i.prepare()

    def render_viapair(self, mat, viapair):
        self.__batch_for_vp[viapair].render_filled(mat)

class _THBatch:
    def __init__(self, parent):
        self.parent = parent
        self.restart()
        self.initialized = False

    def restart(self):
        self.__deferred_list_filled = []
        self.__deferred_list_outline = []

    def _initializeGL(self):
        self.initialized = True

        self.__filled_vao = VAO()
        self.__outline_vao = VAO()

        with self.__filled_vao, self.parent._sq_vbo:
            vbobind(self.parent._filled_shader, self.parent._sq_vbo.data.dtype, "vertex").assign()

        # Use a fake array to get a zero-length VBO for initial binding
        filled_instance_array = numpy.ndarray(0, dtype=self.parent._filled_instance_dtype)
        self.filled_instance_vbo = VBO(filled_instance_array)

        with self.__filled_vao, self.filled_instance_vbo:
            vbobind(self.parent._filled_shader, self.parent._filled_instance_dtype, "pos", div=1).assign()
            vbobind(self.parent._filled_shader, self.parent._filled_instance_dtype, "r", div=1).assign()
            vbobind(self.parent._filled_shader, self.parent._filled_instance_dtype, "r_inside_frac_sq", div=1).assign()
            vbobind(self.parent._filled_shader, self.parent._filled_instance_dtype, "color", div=1).assign()

        with self.__outline_vao, self.parent._outline_vbo:
            vbobind(self.parent._outline_shader, self.parent._outline_vbo.data.dtype, "vertex").assign()

        # Build instance for outline rendering
        # We don't have an inner 'r' for this because we just do two instances per vertex

        # Use a fake array to get a zero-length VBO for initial binding
        outline_instance_array = numpy.ndarray(0, dtype=self.parent._outline_instance_dtype)
        self.outline_instance_vbo = VBO(outline_instance_array)

        with self.__outline_vao, self.outline_instance_vbo:
            vbobind(self.parent._outline_shader, self.parent._outline_instance_dtype, "pos", div=1).assign()
            vbobind(self.parent._outline_shader, self.parent._outline_instance_dtype, "r", div=1).assign()
            vbobind(self.parent._outline_shader, self.parent._outline_instance_dtype, "color", div=1).assign()

    def deferred(self, center, r1, r2, rs, render_hint=RENDER_HINT_NORMAL):
        if rs & RENDER_OUTLINES:
            self.__deferred_list_outline.append((center, r1, r2, rs))
        else:
            self.__deferred_list_filled.append((center, r1, r2, rs))

    def prepare(self):
        self.__prepare_filled()
        self.__prepare_outline()

    def __prepare_filled(self):
        if not self.initialized:
            self._initializeGL()

        count = len(self.__deferred_list_filled)
        self.__filled_count = count

        if count == 0:
            return

        # Resize instance data array
        instance_array = numpy.ndarray(count, dtype = self.parent._filled_instance_dtype)

        color_a = [0.6, 0.6, 0.6, 1]

        for n, (center, r1, r2, rs) in enumerate(self.__deferred_list_filled):

            # HACK, color object
            color_mod = self.parent.parent.sel_colormod(rs & RENDER_SELECTED, color_a)

            # frag shader uses pythag to determine is frag is within
            # shaded area. Precalculate comparison term
            r_frac_sq = (r2 / r1) ** 2
            instance_array[n] = (center, r1, r_frac_sq, color_mod)

        self.filled_instance_vbo.data = instance_array
        self.filled_instance_vbo.copied = False
        self.filled_instance_vbo.bind()

    def __prepare_outline(self):
        count = 0
        for center, r1, r2, rs in self.__deferred_list_outline:
            if r2 == 0:
                count += 1
            else:
                count += 2

        self.__outline_count = count
        if count == 0:
            return


        # Resize instance data array
        instance_array = numpy.ndarray(count, dtype = self.parent._outline_instance_dtype)

        n = 0
        for center, r1, r2, rs in self.__deferred_list_outline:
            color_a = [0.6, 0.6, 0.6, 1]

            # HACK, color object
            color_a = self.parent.parent.sel_colormod(rs & RENDER_SELECTED, color_a)

            instance_array[n] = (center, r1, color_a)
            n += 1

            if r2 > 0:
                instance_array[n] = (center, r2, color_a)
                n += 1

        self.outline_instance_vbo.data = instance_array
        self.outline_instance_vbo.copied = False
        self.outline_instance_vbo.bind()


    def render(self, mat):
        self.render_filled(mat)
        self.render_outline(mat)

    def render_filled(self, mat):
        if self.__filled_count == 0:
            return

        with self.parent._filled_shader, self.__filled_vao, self.filled_instance_vbo, self.parent._sq_vbo:
            GL.glUniformMatrix3fv(self.parent._filled_shader.uniforms.mat, 1, True, mat.ctypes.data_as(GLI.c_float_p))
            GL.glDrawArraysInstanced(GL.GL_TRIANGLE_STRIP, 0, 4, len(self.__deferred_list_filled))

    def render_outline(self, mat):
        if self.__outline_count == 0:
            return

        with self.parent._outline_shader, self.__outline_vao, self.outline_instance_vbo, self.parent._sq_vbo:
            GL.glUniformMatrix3fv(self.parent._outline_shader.uniforms.mat, 1, True, mat.ctypes.data_as(GLI.c_float_p))
            GL.glDrawArraysInstanced(GL.GL_LINE_LOOP, 0, N_OUTLINE_SEGMENTS, self.__outline_count)

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
            ("color", numpy.float32, 4)
        ])

        self._outline_instance_dtype = numpy.dtype([
            ("pos", numpy.float32, 2),
            ("r", numpy.float32, 1),
            ("color", numpy.float32, 4)
        ])

        for i in self.__batches:
            i._initializeGL()
