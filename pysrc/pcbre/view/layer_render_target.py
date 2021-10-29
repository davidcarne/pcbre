import contextlib

import OpenGL.GL as GL  # type: ignore
import OpenGL.constant  # type: ignore
import numpy
from OpenGL.arrays.vbo import VBO  # type: ignore

from pcbre.ui.gl import Texture, VAO, VBOBind

__author__ = 'davidc'

from typing import TYPE_CHECKING, Dict, Any, Sequence, Tuple, Optional, List, Generator

if TYPE_CHECKING:
    import numpy.typing as npt
    from pcbre.ui.gl.glshared import GLShared
    from pcbre.ui.gl.shader import EnhShaderProgram


class CompositeManager:
    def __init__(self) -> None:
        self.__width = 0
        self.__height = 0

        self.__layer_fbs: 'List[RenderLayer]' = []

        self.__active_count = 0
        self.__keys: 'Dict[Any, RenderLayer]' = {}

    def get(self, key: Any) -> 'RenderLayer':
        # If we've already got a composite target for this key
        # return it
        if key in self.__keys:
            return self.__keys[key]

        # Allocate a new layer if required
        if self.__active_count == len(self.__layer_fbs):
            self.__layer_fbs.append(RenderLayer(self.__width, self.__height))

        # Save new layer fb for reuse
        self.__keys[key] = self.__layer_fbs[self.__active_count]
        self.__active_count += 1
        return self.__keys[key]

    def resize(self, width: int, height: int) -> None:
        if width == self.__width and height == self.__height:
            return

        self.__width = width
        self.__height = height

        for i in self.__layer_fbs:
            i.resize(width, height)

        self.__composite_vbo.set_array(self.__get_vbo_data())
        with self.__composite_vbo:
            self.__composite_vbo.copy_data()

    def restart(self) -> None:
        """
        Call at the start of rendering. Resets all layers to initial state
        :return:
        """

        self.__keys = {}

        self.__active_count = 0

        for n, _ in enumerate(self.__layer_fbs):
            self.reset_layer(n)

    def reset_layer(self, n: int) -> None:
        """
        Reset a particular layer to an empty state. This implies alpha of 0 (transparent) and type of 0 (undrawn)
        :param n:
        :return:
        """
        with self.__layer_fbs[n]:
            GL.glClearBufferfv(GL.GL_COLOR, 0, (0, 255, 0, 0))

    def __get_vbo_data(self) -> 'npt.NDArray[numpy.float64]':
        if self.__width == 0 or self.__height == 0:
            assert False

        # Fullscreen textured quad
        filled_points = [
            ((-1.0, -1.0), (0.0, 0.0)),
            ((1.0, -1.0), (1.0, 0.0)),
            ((-1.0, 1.0), (0.0, 1.0)),
            ((1.0, 1.0), (1.0, 1.0)),
        ]

        ar = numpy.array(filled_points, dtype=[("vertex", numpy.float32, 2), ("texpos", numpy.float32, 2)])

        sscale = max(self.__width, self.__height)
        xscale = self.__width / sscale
        yscale = self.__height / sscale

        ar["vertex"][:, 0] *= xscale
        ar["vertex"][:, 1] *= yscale

        return ar

    def initializeGL(self, gls: 'GLShared', width: int, height: int) -> None:
        self.__width = width
        self.__height = height

        # Initialize (but don't fill) the Color LUT
        self.__texture_colors = Texture(debug_name="Layer Color LUT")
        with self.__texture_colors.on(GL.GL_TEXTURE_1D):
            GL.glTexParameteri(GL.GL_TEXTURE_1D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
            GL.glTexParameteri(GL.GL_TEXTURE_1D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
            GL.glTexParameteri(GL.GL_TEXTURE_1D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_1D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)

        # Compositing shader and geometry
        self.__composite_shader = gls.shader_cache.get(
            "layer_composite_vert", "layer_composite_frag",
            fragment_bindings={"final_color": 0})

        ar = self.__get_vbo_data()
        self.__composite_vao = VAO(debug_name="Compositor Quad VAO")
        self.__composite_vbo = VBO(ar, GL.GL_STATIC_DRAW)
        GL.glObjectLabel(GL.GL_BUFFER, int(self.__composite_vbo), -1, "Compositor Quad VBO")

        with self.__composite_vao:
            self.__composite_vbo.bind()
            VBOBind(self.__composite_shader.program, ar.dtype, "vertex").assign()
            VBOBind(self.__composite_shader.program, ar.dtype, "texpos").assign()

    def set_color_table(self, colors: 'Sequence[Tuple[int, int, int, int]]') -> None:
        array: 'npt.NDArray[numpy.uint8]' = numpy.ndarray((256, 4), dtype=numpy.uint8)

        # Create a stub array with the color table data
        array.fill(0)
        array[:] = (255, 0, 255, 255)
        array[:len(colors)] = colors

        with self.__texture_colors.on(GL.GL_TEXTURE_1D):
            GL.glTexImage1D(GL.GL_TEXTURE_1D, 0, GL.GL_RGBA, 256, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE,
                            array)

    class _PREBIND:
        def __init__(self, layer_list: 'Dict[Any, RenderLayer]', composite_shader: 'EnhShaderProgram'):
            self.layer_list = layer_list
            self.composite_shader = composite_shader

        def composite(self, n: Any, layer_primary_color: 'Tuple[int,int,int]') -> None:
            alpha = 0.5 * 255
            try:
                layer = self.layer_list[n]
            except KeyError:
                return

            GL.glActiveTexture(GL.GL_TEXTURE0)
            GL.glBindTexture(GL.GL_TEXTURE_2D, layer.info_texture.v)

            GL.glUniform4f(
                self.composite_shader.uniforms.layer_color,
                layer_primary_color[0],
                layer_primary_color[1],
                layer_primary_color[2],
                alpha)

            GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)

    @contextlib.contextmanager
    def composite_prebind(self) -> Generator['_PREBIND', None, None]:
        GL.glActiveTexture(GL.GL_TEXTURE1)
        GL.glBindTexture(GL.GL_TEXTURE_1D, self.__texture_colors.v)

        GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)

        # Composite the layer to the screen
        with self.__composite_shader.program, self.__composite_vao:
            GL.glUniform1i(self.__composite_shader.uniforms.layer_info, 0)
            GL.glUniform1i(self.__composite_shader.uniforms.color_tab, 1)

            yield self._PREBIND(self.__keys, self.__composite_shader)


class RenderLayer:
    def __init__(self, width: int, height: int, debug_name: Optional[str]=None) -> None:
        self.__debug_name = debug_name

        self.__is_setup = False

        self.__setup(width, height)

    def resize(self, width: int, height: int) -> None:
        self.__setup(width, height)

    @property
    def info_texture(self) -> 'Texture':
        assert self.__is_setup
        return self.__info_tex

    def __teardown(self) -> None:
        assert self.__is_setup
        self.__is_setup = False

        GL.glDeleteFramebuffers(2, [self.__fbo])
        del self.__info_tex

    @staticmethod
    def __i8_texture(i: Texture, typ: OpenGL.constant.IntConstant, typ2: OpenGL.constant.IntConstant, width: int,
                     height: int) -> None:
        GL.glBindTexture(GL.GL_TEXTURE_2D, i.v)

        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)

        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, typ, width, height, 0, typ2, GL.GL_UNSIGNED_BYTE, None)

        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

    def __setup(self, width: int, height: int) -> None:
        if self.__is_setup:
            self.__teardown()

        self.__is_setup = True

        self.__fbo = GL.glGenFramebuffers(1)
        if self.__debug_name is not None:
            GL.glObjectLabel(GL.GL_FRAMEBUFFER, self.__fbo, -1, self.__debug_name)

        self.__info_tex = Texture(debug_name=self.__debug_name)

        self.__i8_texture(self.__info_tex, GL.GL_RG8UI, GL.GL_RG_INTEGER, width, height)

        with self:

            GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, self.__info_tex.v,
                                      0)

            GL.glDrawBuffers([GL.GL_COLOR_ATTACHMENT0])

            status = GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)

            if status != GL.GL_FRAMEBUFFER_COMPLETE:
                lut = [GL.GL_FRAMEBUFFER_UNDEFINED,
                       GL.GL_FRAMEBUFFER_INCOMPLETE_ATTACHMENT,
                       GL.GL_FRAMEBUFFER_INCOMPLETE_MISSING_ATTACHMENT,
                       GL.GL_FRAMEBUFFER_INCOMPLETE_DRAW_BUFFER,
                       GL.GL_FRAMEBUFFER_INCOMPLETE_READ_BUFFER,
                       GL.GL_FRAMEBUFFER_UNSUPPORTED,
                       GL.GL_FRAMEBUFFER_INCOMPLETE_MULTISAMPLE,
                       GL.GL_FRAMEBUFFER_INCOMPLETE_LAYER_TARGETS]

                # Find the magic constant name
                for i in lut:
                    if status == int(i):
                        result = i
                        break
                else:
                    result = "unknown %d" % status

                print("Error, could not create framebuffer. Status: %s" % str(result))
                assert False

    def __enter__(self) -> 'RenderLayer':
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.__fbo)
        return self

    def __exit__(self, exc_type: 'Optional[Any]', exc_val: 'Optional[Any]', exc_tb: 'Optional[Any]') -> None:
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
