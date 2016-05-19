from collections import defaultdict
from pcbre.accel.vert_array import VA_thickline
from pcbre.view.rendersettings import RENDER_STANDARD, RENDER_OUTLINES, RENDER_SELECTED
from pcbre.view.util import get_consolidated_draws_1

__author__ = 'davidc'
import math
from OpenGL import GL
from OpenGL.arrays.vbo import VBO
import numpy
from pcbre import units
from pcbre.matrix import Rect, translate, rotate, Point2, scale, Vec2
from pcbre.ui.gl import VAO, vbobind, glimports as GLI
import ctypes


import weakref

from pcbre.view.target_const import COL_LAYER_MAIN, COL_SEL

NUM_ENDCAP_SEGMENTS = 32
TRIANGLES_SIZE = (NUM_ENDCAP_SEGMENTS - 1) * 3 * 2 + 3 * 2

FIRST_LINE_LOOP = NUM_ENDCAP_SEGMENTS * 2 + 2
LINE_LOOP_SIZE = NUM_ENDCAP_SEGMENTS * 2


def trace_batch_and_draw(view, traces):
    va = VA_thickline(1024)

    t_by_l = defaultdict(list)

    # Layer batches
    for i in traces:
        t_by_l[i.layer].append(i)

    # We build the VA such that each layer may be drawn contiguously
    layer_meta = {}
    for layer, traces in t_by_l.items():
        layer_meta[layer] = va.tell(), len(traces)
        for t in traces:
            va.add_trace(t)

    for layer, (first, count) in layer_meta.items():
        with view.compositor.get(layer):
            view.trace_renderer.render_va(va, view.viewState.glMatrix, COL_LAYER_MAIN, True,
                                               first, count)

# TODO: Detect automatically
has_base_instance = True

class TraceLayer:
    def __init__(self):
        self.nonsel = VA_thickline(1024)
        self.sel = VA_thickline(1024)

class TraceRender:
    def __init__(self, parent_view):
        self.parent = parent_view
        self.__deferred_layer = defaultdict(TraceLayer)
        self.restart()

    def __initialize_uniform(self, gls):
        self.__uniform_shader_vao = VAO()
        self.__uniform_shader = gls.shader_cache.get(
                "line_vertex_shader","basic_fill_frag",
                defines={"INPUT_TYPE":"uniform"},
                fragment_bindings={"alpha" : 0, "type": 1}
        )

        with self.__uniform_shader_vao, self.trace_vbo:
            vbobind(self.__uniform_shader, self.trace_vbo.dtype, "vertex").assign()
            vbobind(self.__uniform_shader, self.trace_vbo.dtype, "ptid").assign()
            self.index_vbo.bind()


    def initializeGL(self, gls):
        # Build trace vertex VBO and associated vertex data
        dtype = [("vertex", numpy.float32, 2), ("ptid", numpy.uint32 )]
        self.working_array = numpy.zeros(NUM_ENDCAP_SEGMENTS * 2 + 2, dtype=dtype)
        self.trace_vbo = VBO(self.working_array, GL.GL_DYNAMIC_DRAW)

        # Generate geometry for trace and endcaps
        # ptid is a variable with value 0 or 1 that indicates which endpoint the geometry is associated with
        self.__build_trace()


        self.__attribute_shader_vao = VAO()
        self.__attribute_shader = gls.shader_cache.get("line_vertex_shader","basic_fill_frag", defines={"INPUT_TYPE":"in"})



        # Now we build an index buffer that allows us to render filled geometry from the same
        # VBO.
        arr = []
        for i in range(NUM_ENDCAP_SEGMENTS - 1):
            arr.append(0)
            arr.append(i+2)
            arr.append(i+3)

        for i in range(NUM_ENDCAP_SEGMENTS - 1):
            arr.append(1)
            arr.append(i+NUM_ENDCAP_SEGMENTS+2)
            arr.append(i+NUM_ENDCAP_SEGMENTS+3)

        arr.append(2)
        arr.append(2 + NUM_ENDCAP_SEGMENTS - 1)
        arr.append(2 + NUM_ENDCAP_SEGMENTS)
        arr.append(2 + NUM_ENDCAP_SEGMENTS)
        arr.append(2 + NUM_ENDCAP_SEGMENTS * 2 - 1)
        arr.append(2)

        arr = numpy.array(arr, dtype=numpy.uint32)
        self.index_vbo = VBO(arr, target=GL.GL_ELEMENT_ARRAY_BUFFER)



        self.instance_dtype = numpy.dtype([
            ("pos_a", numpy.float32, 2),
            ("pos_b", numpy.float32, 2),
            ("thickness", numpy.float32, 1),
            #("color", numpy.float32, 4)
        ])

        # Use a fake array to get a zero-length VBO for initial binding
        instance_array = numpy.ndarray(0, dtype=self.instance_dtype)
        self.instance_vbo = VBO(instance_array)


        with self.__attribute_shader_vao, self.trace_vbo:
            vbobind(self.__attribute_shader, self.trace_vbo.dtype, "vertex").assign()
            vbobind(self.__attribute_shader, self.trace_vbo.dtype, "ptid").assign()

        with self.__attribute_shader_vao, self.instance_vbo:
            self.__bind_pos_a = vbobind(self.__attribute_shader, self.instance_dtype, "pos_a", div=1)
            self.__bind_pos_b =  vbobind(self.__attribute_shader, self.instance_dtype, "pos_b", div=1)
            self.__bind_thickness = vbobind(self.__attribute_shader, self.instance_dtype, "thickness", div=1)
            #vbobind(self.__attribute_shader, self.instance_dtype, "color", div=1).assign()
            self.__base_rebind(0)

            self.index_vbo.bind()

        self.__initialize_uniform(gls)

        self.__last_prepared = weakref.WeakKeyDictionary()

    def __base_rebind(self, base):
        self.__bind_pos_a.assign(base)
        self.__bind_pos_b.assign(base)
        self.__bind_thickness.assign(base)

    def restart(self):
        self.__prepared = False

        # Reset all VBOs
        for v in self.__deferred_layer.values():
            v.sel.clear()
            v.nonsel.clear()

        self.__needs_rebuild = False

    def __build_trace(self):
        # Update trace VBO
        self.working_array["vertex"][0] = (0,0)
        self.working_array["ptid"][0] = 0
        self.working_array["vertex"][1] = (0,0)
        self.working_array["ptid"][1] = 1

        end = Vec2(1,0)
        for i in range(0, NUM_ENDCAP_SEGMENTS):
            theta = math.pi * i/(NUM_ENDCAP_SEGMENTS - 1) + math.pi/2
            m = rotate(theta).dot(end.homol())
            self.working_array["vertex"][2 + i] = m[:2]
            self.working_array["ptid"][2 + i] = 0
            self.working_array["vertex"][2 + i + NUM_ENDCAP_SEGMENTS] = -m[:2]
            self.working_array["ptid"][2 + i + NUM_ENDCAP_SEGMENTS] = 1

        # Force data copy
        self.trace_vbo.copied = False
        self.trace_vbo.bind()


    def deferred(self, trace, render_settings):
        assert not self.__prepared
        assert not render_settings & RENDER_OUTLINES

        ls = self.__deferred_layer[trace.layer]

        if render_settings & RENDER_SELECTED:
            dest = ls.sel
        else:
            dest = ls.nonsel

        dest.add_thickline(trace.p0.x, trace.p0.y, trace.p1.x, trace.p1.y, trace.thickness/2)

    def render(self, mat):


        # Build and copy VBO. Track draw start/size per layer
        pos = {}

        accuum = VA_thickline(1024)
        for layer, ts in self.__deferred_layer.items():
            pos[layer, False] = (accuum.tell(), ts.nonsel.count())
            accuum.extend(ts.nonsel)

        for layer, ts in self.__deferred_layer.items():
            pos[layer, True] = (accuum.tell(), ts.sel.count())
            accuum.extend(ts.sel)


        self.instance_vbo.set_array(accuum.buffer()[:])
        self.instance_vbo.bind()


        with self.__attribute_shader, self.__attribute_shader_vao:
            GL.glUniformMatrix3fv(self.__attribute_shader.uniforms.mat, 1, True, mat.ctypes.data_as(GLI.c_float_p))

            for layer in self.__deferred_layer:
                with self.parent.compositor.get(layer):
                    for selected in (False, True):
                        first, count = pos[layer, selected]
                        if not count:
                            continue

                        if selected:
                            col = COL_SEL
                        else:
                            col = COL_LAYER_MAIN

                        self.__render_va_inner(col, False, first, count)


    def __render_va_inner(self, col, is_outline, first, count):
        GL.glUniform4ui(self.__attribute_shader.uniforms.layer_info, 255, col, 0, 0)


        if has_base_instance:
            # Many instances backport glDrawElementsInstancedBaseInstance
            # This is faster than continually rebinding, so support if possible
            if not is_outline:
                # filled traces come first in the array
                GL.glDrawElementsInstancedBaseInstance(GL.GL_TRIANGLES, TRIANGLES_SIZE, GL.GL_UNSIGNED_INT,
                                                       ctypes.c_void_p(0), count, first)
            else:
                # Then outline traces. We reuse the vertex data for the outside
                GL.glDrawArraysInstancedBaseInstance(GL.GL_LINE_LOOP, 2, NUM_ENDCAP_SEGMENTS * 2,
                                                     count, first)
        else:
            with self.instance_vbo:
                if not is_outline:
                    # filled traces come first in the array
                    self.__base_rebind(first)
                    GL.glDrawElementsInstanced(GL.GL_TRIANGLES, TRIANGLES_SIZE, GL.GL_UNSIGNED_INT,
                                               ctypes.c_void_p(0), count)
                else:
                    self.__base_rebind(first)
                    # Then outline traces. We reuse the vertex data for the outside
                    GL.glDrawArraysInstanced(GL.GL_LINE_LOOP, 2, NUM_ENDCAP_SEGMENTS * 2,
                                             count)

    def render_va(self, va, mat, col, is_outline=False, first=0, count=None):
        self.instance_vbo.set_array(va.buffer()[:])
        self.instance_vbo.bind()

        if count is None:
            count = va.count() - va.first()

        with self.__attribute_shader, self.__attribute_shader_vao:
            GL.glUniformMatrix3fv(self.__attribute_shader.uniforms.mat, 1, True, mat.ctypes.data_as(GLI.c_float_p))

            self.__render_va_inner(col, is_outline, first, count)



    # Immediate-mode render of a single trace
    # SLOW (at least for bulk-rendering)
    # Useful for rendering Ua elements
    def render_OLD(self, mat, trace, render_settings=RENDER_STANDARD):
        with self.__uniform_shader, self.__uniform_shader_vao:
            GL.glUniform1f(self.__uniform_shader.uniforms.thickness, trace.thickness/2)
            GL.glUniform2f(self.__uniform_shader.uniforms.pos_a, trace.p0.x, trace.p0.y)
            GL.glUniform2f(self.__uniform_shader.uniforms.pos_b, trace.p1.x, trace.p1.y)
            GL.glUniformMatrix3fv(self.__uniform_shader.uniforms.mat, 1, True, mat.ctypes.data_as(GLI.c_float_p))
            GL.glUniform4ui(self.__uniform_shader.uniforms.layer_info, 255, COL_LAYER_MAIN, 0, 0)

            if render_settings & RENDER_OUTLINES:
                GL.glDrawArrays(GL.GL_LINE_LOOP, 2, NUM_ENDCAP_SEGMENTS * 2)
            else:
                GL.glDrawElements(GL.GL_TRIANGLES, TRIANGLES_SIZE, GL.GL_UNSIGNED_INT, ctypes.c_void_p(0))
