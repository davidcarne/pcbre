from collections import defaultdict
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
from pcbre.ui.gl import VAO, vbobind, glimports as GLI

N_OUTLINE_SEGMENTS = 100



class THRenderer:
    def __init__(self, parent_view):
        self.parent = parent_view

    def initializeGL(self, glshared):

        self._filled_shader = glshared.shader_cache.get(
            "via_filled_vertex_shader", "via_filled_fragment_shader")

        self._outline_shader = glshared.shader_cache.get(
            "via_outline_vertex_shader", "basic_fill_frag"
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

        self.__dtype = numpy.dtype([
            ("pos", numpy.float32, 2),
            ("r", numpy.float32, 1),
            ("r_inside_frac_sq", numpy.float32, 1),
        ])

        self.__filled_vao = VAO()
        self.__outline_vao = VAO()

        with self.__filled_vao, self._sq_vbo:
            vbobind(self._filled_shader, self._sq_vbo.data.dtype, "vertex").assign()

        # Use a fake array to get a zero-length VBO for initial binding
        filled_instance_array = numpy.ndarray(0, dtype=self.__dtype)
        self.filled_instance_vbo = VBO(filled_instance_array)

        with self.__filled_vao, self.filled_instance_vbo:
            vbobind(self._filled_shader, self.__dtype, "pos", div=1).assign()
            vbobind(self._filled_shader, self.__dtype, "r", div=1).assign()
            vbobind(self._filled_shader, self.__dtype, "r_inside_frac_sq", div=1).assign()

        with self.__outline_vao, self._outline_vbo:
            vbobind(self._outline_shader, self._outline_vbo.data.dtype, "vertex").assign()

        # Build instance for outline rendering
        # We don't have an inner 'r' for this because we just do two instances per vertex

        # Use a fake array to get a zero-length VBO for initial binding
        outline_instance_array = numpy.ndarray(0, dtype=self.__dtype)
        self.outline_instance_vbo = VBO(outline_instance_array)

        with self.__outline_vao, self.outline_instance_vbo:
            vbobind(self._outline_shader, self.__dtype, "pos", div=1).assign()
            vbobind(self._outline_shader, self.__dtype, "r", div=1).assign()

    def render_filled(self, mat, va, color=COL_VIA):

        self.filled_instance_vbo.set_array(va.buffer()[:])


        try:
            with self._filled_shader, self.__filled_vao, self.filled_instance_vbo, self._sq_vbo:
                GL.glUniformMatrix3fv(self._filled_shader.uniforms.mat, 1, True, mat.ctypes.data_as(GLI.c_float_p))
                GL.glUniform1ui(self._filled_shader.uniforms.color, color)
                GL.glDrawArraysInstancedBaseInstance(GL.GL_TRIANGLE_STRIP, 0, 4, va.count(), 0)
        except OpenGL.error.GLError as e:
            print("Threw OGL error:")


    def render_outlines(self, mat, va):
        if not va.count():
            return

        self.outline_instance_vbo.set_array(va.buffer()[:])
        self.outline_instance_vbo.bind()

        with self._outline_shader, self.__outline_vao, self.outline_instance_vbo, self._sq_vbo:
            GL.glUniformMatrix3fv(self._outline_shader.uniforms.mat, 1, True, mat.ctypes.data_as(GLI.c_float_p))
            GL.glUniform4ui(self._outline_shader.uniforms.layer_info, 255, COL_SEL, 0, 0)
            GL.glDrawArraysInstanced(GL.GL_LINE_LOOP, 0, N_OUTLINE_SEGMENTS, va.count())
