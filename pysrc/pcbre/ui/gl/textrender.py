# Signed distance field based text rendering

from OpenGL.arrays.vbo import VBO
from collections import namedtuple, defaultdict
from pcbre.matrix import Rect, translate, scale, Point2, projectPoint
from pcbre.ui.gl import Texture, vbobind, VAO
from OpenGL import GL
import ctypes
import numpy

from pcbre.ui.gl.textatlas import BASE_FONT

__author__ = 'davidc'

class TextBatch:
    __tag = namedtuple("tag", ['mat','inf'])
    def __init__(self, tr):
        self.__text_render = tr

        self.__elem_count = 0
        self.__color = [1.0, 1.0, 1.0, 1.0]

    def initializeGL(self):
        self.vbo = VBO(numpy.ndarray(0, dtype=self.__text_render.buffer_dtype), GL.GL_STATIC_DRAW, GL.GL_ARRAY_BUFFER)
        self.vao = VAO()

        with self.vao, self.vbo:
            self.__text_render.b1.assign()
            self.__text_render.b2.assign()

    def restart(self):
        self.__strs = []

    # TEMP
    def get_string(self, text):
        """

        :param text:
        :return:
        :returns: _StringMetrics
        """
        return self.__text_render.getStringMetrics(text)

    def add(self, mat, str_info):
        """
        Queues a text string to be rendered in the batch
        :param mat: location matrix
        :param str_info:
        :type str_info: _StringMetrics
        :return:
        """
        self.__strs.append(TextBatch.__tag(mat, str_info))

    def prepare(self):
        self.__text_render.updateTexture()


        clist = []

        for mat, str_info in self.__strs:
            for (x,y), (u,v) in str_info.arr:
                newpt = projectPoint(mat, Point2(x,y))
                clist.append(((newpt.x,newpt.y), (u,v)))

        arr = numpy.array(clist, dtype=self.__text_render.buffer_dtype)

        self.vbo.data = arr
        self.vbo.size = None
        self.vbo.copied = False
        self.vbo.bind()

        self.__elem_count = len(arr)


    def render(self, mat):
        with self.__text_render.sdf_shader, self.__text_render.tex.on(GL.GL_TEXTURE_2D), self.vao:
            GL.glUniform1i(self.__text_render.sdf_shader.uniforms.tex1, 0)
            GL.glUniformMatrix3fv(self.__text_render.sdf_shader.uniforms.mat, 1, True, mat.astype(numpy.float32))
            GL.glUniform4f(self.__text_render.sdf_shader.uniforms.color, *self.__color)

            GL.glDrawArrays(GL.GL_TRIANGLES, 0, self.__elem_count)

        print("Drawing %d elements" % self.__elem_count)

class TextBatcher(object):
    __tag_type = namedtuple("render_tag", ["textinfo", "matrix", "color"])

    def __init__(self, tr):
        self.text_render = tr
        self.__cached = {}

        self.__clist = []

        self.restart()

    def restart(self):
        self.__render_tags = defaultdict(list)


    def initializeGL(self):
        # Working VBO that will contain glyph data
        self.vbo = VBO(numpy.ndarray(0, dtype=self.text_render.buffer_dtype), GL.GL_DYNAMIC_DRAW, GL.GL_ARRAY_BUFFER)
        self.vao = VAO()

        with self.vao, self.vbo:
            self.text_render.b1.assign()
            self.text_render.b2.assign()
        self.__vbo_needs_update = True


    def render(self, key=None):
        if self.__vbo_needs_update:
            arr = numpy.array(self.__clist, dtype=self.text_render.buffer_dtype)

            self.vbo.data = arr
            self.vbo.size = None
            self.vbo.copied = False
            self.vbo.bind()
            self.__vbo_needs_update = False

        self.text_render.updateTexture()

        with self.text_render.sdf_shader, self.text_render.tex.on(GL.GL_TEXTURE_2D), self.vao:
            GL.glUniform1i(self.text_render.sdf_shader.uniforms.tex1, 0)

            for tag in self.__render_tags[key]:
                mat_calc = tag.matrix
                GL.glUniformMatrix3fv(self.text_render.sdf_shader.uniforms.mat, 1, True, mat_calc.astype(numpy.float32))
                GL.glUniform4f(self.text_render.sdf_shader.uniforms.color, *tag.color)

                GL.glDrawArrays(GL.GL_TRIANGLES, tag.textinfo.start, tag.textinfo.count)

    def submit(self, ts, mat, color, k=None):
        self.__render_tags[k].append(self.__tag_type(ts, mat, color))

    def submit_text_box(self, premat, text, box, color, k=None):
        ts = self.get_string(text)
        mat = premat.dot(ts.get_render_to_mat(box))
        self.submit(ts, mat, color, k)

    def get_string(self, text):
        if text in self.__cached:
            return self.__cached[text]

        self.__cached[text] = ti = self.text_render.getStringMetrics(text)

        ti.start = len(self.__clist)

        self.__clist.extend(ti.arr)
        ti.count = len(ti.arr)
        self.__vbo_needs_update = True
        return ti



class _StringMetrics(object):
    def __init__(self, arr, metrics):
        self.__rect = Rect()
        (self.__rect.left, self.__rect.right, self.__rect.bottom, self.__rect.top) = metrics
        self.arr = arr

    def get_metrics(self):
        """
        :return: (left, right, bottom, top)
        """
        return self.__rect

    def get_render_to_wh(self, rect):
        """

        """
        hscale = rect.width / self.__rect.width
        vscale = rect.height / self.__rect.height

        actual_scale = min(hscale, vscale)
        return actual_scale * self.__rect.width, actual_scale * self.__rect.height

    def get_render_to_mat(self, rect):
        hscale = rect.width / self.__rect.width
        vscale = rect.height / self.__rect.height

        actual_scale = min(hscale, vscale)

        cx = self.__rect.center
        cx *= actual_scale

        return translate(rect.center.x - cx.x, rect.center.y - cx.y).dot(scale(actual_scale))

#_tex_vertex = namedtuple("tex_vertex", ["x", "y", "tx", "ty"])

def de_bruijn(n):
    import operator
    """
    De Bruijn sequence for numeric alphabet of length n

    Based on the wikipedia example code
    """
    k = 10

    a = [0] * k * n
    sequence = []
    def db(t, p):
        if t > n:
            if n % p == 0:
                for j in range(1, p + 1):
                    sequence.append(a[j])
        else:
            a[t] = a[t - p]
            db(t + 1, p)
            for j in range(a[t - p] + 1, k):
                a[t] = j
                db(t + 1, t)
    db(1, 1)
    return "".join(map(str, sequence))


class TextRender(object):
    def __init__(self, gls, sdf_atlas):
        self.gls = gls

        self.sdf_atlas = sdf_atlas

        self.last_glyph_count = 0

    def initializeGL(self):
        self.sdf_shader = self.gls.shader_cache.get("image_vert", "tex_frag")

        self.buffer_dtype = numpy.dtype([
            ("vertex", numpy.float32, 2),
            ("texpos", numpy.float32, 2)
        ])

        self.b1 = vbobind(self.sdf_shader, self.buffer_dtype, "vertex")
        self.b2 = vbobind(self.sdf_shader, self.buffer_dtype, "texpos")


        self.tex = Texture()


        # TODO: implement short-int caching
        # build a De-bruijn sequence (shorted substring containing all substrings)
        # self.int_seq = de_bruijn(4)
        # self.int_seq += self.int_seq[:3]


    def getStringMetrics(self, text):
        """
        create an array of coord data for rendering
        :return:
        """

        # In the future, we'll probably want to move to a texture-buffer-object
        # approach for storing glyph metrics, such that all we need to submit is an
        # array of character indicies and X-offsets
        #
        # This would pack into 8 bytes/char quite nicely (4 byte char index, float32 left)
        # With this, streaming text to the GPU would be much more effective

        # Starting pen X coordinate
        q = []
        pen_x = 0

        left, right, top, bottom = 0, 0, 0, 0

        for ch in text:
            # Fetch the glyph from the atlas
            gp = self.sdf_atlas.getGlyph(ch)

            # width and height of the rendered quad is proportional to the glpyh size
            margin = self.sdf_atlas.margin
            w = (gp.w + margin * 2)
            h = (gp.h + margin * 2)
            # Calculate the offset to the corner of the character.
            c_off_x = pen_x + gp.l - margin
            # Y position is a bit tricky. the "top" of the glyph is whats specified, but we care about the bottom-left
            # so subtract the height
            c_off_y = gp.t - gp.h - margin

            left = min(left, (c_off_x + margin) / BASE_FONT)
            right = max(right, (c_off_x + w - margin) / BASE_FONT)
            bottom = min(bottom, (c_off_y + margin) / BASE_FONT)
            top = max(top, (c_off_y + h - margin) / BASE_FONT)

            x0 = (c_off_x) / BASE_FONT
            y0 = (c_off_y) / BASE_FONT
            x1 = (c_off_x + w) / BASE_FONT
            y1 = (c_off_y + h) / BASE_FONT

            q.append(((x0, y0), (gp.sx, gp.sy)))
            q.append(((x0, y1), (gp.sx, gp.ty)))
            q.append(((x1, y0), (gp.tx, gp.sy)))
            q.append(((x1, y0), (gp.tx, gp.sy)))
            q.append(((x0, y1), (gp.sx, gp.ty)))
            q.append(((x1, y1), (gp.tx, gp.ty)))

            # And increment to the next character
            pen_x += gp.hb
        return _StringMetrics(q, (left, right, bottom, top))




    def updateTexture(self):
        # Don't update the texture if its up-to-date
        if len(self.sdf_atlas.atlas) == self.last_glyph_count:
            return

        self.last_glyph_count = len(self.sdf_atlas.atlas)

        # Setup the basic texture parameters
        with self.tex.on(GL.GL_TEXTURE_2D):
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)

            GL.glTexParameteri(GL.GL_TEXTURE_2D,GL.GL_TEXTURE_WRAP_S,GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_2D,GL.GL_TEXTURE_WRAP_T,GL.GL_CLAMP_TO_EDGE)

            # numpy packs data tightly, whereas the openGL default is 4-byte-aligned
            # fix line alignment to 1 byte so odd-sized textures load right
            GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)

            # Download the data to the buffer. 
            GL.glTexImage2D(GL.GL_TEXTURE_2D,
                            0,
                            GL.GL_RED,
                            self.sdf_atlas.image.shape[1],
                            self.sdf_atlas.image.shape[0],
                            0,
                            GL.GL_RED,
                            GL.GL_UNSIGNED_BYTE,
                            self.sdf_atlas.image.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)))
