from OpenGL.arrays.vbo import VBO  # type: ignore
import OpenGL.GL as GL  # type: ignore
import numpy
import ctypes
from pcbre.ui.gl import VBOBind, Texture, VAO

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pcbre.model.imagelayer import ImageLayer
    from pcbre.ui.gl.glshared import GLShared
    import numpy.typing as npt

class ImageView:
    def __init__(self, il: 'ImageLayer') -> None:
        """

        :param il:
        :type il: pcbre.model.imagelayer.ImageLayer
        :return:
        """

        self.il = il
        self.im = il.decoded_image
        self.mat = None

    def initGL(self, gls: 'GLShared') -> None:
        self._tex = Texture()

        # Setup the basic texture parameters
        with self._tex.on(GL.GL_TEXTURE_2D):
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)

            # numpy packs data tightly, whereas the openGL default is 4-byte-aligned
            # fix line alignment to 1 byte so odd-sized textures load right
            GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)

            # Download the data to the buffer. cv2 stores data in BGR format
            GL.glTexImage2D(
                GL.GL_TEXTURE_2D,
                0,
                GL.GL_RGB,
                self.im.shape[1],
                self.im.shape[0],
                0,
                GL.GL_BGR,
                GL.GL_UNSIGNED_BYTE,
                self.im.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
                )

        self.prog = gls.shader_cache.get("image_vert", "image_frag")

        ar = numpy.ndarray((4, ), dtype=[
            ("vertex", numpy.float32, 2),
            ("texpos", numpy.float32, 2)
        ]) # type: ignore

        sca = max(self.im.shape[0], self.im.shape[1])
        x = self.im.shape[1] / float(sca)
        y = self.im.shape[0] / float(sca)
        ar["vertex"] = [(-x, -y), (-x, y), (x, -y), (x, y)]
        ar["texpos"] = [(0, 0), (0, 1), (1, 0), (1, 1)]

        self.b1 = VBOBind(self.prog.program, ar.dtype, "vertex")
        self.b2 = VBOBind(self.prog.program, ar.dtype, "texpos")

        self.vbo = VBO(ar, GL.GL_STATIC_DRAW, GL.GL_ARRAY_BUFFER)

        self.mat_loc = GL.glGetUniformLocation(self.prog.program, "mat")
        self.tex1_loc = GL.glGetUniformLocation(self.prog.program, "tex1")

        self.vao = VAO()
        with self.vbo, self.vao:
            self.b1.assign()
            self.b2.assign()

    def render(self, viewPort: 'npt.NDArray[numpy.float64]') -> None:
        m_pre = self.mat
        if self.mat is None:
            m_pre = self.il.transform_matrix
        mat = viewPort.dot(m_pre)

        GL.glActiveTexture(GL.GL_TEXTURE0)
        with self.prog.program, self._tex.on(GL.GL_TEXTURE_2D), self.vao:
            GL.glUniformMatrix3fv(self.mat_loc, 1, True, mat.astype(numpy.float32))
            GL.glUniform1i(self.tex1_loc, 0)

            GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)

    #def tfI2W(self, pt) -> Tuple[float, float]:
    #    x_, y_, t_ = self.il.transform_matrix.dot([pt[0], pt[1], 1.])
    #    return (x_/t_, y_/t_)

    #def tfW2I(self, pt) -> Tuple[float, float]:
    #    reverse = numpy.linalg.inv(self.il.transform_matrix)
    #    x_, y_, t_ = reverse.dot([pt[0], pt[1], 1.])
    #    return (x_/t_, y_/t_)
