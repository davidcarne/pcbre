__author__ = 'davidc'

from qtpy import QtCore, QtGui, QtOpenGL
from OpenGL import GL  # type: ignore
import re
from typing import Tuple, Union


class _33ProbeWidget(QtOpenGL.QGLWidget):
    def __init__(self) -> None:
        f = QtOpenGL.QGLFormat()
        f.setVersion(3, 3)
        f.setProfile(QtOpenGL.QGLFormat.CoreProfile)
        c = QtOpenGL.QGLContext(f)
        QtOpenGL.QGLWidget.__init__(self, c)

def probe() -> Union[Tuple[int, int], None]:
    w = QtOpenGL.QGLWidget()
    w.makeCurrent()

    vers = GL.glGetString(GL.GL_VERSION).decode("ascii")
    v_match = re.match(r"^(\d+(\.\d+)+)\s", vers)

    # If we can't parse the vers string, who knows what version we have
    if not v_match:
        return None

    g = v_match.group(1).split(".")
    v1 = int(g[0])
    v2 = int(g[1])

    return v1, v2


