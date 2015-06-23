__author__ = 'davidc'

import OpenGL.GL as GL
import numpy
import ctypes
from . import glimports as GLI
import contextlib

def translate_dtype(dt):
    assert len(dt.shape) <= 1
    if dt.base == numpy.uint32:
        t = GL.GL_UNSIGNED_INT
    elif dt.base == numpy.float32:
        t = GL.GL_FLOAT
    else:
        raise NotImplementedError("Unknown dtype %s" % dt)

    if not dt.shape:
        n = 1
    else:
        n = dt.shape[0]

    return t, n

def get_offset(dtype, name):
    _, offs = dtype.fields[name]
    return ctypes.c_void_p(offs)

class vbobind(object):
    def __init__(self, program, dtype, name, shader_name=None, div=0):
        if shader_name is None:
            shader_name = name

        self.loc = GL.glGetAttribLocation(program, shader_name)
        assert self.loc != -1

        self.t, self.n = translate_dtype(dtype.fields[name][0])

        self.offset = get_offset(dtype, name)
        self.stride = dtype.itemsize

        self.div = div

    def assign(self):
        assert GL.glGetError() == 0
        GL.glEnableVertexAttribArray(self.loc)
        if self.t in [GL.GL_BYTE, GL.GL_UNSIGNED_BYTE, GL.GL_SHORT, GL.GL_UNSIGNED_SHORT, GL.GL_INT, GL.GL_UNSIGNED_INT]:
            GL.glVertexAttribIPointer(self.loc, self.n, self.t, self.stride, self.offset)
        else:
            GL.glVertexAttribPointer(self.loc, self.n, self.t, False, self.stride, self.offset)
        GL.glVertexAttribDivisor(self.loc, self.div)

class Texture(int):
    def __new__(cls, *args, **kwargs):
        a = GL.glGenTextures(1)
        return  super(Texture, cls).__new__(cls, a)

    @contextlib.contextmanager
    def on(self, target):
        GL.glBindTexture(target, self)
        yield
        GL.glBindTexture(target, 0)


class VAO(int):
    def __new__(cls, *args, **kwargs):
        a = GL.glGenVertexArrays(1)
        return  super(VAO, cls).__new__(cls, a)

    def __enter__(self):
        GL.glBindVertexArray(self)

    def __exit__(self, exc_type, exc_val, exc_tb):
        GL.glBindVertexArray(0)
