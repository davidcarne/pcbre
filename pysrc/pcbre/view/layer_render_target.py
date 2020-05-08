from OpenGL.arrays.vbo import VBO
import contextlib
from pcbre.ui.gl import Texture, VAO, vbobind
import numpy

__author__ = 'davidc'

import OpenGL.GL as GL


class CompositeManager:
    def __init__(self):
        self.__width = 0
        self.__height = 0

        self.__layer_fbs = []

        self.__active_count = 0
        self.__keys = {}

    def get(self, key):
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

    def resize(self, width, height):
        if width == self.__width and height == self.__height:
            return

        self.__width = width
        self.__height = height

        for i in self.__layer_fbs:
            i.resize(width, height)

        self.__composite_vbo.set_array(self.__get_vbo_data())
        with self.__composite_vbo:
            self.__composite_vbo.copy_data()

    def restart(self):
        """
        Call at the start of rendering. Resets all layers to initial state
        :return:
        """

        self.__keys = {}

        self.__active_count = 0

        for n, _ in enumerate(self.__layer_fbs):
            self.reset_layer(n)

    def reset_layer(self, n):
        """
        Reset a particular layer to an empty state. This implies alpha of 0 (transparent) and type of 0 (undrawn)
        :param n:
        :return:
        """
        with self.__layer_fbs[n]:
            GL.glClearBufferfv(GL.GL_COLOR, 0, (0, 255, 0, 0))

    def __get_vbo_data(self):
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

    def initializeGL(self, gls, width, height):
        self.__width = width
        self.__height = height

        # Initialize (but don't fill) the Color LUT
        self.__texture_colors = Texture()
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
        self.__composite_vao = VAO()
        self.__composite_vbo = VBO(ar, GL.GL_STATIC_DRAW)

        with self.__composite_vao:
            self.__composite_vbo.bind()
            vbobind(self.__composite_shader, ar.dtype, "vertex").assign()
            vbobind(self.__composite_shader, ar.dtype, "texpos").assign()

    def set_color_table(self, colors):
        array = numpy.ndarray((256, 4), dtype=numpy.uint8)

        # Create a stub array with the color table data
        array.fill(0)
        array[:] = (255, 0, 255, 255)
        array[:len(colors)] = colors

        with self.__texture_colors.on(GL.GL_TEXTURE_1D):
            GL.glTexImage1D(GL.GL_TEXTURE_1D, 0, GL.GL_RGBA, 256, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE,
                            array)

    def clear_bg_fb(self, n):
        GL.glClearColor(0, 0.0, 0.0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)

    @contextlib.contextmanager
    def composite_prebind(self):
        GL.glActiveTexture(GL.GL_TEXTURE1)
        GL.glBindTexture(GL.GL_TEXTURE_1D, self.__texture_colors)

        GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)

        layer_list = self.__keys
        composite_shader = self.__composite_shader

        class _PREBIND:
            def composite(self, n, layer_primary_color):
                alpha = 0.5 * 255
                try:
                    layer = layer_list[n]
                except KeyError:
                    return

                GL.glActiveTexture(GL.GL_TEXTURE0)
                GL.glBindTexture(GL.GL_TEXTURE_2D, layer.info_texture)

                GL.glUniform4f(
                    composite_shader.uniforms.layer_color,
                    layer_primary_color[0],
                    layer_primary_color[1],
                    layer_primary_color[2],
                    alpha)

                GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)

        # Composite the layer to the screen
        with self.__composite_shader, self.__composite_vao:
            GL.glUniform1i(self.__composite_shader.uniforms.layer_info, 0)
            GL.glUniform1i(self.__composite_shader.uniforms.color_tab, 1)

            yield _PREBIND()


class RenderLayer:
    def __init__(self, width, height):
        self.__is_setup = False

        self.__setup(width, height)

    def resize(self, width, height):
        self.__setup(width, height)

    @property
    def info_texture(self):
        assert self.__is_setup
        return self.__info_tex

    def __teardown(self):
        assert self.__is_setup
        self.__is_setup = False

        GL.glDeleteFramebuffers([self.__fbo])
        del self.__info_tex

    def __i8_texture(self, i, typ, typ2, width, height):
        GL.glBindTexture(GL.GL_TEXTURE_2D, i)

        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)

        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, typ, width, height, 0, typ2, GL.GL_UNSIGNED_BYTE, None)

        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

    def __setup(self, width, height):
        if self.__is_setup:
            self.__teardown()

        self.__is_setup = True

        self.__fbo = GL.glGenFramebuffers(1)
        self.__info_tex = Texture()

        self.__i8_texture(self.__info_tex, GL.GL_RG8UI, GL.GL_RG_INTEGER, width, height)

        with self:

            GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, self.__info_tex, 0)

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

    def __enter__(self):
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.__fbo)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
