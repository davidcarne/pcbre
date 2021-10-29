from pcbre.model.component import Component
from pcbre.util import Timer
import OpenGL.GL as GL  # type: ignore
from OpenGL.arrays.vbo import VBO  # type: ignore
from pcbre.accel.vert_array import VA_xy
from pcbre.ui.gl import VAO, glimports as GLI
import ctypes
import numpy

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pcbre.ui.boardviewwidget import BoardViewWidget
    from pcbre.ui.gl.glshared import GLShared

class DebugRender:
    def __init__(self, boardview: 'BoardViewWidget') -> None:
        self.debug_draw = False
        self.debug_draw_bbox = True
        self.parent = boardview

    def initializeGL(self, gls: 'GLShared') -> None:
        self.shader = gls.shader_cache.get("vert2", "frag1")

        self.vao = VAO()

        self.vbo = VBO(bytes(), usage=GL.GL_STREAM_DRAW)

        # bind the shader
        with self.vao, self.vbo:
            loc = GL.glGetAttribLocation(self.shader.program, "vertex")
            assert loc != -1
            GL.glEnableVertexAttribArray(loc)

            # TODO - HACK. AttribPointer is dependent on ABI data layout.
            # Should be common on all sane archs, but this should be fetched on demand
            GL.glVertexAttribPointer(loc, 2, GL.GL_FLOAT, False, 8, ctypes.c_void_p(0))
            GL.glVertexAttribDivisor(loc, 0)

    def render(self) -> None:

        if not self.debug_draw:
            return

        # Create two X-Y vertex buffers; one for selected features, and one non-selected
        buf = VA_xy(1024)
        buf_sel = VA_xy(1024)

        t_debug_bbox = Timer()
        t_debug_bbox_add = Timer()
        with t_debug_bbox:
            if self.debug_draw_bbox:

                # Build a list of all bboxes we're going to draw
                bboxes = []
                for i in self.parent.getVisible():
                    bboxes.append((i.bbox, i in self.parent.selectionList))

                    if isinstance(i, Component):
                        for j in i.get_pads():
                            bboxes.append((j.bbox, j in self.parent.selectionList))

                with t_debug_bbox_add:
                    # Add bboxes to buffers
                    for bbox, selected in bboxes:
                        cx = (bbox.left + bbox.right) / 2
                        cy = (bbox.bottom + bbox.top) / 2
                        h = bbox.top - bbox.bottom
                        w = bbox.right - bbox.left

                        dest = buf
                        if selected:
                            dest = buf_sel

                        dest.add_aligned_box(cx, cy, w, h)

        t_debug_draw = Timer()
        with t_debug_draw:
            # TODO: HACK
            # PyOpenGL doesn't know how to deal with a cffi buffer
            buf_r = buf.buffer()[:] + buf_sel.buffer()[:]
            self.vbo.set_array(buf_r, None)

            # Now render the two buffers
            with self.shader.program, self.vao, self.vbo:
                GL.glUniformMatrix3fv(self.shader.uniforms.mat, 1, True, self.parent.viewState.glMatrix.astype(numpy.float32))

                GL.glUniform4f(self.shader.uniforms.color, 255, 0, 255, 255)
                GL.glDrawArrays(GL.GL_LINES, 0, buf.count())

                GL.glUniform4f(self.shader.uniforms.color, 255, 255, 255, 255)
                GL.glDrawArrays(GL.GL_LINES, buf.count(), buf_sel.count())

        print("debug draw time: %f(%f) %f" % (t_debug_bbox.interval, t_debug_bbox_add.interval, t_debug_draw.interval))
