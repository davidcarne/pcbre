from pcbre.view.rendersettings import RENDER_SELECTED, RENDER_OUTLINES, RENDER_HINT_NORMAL

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

class THRenderer:
    def __init__(self, parent_view):
        self.parent = parent_view
        self.restart()

    def restart(self):
        self.__deferred_list_filled = []
        self.__deferred_list_outline = []

    def initializeGL(self, glshared):

        self.__filled_shader = glshared.shader_cache.get(
            "via_filled_vertex_shader", "via_filled_fragment_shader")

        self.__outline_shader = glshared.shader_cache.get(
            "via_outline_vertex_shader", "frag1"
        )

        self.__filled_vao = VAO()
        self.__outline_vao = VAO()

        # Build geometry for filled rendering using the frag shader for circle borders
        filled_points = [
            ((-1, -1), ),
            ((1, -1), ),
            ((-1, 1), ),
            ((1,  1), ),
        ]
        ar = numpy.array(
            filled_points
            , dtype=[("vertex", numpy.float32, 2)])

        self.__sq_vbo = VBO(ar, GL.GL_STATIC_DRAW)
        with self.__filled_vao, self.__sq_vbo:
            vbobind(self.__filled_shader, ar.dtype, "vertex").assign()


        # Build and bind an instance array for the "filled" geometry
        self.filled_instance_dtype = numpy.dtype([
            ("pos", numpy.float32, 2),
            ("r", numpy.float32, 1),
            ("r_inside_frac_sq", numpy.float32, 1),
            ("color", numpy.float32, 4)
        ])

        # Use a fake array to get a zero-length VBO for initial binding
        filled_instance_array = numpy.ndarray(0, dtype=self.filled_instance_dtype)
        self.filled_instance_vbo = VBO(filled_instance_array)

        with self.__filled_vao, self.filled_instance_vbo:
            vbobind(self.__filled_shader, self.filled_instance_dtype, "pos", div=1).assign()
            vbobind(self.__filled_shader, self.filled_instance_dtype, "r", div=1).assign()
            vbobind(self.__filled_shader, self.filled_instance_dtype, "r_inside_frac_sq", div=1).assign()
            vbobind(self.__filled_shader, self.filled_instance_dtype, "color", div=1).assign()


        # Build geometry for outline rendering
        outline_points = []
        for i in numpy.linspace(0, math.pi * 2, N_OUTLINE_SEGMENTS, False):
            outline_points.append(((math.cos(i), math.sin(i)), ))

        ar = numpy.array(
            outline_points
            , dtype=[("vertex", numpy.float32, 2)])

        self.__outline_vbo = VBO(ar, GL.GL_STATIC_DRAW)
        with self.__outline_vao, self.__outline_vbo:
            vbobind(self.__outline_shader, ar.dtype, "vertex").assign()

        # Build instance for outline rendering
        # We don't have an inner 'r' for this because we just do two instances per vertex
        self.outline_instance_dtype = numpy.dtype([
            ("pos", numpy.float32, 2),
            ("r", numpy.float32, 1),
            ("color", numpy.float32, 4)
        ])

        # Use a fake array to get a zero-length VBO for initial binding
        outline_instance_array = numpy.ndarray(0, dtype=self.outline_instance_dtype)
        self.outline_instance_vbo = VBO(outline_instance_array)

        with self.__outline_vao, self.outline_instance_vbo:
            vbobind(self.__outline_shader, self.outline_instance_dtype, "pos", div=1).assign()
            vbobind(self.__outline_shader, self.outline_instance_dtype, "r", div=1).assign()
            vbobind(self.__outline_shader, self.outline_instance_dtype, "color", div=1).assign()

    def deferred(self, center, r1, r2, rs, render_hint=RENDER_HINT_NORMAL):
        if rs & RENDER_OUTLINES:
            self.__deferred_list_outline.append((center, r1, r2, rs))
        else:
            self.__deferred_list_filled.append((center, r1, r2, rs))

    def render(self, mat):
        self.render_filled(mat)
        self.render_outline(mat)

    def render_filled(self, mat):
        count = len(self.__deferred_list_filled)

        if count == 0:
            return

        # Resize instance data array
        instance_array = numpy.ndarray(count, dtype = self.filled_instance_dtype)

        for n, (center, r1, r2, rs) in enumerate(self.__deferred_list_filled):
            color_a = [0.6, 0.6, 0.6, 1]

            # HACK, color object
            color_a = self.parent.sel_colormod(rs & RENDER_SELECTED, color_a)

            # frag shader uses pythag to determine is frag is within
            # shaded area. Precalculate comparison term
            r_frac_sq = (r2 / r1) ** 2
            instance_array[n] = (center, r1, r_frac_sq, color_a)

        self.filled_instance_vbo.data = instance_array
        self.filled_instance_vbo.size = None
        self.filled_instance_vbo.copied = False
        self.filled_instance_vbo.bind()

        with self.__filled_shader, self.__filled_vao, self.filled_instance_vbo, self.__sq_vbo:
            GL.glUniformMatrix3fv(self.__filled_shader.uniforms.mat, 1, True, mat.ctypes.data_as(GLI.c_float_p))
            GL.glDrawArraysInstanced(GL.GL_TRIANGLE_STRIP, 0, 4, count)

    def render_outline(self, mat):
        count = 0
        for center, r1, r2, rs in self.__deferred_list_outline:
            if r2 == 0:
                count += 1
            else:
                count += 2

        if count == 0:
            return

        # Resize instance data array
        instance_array = numpy.ndarray(count, dtype = self.outline_instance_dtype)

        n = 0
        for center, r1, r2, rs in self.__deferred_list_outline:
            color_a = [0.6, 0.6, 0.6, 1]

            # HACK, color object
            color_a = self.parent.sel_colormod(rs & RENDER_SELECTED, color_a)

            instance_array[n] = (center, r1, color_a)
            n += 1

            if r2 > 0:
                instance_array[n] = (center, r2, color_a)
                n += 1

        self.outline_instance_vbo.data = instance_array
        self.outline_instance_vbo.size = None
        self.outline_instance_vbo.copied = False
        self.outline_instance_vbo.bind()

        with self.__outline_shader, self.__outline_vao, self.outline_instance_vbo, self.__sq_vbo:
            GL.glUniformMatrix3fv(self.__outline_shader.uniforms.mat, 1, True, mat.ctypes.data_as(GLI.c_float_p))
            GL.glDrawArraysInstanced(GL.GL_LINE_LOOP, 0, N_OUTLINE_SEGMENTS, count)
