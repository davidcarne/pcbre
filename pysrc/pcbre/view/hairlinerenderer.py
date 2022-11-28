__author__ = 'davidc'

from typing import TYPE_CHECKING

import numpy
from OpenGL import GL  # type: ignore
from OpenGL.arrays.vbo import VBO  # type: ignore

from pcbre.ui.gl import VAO, VBOBind

if TYPE_CHECKING:
    from pcbre.ui.boardviewwidget import BoardViewWidget
    import numpy.typing as npt
    from pcbre.accel.vert_array import VA_xy


class HairlineRenderer:

    def __init__(self, view: 'BoardViewWidget') -> None:
        self.__view = view

    def initializeGL(self) -> None:
        self.__dtype = numpy.dtype([('vertex', numpy.float32, 2)])
        self.__shader = self.__view.gls.shader_cache.get("basic_fill_vert", "basic_fill_frag")

        self._va_vao = VAO()
        self._va_batch_vbo = VBO(numpy.array([], dtype=self.__dtype), GL.GL_STREAM_DRAW)
        GL.glObjectLabel(GL.GL_BUFFER, int(self._va_batch_vbo), -1, "Hairline VA batch VBO")

        with self._va_vao, self._va_batch_vbo:
            VBOBind(self.__shader.program, self.__dtype, "vertex").assign()

    def render_va(self, mat: 'npt.NDArray[numpy.float64]', va: 'VA_xy', col: int) -> None:
        if va.count() == 0:
            return

        self._va_batch_vbo.set_array(va.buffer()[:])

        with self.__shader.program, self._va_vao, self._va_batch_vbo:
            GL.glUniformMatrix3fv(self.__shader.uniforms.mat, 1, True, mat.astype(numpy.float32))
            GL.glUniform4ui(self.__shader.uniforms.layer_info, 255, col, 0, 0)
            GL.glDrawArrays(GL.GL_LINES, 0, va.count())
