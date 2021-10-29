__author__ = 'davidc'

import contextlib
import ctypes
from typing import TYPE_CHECKING, Optional, Tuple, Generator, Any

import OpenGL.GL as GL  # type: ignore
import numpy

if TYPE_CHECKING:
    import numpy.typing


def translate_dtype(dt: 'numpy.dtype[Any]') -> Tuple[int, int]:
    if len(dt.shape) == 0:
        n = 1
        elem = dt
    elif len(dt.shape) == 1:
        assert dt.subdtype is not None
        elem, (n,) = dt.subdtype
    else:
        raise ValueError("Unknown dtype %r" % dt)

    if elem == numpy.dtype(numpy.uint32):
        t = GL.GL_UNSIGNED_INT
    elif elem == numpy.dtype(numpy.float32):
        t = GL.GL_FLOAT
    else:
        raise ValueError("Unknown dtype scalar type %r" % dt)

    # Cannot type OpenGL return type
    return t, n


class VBOBind(object):
    def __init__(self, program: int, dtype: 'numpy.dtype[Any]', name: str, shader_name: Optional[str] = None,
                 div: int = 0) -> None:
        if shader_name is None:
            shader_name = name

        self.loc = GL.glGetAttribLocation(program, shader_name)
        assert self.loc != -1

        fields = dtype.fields
        assert fields is not None
        self.t, self.n = translate_dtype(fields[name][0])

        self.offset = fields[name][1]
        self.stride = dtype.itemsize

        self.div = div

    def assign(self, base: int = 0) -> None:
        assert GL.glGetError() == 0
        offset = ctypes.c_void_p(self.offset + base * self.stride)
        GL.glEnableVertexAttribArray(self.loc)
        if self.t in [GL.GL_BYTE, GL.GL_UNSIGNED_BYTE, GL.GL_SHORT, GL.GL_UNSIGNED_SHORT, GL.GL_INT,
                      GL.GL_UNSIGNED_INT]:
            GL.glVertexAttribIPointer(self.loc, self.n, self.t, self.stride, offset)
        else:
            GL.glVertexAttribPointer(self.loc, self.n, self.t, False, self.stride, offset)
        GL.glVertexAttribDivisor(self.loc, self.div)


class Texture:
    def __init__(self, debug_name: Optional[str] = None) -> None:
        self.v = GL.glGenTextures(1)

        # Defer debug name binding; seems to only work after the initial bind
        self.__debug_name = debug_name
        self.__debug_name_set = False

    @contextlib.contextmanager
    def on(self, target: int) -> Generator[None, None, None]:
        GL.glBindTexture(target, self.v)

        # deferred debug name application
        if self.__debug_name is not None and not self.__debug_name_set:
            GL.glObjectLabel(GL.GL_TEXTURE, self.v, -1, self.__debug_name)
            self.__debug_name_set = True

        yield
        GL.glBindTexture(target, 0)


class VAO:
    def __init__(self, debug_name: Optional[str] = None) -> None:
        self.v = GL.glGenVertexArrays(1)

        if debug_name is not None:
            GL.glObjectLabel(GL.GL_VERTEX_ARRAY, self.v, -1, debug_name)

    def __enter__(self) -> None:
        GL.glBindVertexArray(self.v)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        GL.glBindVertexArray(0)
