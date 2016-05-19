from collections import defaultdict
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

class _TraceRenderBatch:
    def __init__(self, parent):
        self.parent = parent

    def _initializeGL(self):
        pass

class TraceRender:
    def __init__(self, parent_view):
        self.parent = parent_view

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
        self.__deferred_layer = defaultdict(list)
        self.__prepared = False
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



    def deferred_multiple(self, trace_settings, render_settings=0):
        """
        :param trace_settings: list of traces to draw and the settings for that particular trace
        :param render_settings:
        :return:
        """
        for t, tr in trace_settings:
            tr |= render_settings
            self.deferred(t, tr)

    def deferred(self, trace, render_settings, render_hint):
        assert not self.__prepared
        self.__deferred_layer[trace.layer].append((trace, render_settings))
        if trace not in self.__last_prepared:
            self.__needs_rebuild = True

    def prepare(self):
        """
        :return: Build VBOs and information for rendering pass
        """
        self.__prepared = True

        if not self.__needs_rebuild:
            return

        self.__last_prepared = weakref.WeakKeyDictionary()

        # Total trace count, across all layers
        count = sum(len(i) for i in self.__deferred_layer.values())

        # Allocate an array of that size
        instance_array = numpy.ndarray(count, dtype = self.instance_dtype)

        pos = 0
        for layer, traces in self.__deferred_layer.items():
            # We reorder the traces to batch them by outline, and net to encourage
            # maximum draw call length. The rationale is that nets are commonly selected
            # or may be commonly drawn in different colors.
            traces = sorted(traces, key=lambda i: (i[1] & RENDER_OUTLINES, id(i[0].net)))

            for trace, _ in traces:
                # Now insert into the array
                instance_array[pos] = (trace.p0, trace.p1, trace.thickness/2)

                # And memoize where the trace occurs
                self.__last_prepared[trace] = pos

                pos += 1

        # Force full resend of VBO
        self.instance_vbo.data = instance_array
        self.instance_vbo.size = None
        self.instance_vbo.copied = False
        self.instance_vbo.bind()


    def render_deferred_layer(self, mat, layer):
        if not self.__prepared:
            self.prepare()

        trace_settings = self.__deferred_layer[layer]

        count = len(trace_settings)
        if count == 0:
            return

        # key format: is_selected, is_outline
        draw_bins = defaultdict(list)
        draw_range_bins = dict()

        # Bin the traces by draw call
        for t, tr in trace_settings:
            is_selected = bool(tr & RENDER_SELECTED)
            is_outline = bool(tr & RENDER_OUTLINES)
            draw_bins[is_selected, is_outline].append(self.__last_prepared[t])

        # Build draw ranges
        for key, bin in draw_bins.items():
            draw_range_bins[key] = get_consolidated_draws_1(draw_bins[key])


        # HACK / Fixme: Precalculate selected / nonselected colors
        color_a = self.parent.color_for_layer(layer) + [1]
        color_sel = self.parent.sel_colormod(True, color_a)

        has_base_instance = False
        with self.__attribute_shader, self.__attribute_shader_vao:
            # Setup overall calls
            GL.glUniformMatrix3fv(self.__attribute_shader.uniforms.mat, 1, True, mat.ctypes.data_as(GLI.c_float_p))

            # We order the draw calls such that selected areas are drawn on top of nonselected.
            sorted_kvs = sorted(draw_range_bins.items(), key=lambda i: i[0][0])
            for (is_selected, is_outline), ranges in sorted_kvs:

                if is_selected:
                    GL.glUniform4ui(self.__attribute_shader.uniforms.layer_info, 255, COL_SEL, 0, 0)
                else:
                    GL.glUniform4ui(self.__attribute_shader.uniforms.layer_info, 255, COL_LAYER_MAIN, 0, 0)

                if has_base_instance:
                    # Many instances backport glDrawElementsInstancedBaseInstance
                    # This is faster than continually rebinding, so support if possible
                    if not is_outline:
                        for first, last in ranges:
                            # filled traces come first in the array
                            GL.glDrawElementsInstancedBaseInstance(GL.GL_TRIANGLES, TRIANGLES_SIZE, GL.GL_UNSIGNED_INT,
                                                                   ctypes.c_void_p(0), last - first, first)
                    else:
                        for first, last in ranges:
                            # Then outline traces. We reuse the vertex data for the outside
                            GL.glDrawArraysInstancedBaseInstance(GL.GL_LINE_LOOP, 2, NUM_ENDCAP_SEGMENTS * 2,
                                                                 last - first, first)
                else:
                    with self.instance_vbo:
                        if not is_outline:
                            for first, last in ranges:
                                # filled traces come first in the array
                                self.__base_rebind(first)
                                GL.glDrawElementsInstanced(GL.GL_TRIANGLES, TRIANGLES_SIZE, GL.GL_UNSIGNED_INT,
                                                                       ctypes.c_void_p(0), last - first)
                        else:
                            for first, last in ranges:
                                self.__base_rebind(first)
                                # Then outline traces. We reuse the vertex data for the outside
                                GL.glDrawArraysInstanced(GL.GL_LINE_LOOP, 2, NUM_ENDCAP_SEGMENTS * 2,
                                                                     last - first)

    # Immediate-mode render of a single trace
    # SLOW (at least for bulk-rendering)
    # Useful for rendering UI elements
    def render(self, mat, trace, render_settings=RENDER_STANDARD):
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
