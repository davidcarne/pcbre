from collections import defaultdict
from pcbre.model.artwork_geom import Airwire
from pcbre.model.component import Component
from pcbre.model.const import SIDE
from pcbre.model.dipcomponent import DIPComponent
from pcbre.model.passivecomponent import Passive2Component
from pcbre.model.smd4component import SMD4Component
from pcbre.view.componentview import dip_border_va, smd_border_va, passive_border_va, cmp_border_va
from pcbre.view.rendersettings import RENDER_STANDARD, RENDER_OUTLINES, RENDER_SELECTED, RENDER_HINT_NORMAL, \
    RENDER_HINT_ONCE
from pcbre.view.target_const import COL_SEL, COL_AIRWIRE, COL_CMP_LINE
from pcbre.view.util import get_consolidated_draws_1, get_consolidated_draws

__author__ = 'davidc'
import math
from OpenGL import GL
from OpenGL.arrays.vbo import VBO
import numpy
from pcbre import units
from pcbre.matrix import Rect, translate, rotate, Point2, scale, Vec2
from pcbre.ui.gl import VAO, vbobind, glimports as GLI
import ctypes

from pcbre.accel.vert_array import VA_xy


class HairlineRenderer:


    def __init__(self, view):
        self.__view = view

    def initializeGL(self):
        self.__dtype = numpy.dtype([('vertex', numpy.float32, 2)])
        self.__shader = self.__view.gls.shader_cache.get("basic_fill_vert", "basic_fill_frag")

        self._va_vao = VAO()
        self._va_batch_vbo = VBO(numpy.array([], dtype=self.__dtype), GL.GL_STREAM_DRAW)


        with self._va_vao, self._va_batch_vbo:
            vbobind(self.__shader, self.__dtype, "vertex").assign()


    def render_va(self, mat, va, col):
        self._va_batch_vbo.set_array(va.buffer()[:])

        mat = numpy.array(mat, dtype=numpy.float32)
        with self.__shader, self._va_vao, self._va_batch_vbo:
            GL.glUniformMatrix3fv(self.__shader.uniforms.mat, 1, True, mat.ctypes.data_as(GLI.c_float_p))
            GL.glUniform4ui(self.__shader.uniforms.layer_info, 255, col, 0, 0)
            GL.glDrawArrays(GL.GL_LINES, 0, va.count())
