from pcbre.accel.vert_array import VA_thickline

__author__ = 'davidc'
import math
from OpenGL import GL  # type: ignore
from OpenGL.arrays.vbo import VBO  # type: ignore
import numpy
from pcbre.matrix import rotate, Vec2
from pcbre.ui.gl import VAO, VBOBind, glimports as GLI
import ctypes
from pcbre.view.target_const import COL_LAYER_MAIN, COL_SEL

from typing import TYPE_CHECKING, Optional, Any

if TYPE_CHECKING:
    from pcbre.ui.boardviewwidget import BoardViewWidget
    from pcbre.ui.gl.glshared import GLShared
    from pcbre.ui.gl.shader import EnhShaderProgram
    from pcbre.accel.vert_array import VA_thickline
    import numpy.typing as npt

NUM_ENDCAP_SEGMENTS = 32
TRIANGLES_SIZE = (NUM_ENDCAP_SEGMENTS - 1) * 3 * 2 + 3 * 2

FIRST_LINE_LOOP = NUM_ENDCAP_SEGMENTS * 2 + 2
LINE_LOOP_SIZE = NUM_ENDCAP_SEGMENTS * 2

# TODO: Detect automatically
has_base_instance = True


class TraceRender:
    def __init__(self, parent_view: 'BoardViewWidget') -> None:
        self.parent = parent_view
        self.restart()

    def initializeGL(self, gls: 'GLShared') -> None:
        # Build trace vertex VBO and associated vertex data
        dtype = [("vertex", numpy.float32, 2), ("ptid", numpy.uint32)]
        self.working_array = numpy.zeros(NUM_ENDCAP_SEGMENTS * 2 + 2, dtype=dtype)
        self.trace_vbo = VBO(self.working_array, GL.GL_DYNAMIC_DRAW)
        GL.glObjectLabel(GL.GL_BUFFER, int(self.trace_vbo), -1, "Thickline Trace VBO")

        # Generate geometry for trace and endcaps
        # ptid is a variable with value 0 or 1 that indicates which endpoint the geometry is associated with
        self.__build_trace()

        self.__attribute_shader_vao = VAO(debug_name="Thickline attribute shader VAO")
        shader = gls.shader_cache.get(
            "line_vertex_shader", "basic_fill_frag", defines={"INPUT_TYPE": "in"})
        assert shader is not None
        self.__attribute_shader : 'EnhShaderProgram' = shader

        # Now we build an index buffer that allows us to render filled geometry from the same
        # VBO.
        arr = []
        for i in range(NUM_ENDCAP_SEGMENTS - 1):
            arr.append(0)
            arr.append(i + 2)
            arr.append(i + 3)

        for i in range(NUM_ENDCAP_SEGMENTS - 1):
            arr.append(1)
            arr.append(i + NUM_ENDCAP_SEGMENTS + 2)
            arr.append(i + NUM_ENDCAP_SEGMENTS + 3)

        arr.append(2)
        arr.append(2 + NUM_ENDCAP_SEGMENTS - 1)
        arr.append(2 + NUM_ENDCAP_SEGMENTS)
        arr.append(2 + NUM_ENDCAP_SEGMENTS)
        arr.append(2 + NUM_ENDCAP_SEGMENTS * 2 - 1)
        arr.append(2)

        arr2 = numpy.array(arr, dtype=numpy.uint32)
        self.index_vbo = VBO(arr2, target=GL.GL_ELEMENT_ARRAY_BUFFER)
        GL.glObjectLabel(GL.GL_BUFFER, int(self.index_vbo), -1, "Thickline Index VBO")

        self.instance_dtype = numpy.dtype([
            ("pos_a", numpy.float32, 2),
            ("pos_b", numpy.float32, 2),
            ("thickness", numpy.float32),
            # ("color", numpy.float32, 4)
        ])


        # Use a fake array to get a zero-length VBO for initial binding
        instance_array : 'npt.NDArray[Any]' = numpy.ndarray(0, dtype=self.instance_dtype)
        self.instance_vbo = VBO(instance_array)
        GL.glObjectLabel(GL.GL_BUFFER, int(self.instance_vbo), -1, "Thickline Instance VBO")

        with self.__attribute_shader_vao, self.trace_vbo:
            VBOBind(self.__attribute_shader.program, self.trace_vbo.dtype, "vertex").assign()
            VBOBind(self.__attribute_shader.program, self.trace_vbo.dtype, "ptid").assign()

        with self.__attribute_shader_vao, self.instance_vbo:
            self.__bind_pos_a = VBOBind(self.__attribute_shader.program, self.instance_dtype, "pos_a", div=1)
            self.__bind_pos_b = VBOBind(self.__attribute_shader.program, self.instance_dtype, "pos_b", div=1)
            self.__bind_thickness = VBOBind(self.__attribute_shader.program, self.instance_dtype, "thickness", div=1)
            # vbobind(self.__attribute_shader, self.instance_dtype, "color", div=1).assign()
            self.__base_rebind(0)

            self.index_vbo.bind()

    def __base_rebind(self, base: int) -> None:
        self.__bind_pos_a.assign(base)
        self.__bind_pos_b.assign(base)
        self.__bind_thickness.assign(base)

    def restart(self) -> None:
        pass

    def __build_trace(self) -> None:
        # Update trace VBO
        self.working_array["vertex"][0] = (0, 0)
        self.working_array["ptid"][0] = 0
        self.working_array["vertex"][1] = (0, 0)
        self.working_array["ptid"][1] = 1

        end = Vec2(1, 0)
        for i in range(0, NUM_ENDCAP_SEGMENTS):
            theta = math.pi * i/(NUM_ENDCAP_SEGMENTS - 1) + math.pi/2
            m = rotate(theta).dot(end.homol())
            self.working_array["vertex"][2 + i] = m[:2]
            self.working_array["ptid"][2 + i] = 0
            self.working_array["vertex"][2 + i + NUM_ENDCAP_SEGMENTS] = -m[:2]
            self.working_array["ptid"][2 + i + NUM_ENDCAP_SEGMENTS] = 1

        # Force data copy
        self.trace_vbo.bind()
        self.trace_vbo.set_array(self.working_array)

    def __render_va_inner(self, col: int, is_outline: bool, first: int, count: int) -> None:
        GL.glUniform4ui(self.__attribute_shader.uniforms.layer_info, 255, col, 0, 0)

        if has_base_instance:
            # Many GL implementations backport glDrawElementsInstancedBaseInstance
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

    def render_va(self, va: 'VA_thickline', mat: 'npt.NDArray[numpy.float64]', col: int, is_outline: bool=False, first:int=0, count: 'Optional[int]'=None) -> None:
        if len(va.buffer()) == 0:
            return

        GL.glPushDebugGroup(GL.GL_DEBUG_SOURCE_APPLICATION, 0, -1, "Thickline Draw")
        assert self.instance_dtype.itemsize == va.stride

        self.instance_vbo.set_array(va.buffer()[:])

        if count is None:
            count = va.count() - first

        with self.__attribute_shader.program, self.__attribute_shader_vao, self.instance_vbo:
            GL.glUniformMatrix3fv(self.__attribute_shader.uniforms.mat, 1, True, mat.astype(numpy.float32))

            self.__render_va_inner(col, is_outline, first, count)
        GL.glPopDebugGroup()
