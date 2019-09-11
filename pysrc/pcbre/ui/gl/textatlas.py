__author__ = 'davidc'

from collections import namedtuple, defaultdict
from pcbre.algo.skyline import SkyLine
import scipy.ndimage.morphology
import scipy.ndimage.interpolation
import time
import freetype
import numpy
import qtpy
from qtpy import QtCore, QtGui
from pcbre.ui.misc import QImage_from_numpy
import json

BASE_FONT = 32.
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

            # PySide2 and PyQt represent a void pointer slightly differently
            if qtpy.PYQT4 or qtpy.PYQT5:
                import ctypes
                ptr = ctypes.cast(ptr.__int__(), ctypes.POINTER(ctypes.c_uint8))

            # Extract the first channel
            data = numpy.ctypeslib.as_array(ptr, (newimg.height(), newimg.width(), 4))[:,:,0].copy()

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

    old_w = inside.shape[1]//PRESCALE
    old_h = inside.shape[0]//PRESCALE

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
        return AtlasEntry(glyph.bitmap.width//PRESCALE, glyph.bitmap.rows//PRESCALE,
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
        v = self.atlas.get(char)
        if v is not None:
            return v

        self.addGlyph(char)

        return self.atlas[char]


text_atlas_entry = namedtuple("text_atlas_key", ["start", "count"])
