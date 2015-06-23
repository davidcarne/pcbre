# Signed distance field based text rendering

from OpenGL.arrays.vbo import VBO
from collections import namedtuple, defaultdict
from pcbre.algo.skyline import SkyLine
from pcbre.matrix import Rect, translate, scale
from pcbre.ui.gl import Texture, vbobind, VAO
from OpenGL import GL
import ctypes
import scipy.ndimage.morphology
import scipy.ndimage.interpolation
import time
import freetype
import numpy
from PySide import QtCore, QtGui
from pcbre.ui.misc import QImage_from_numpy
import json

BASE_FONT = 32.

__author__ = 'davidc'

# Constant used to determine how large to expand bitmaps
PRESCALE = 4


# Use compiled C implementation of EDTAA3
# At some point, we'll want to rewrite this to do glyph-curve-distance based rendering
# but that point isn't now.
from pcbre.accel.edtaa3 import edtaa3, compute_gradient, c_double_p, c_short_p


def saveCached(image, atlas):
    img = QImage_from_numpy(image)
    # TODO - make this better
    img.save("/tmp/shader.png", "PNG")

    ser = dict()
    for k, v in list(atlas.items()):
        d = {
            "sx": v.sx,
            "sy": v.sy,
            "tx": v.tx,
            "ty": v.ty,
            "w":  v.w,
            "h":  v.h,
            "l": v.l,
            "t": v.t,
            "hb": v.hb,
            }
        ser[k] = d
    json.dump(ser, open("/tmp/shader.json", "w"))

def loadCached():
    try:
        # TODO, rework to use app cache directory
        img = QtGui.QImage()
        if img.load("/tmp/shader.png"):
            newimg = img.convertToFormat(QtGui.QImage.Format.Format_ARGB32)

            shape = newimg.height(), newimg.width()
            ptr = newimg.constBits()

            # Extract the first channel
            data = numpy.array(ptr, dtype=numpy.uint8).reshape(newimg.height(), newimg.width(), 4)[:,:,0].copy()

            st = json.load(open("/tmp/shader.json","r"))

            atlas = {}
            for k, v in list(st.items()):
                atlas[k] = AtlasEntry(v['w'], v['h'], v['sx'], v['sy'], v['tx'], v['ty'], v['l'], v['t'], v['hb'])

            return atlas, data

    except IOError:
        pass

    return None

def distance_transform_bitmap(input, margin):
    # Calculate the size of the surface we're drawing on
    mp = margin * PRESCALE
    width = input.width + 2 * mp
    height = input.rows + 2 * mp
    shape = (height, width)

    # Build a buffer containing our padded-out glyph in double format for passing to EDTAA3
    data = numpy.zeros(shape, dtype=numpy.double)
    if input._FT_Bitmap.buffer:
        data[mp:-mp, mp:-mp] = numpy.ctypeslib.as_array(input._FT_Bitmap.buffer, (input.rows, input.width))[::-1]

    # And rescale said buffer to be in the range 0..1
    data /= 255.0
    numpy.clip(data, 0, 1, out=data)

    # Allocate working buffers
    xdist = numpy.zeros(shape, dtype=numpy.short)
    ydist = numpy.zeros(shape, dtype=numpy.short)
    gx = numpy.zeros(shape, dtype=numpy.double)
    gy = numpy.zeros(shape, dtype=numpy.double)
    outside = numpy.zeros(shape, dtype=numpy.double)
    inside = numpy.zeros(shape, dtype=numpy.double)

    # Distance transform for the outside
    compute_gradient(data.ctypes.data_as(c_double_p),
                     width, height,
                     gx.ctypes.data_as(c_double_p),
                     gy.ctypes.data_as(c_double_p))

    edtaa3(data.ctypes.data_as(c_double_p),
           gx.ctypes.data_as(c_double_p),
           gy.ctypes.data_as(c_double_p),
           width,
           height,
           xdist.ctypes.data_as(c_short_p),
           ydist.ctypes.data_as(c_short_p),
           outside.ctypes.data_as(c_double_p))

    outside.clip(min=0, out=outside)

    # Distance transform for the inside
    data = 1 - data

    gx.fill(0)
    gy.fill(0)

    compute_gradient(data.ctypes.data_as(c_double_p),
                     width, height,
                     gx.ctypes.data_as(c_double_p),
                     gy.ctypes.data_as(c_double_p))

    edtaa3(data.ctypes.data_as(c_double_p),
           gx.ctypes.data_as(c_double_p),
           gy.ctypes.data_as(c_double_p),
           width,
           height,
           xdist.ctypes.data_as(c_short_p),
           ydist.ctypes.data_as(c_short_p),
           inside.ctypes.data_as(c_double_p))

    inside.clip(min=0, out=inside)


    # Combine inside and outside distance transform
    inside -= outside

    old_w = inside.shape[1]/PRESCALE
    old_h = inside.shape[0]/PRESCALE

    # Resample down to the low res version
    rescaled = scipy.ndimage.interpolation.zoom(inside, 1./PRESCALE, order=1)
    rescaled = rescaled[:old_h, :old_w]

    # And transfer back to a uint8
    # All in-place ops to prevent reallocations
    rescaled *= 8
    rescaled += 192
    numpy.rint(rescaled, out=rescaled)
    rescaled.clip(0,255, out=rescaled)

    rv = numpy.array(rescaled, numpy.uint8)

    # Hard-clip the margins to prevent rendering errors
    rv[0, :] = 0
    rv[-1, :] = 0
    rv[:, 0] = 0
    rv[:, -1] = 0

    return rv

class AtlasEntry(object):
    def __init__(self, w, h, sx, sy, tx, ty, l, t, hb):
        # Texture Coordinates
        self.sx = sx
        self.sy = sy
        self.tx = tx
        self.ty = ty


        self.w = w
        self.h = h

        # left-offset
        self.l = l

        # top-offset
        self.t = t

        # horiz-advance
        self.hb = hb


    @staticmethod
    def fromGlyph(glyph):
        return AtlasEntry(glyph.bitmap.width/PRESCALE, glyph.bitmap.rows/PRESCALE,
                          0, 0, 0, 0,
                          glyph.metrics.horiBearingX/64.0/PRESCALE, glyph.metrics.horiBearingY/64.0/PRESCALE,
                          glyph.metrics.horiAdvance/64.0/PRESCALE)

    def updatePos(self, texwidth, texheight, x0, y0, x1, y1):
        fw = float(texwidth)
        fh = float(texheight)
        self.sx = x0/fw
        self.sy = y0/fh
        self.tx = x1/fw
        self.ty = y1/fw

class SDFTextAtlas(object):
    def __init__(self, fontname):
        self.face = freetype.Face(fontname)
        pre = time.time()

        height_base = int(BASE_FONT)
        self.face.set_char_size(height=PRESCALE * height_base * 64)

        dim = 1024
        self.margin = 3

        self.packer = SkyLine(dim, dim)

        load_results = loadCached()

        if load_results is not None:
            self.atlas, self.image = load_results
        else:
            self.atlas = {}
            self.image = numpy.zeros((dim, dim), dtype=numpy.uint8)

        old_set = frozenset(list(self.atlas.keys()))

        import string
        chars = string.digits + string.ascii_letters + string.punctuation + ' '

        #self.addGlyphs(string.digits + string.letters + string.punctuation)

        for i in chars:
            self.getGlyph(i)

        d = time.time() - pre

        new_set = frozenset(list(self.atlas.keys()))
        if old_set != new_set:
            saveCached(self.image, self.atlas)


    def addGlyphs(self, multi):
        """
        Add multiple glyphs at a time, packing by best-packing-score first
        Execution time is poor, and gains don't seem to be worth increased execution time
        The packer algorithm could almost certainly made smarter (specifically, the "find" algo)

        :param multi:
        :return:
        """
        # Tuples of (char, ae, bitmap)

        glyphs = []

        # Pre-build the bitmap info
        for char in multi:
            self.face.load_char(char)
            #bitmap = self.face.glyph.bitmap
            #w,h = bitmap.width, bitmap.rows
            #bl, bt = self.face.glyph.metrics.horiBearingX/64.0, self.face.glyph.metrics.horiBearingY/64.0
            #bm = numpy.array(bitmap.buffer, dtype=numpy.ubyte).reshape(h,w)
            #ha = self.face.glyph.metrics.horiAdvance/64.0

            ae = AtlasEntry.fromGlyph(self.face.glyph)
            #bm = numpy.array(self.face.glyph.bitmap.buffer, dtype=numpy.ubyte).reshape(ae.h, ae.w)
            w, h = self.face.glyph.bitmap.width, self.face.glyph.bitmap.rows
            bm = distance_transform_bitmap(self.face.glyph.bitmap, self.margin)

            #print char, bl, bt, self.face.glyph.metrics.horiBearingX/64.0, self.face.glyph.metrics.horiBearingY/64.0, ha/64.0, w
            #glyphs.append((char, w, h, bl, bt, ha, bm))
            glyphs.append((char, ae, bm))

        # Submit a list of rects to pack to the packer
        packlist = [(x[1].w + 2 * self.margin, x[1].h + 2 * self.margin) for x in glyphs]
        multiple = self.packer.pack_multiple(packlist)
        assert len(multiple) == len(packlist)

        # Now fill those rects
        fw = float(self.packer.width)
        fh = float(self.packer.height)

        for (char, ae, bm), (x0, y0) in zip(glyphs, multiple):
            x1, y1 = x0 + ae.w + 2 * self.margin, y0 + ae.h + 2 * self.margin
            ae.updatePos(self.packer.width, self.packer.height, x0, y0, x1, y1)

            self.atlas[char] = ae
            self.image[y0:y1, x0:x1] = bm

    def addGlyph(self, char):
        self.face.load_char(char)

        bitmap = self.face.glyph.bitmap

        w,h = bitmap.width, bitmap.rows


        ae = AtlasEntry.fromGlyph(self.face.glyph)

        pos = self.packer.pack(ae.w + 2 * self.margin, ae.h + 2 * self.margin)
        if pos is not None:

            x0, y0 = pos
            x1, y1 = x0 + ae.w, y0 + ae.h
            x1 += 2 * self.margin
            y1 += 2 * self.margin

            self.image[y0:y1, x0:x1] = distance_transform_bitmap(bitmap, self.margin)


            ae.updatePos(self.packer.width, self.packer.height, x0 , y0, x1, y1)

            self.atlas[char] = ae


    def getGlyph(self, char):
        try:
            return self.atlas[char]
        except KeyError:
            self.addGlyph(char)

        return self.atlas[char]


text_atlas_entry = namedtuple("text_atlas_key", ["start", "count"])

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

        self.__cached[text] = ti = self.text_render.getString(text)

        ti.start = len(self.__clist)

        self.__clist.extend(ti.arr)
        ti.count = len(ti.arr)
        self.__vbo_needs_update = True
        return ti



class TextInfo(object):
    def __init__(self, arr, metrics):
        self.__rect = Rect()
        (self.__rect.left, self.__rect.right, self.__rect.bottom, self.__rect.top) = metrics
        self.arr = arr

    def get_metrics(self):
        """
        :return: (left, right, bottom, top)
        """
        return self.__metrics

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


    def getString(self, text):
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
        return TextInfo(q, (left, right, bottom, top))




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

            # Download the data to the buffer. cv2 stores data in BGR format
            GL.glTexImage2D(GL.GL_TEXTURE_2D,
                            0,
                            GL.GL_RED,
                            self.sdf_atlas.image.shape[1],
                            self.sdf_atlas.image.shape[0],
                            0,
                            GL.GL_RED,
                            GL.GL_UNSIGNED_BYTE,
                            self.sdf_atlas.image.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)))
