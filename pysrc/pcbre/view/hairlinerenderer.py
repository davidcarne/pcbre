__author__ = 'davidc'
from OpenGL import GL
from OpenGL.arrays.vbo import VBO
import numpy
from pcbre.ui.gl import VAO, vbobind, glimports as GLI


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
