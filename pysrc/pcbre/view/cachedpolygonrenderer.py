from collections import defaultdict
from OpenGL import GL  # type: ignore
from OpenGL.arrays.vbo import VBO  # type: ignore
from pcbre.ui.gl import VAO, VBOBind, glimports as GLI
import ctypes
import numpy
from pcbre.matrix import Point2
from pcbre.view.rendersettings import RENDER_STANDARD, RENDER_OUTLINES, RENDER_SELECTED, RENDER_HINT_NORMAL
from pcbre.view.util import get_consolidated_draws

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from pcbre.ui.boardviewwidget import BoardViewWidget
    from pcbre.ui.gl.glshared import GLShared

__author__ = 'davidc'

class PolygonLayerCache:
    """Per-layer VA that stores polygon geometry"""

    # Sentinel value for the Index used to indicate a new primitive
    RESTART_INDEX = 2 ** 32 - 1

    def __init__(self) -> None:
        # Ordered sequence of polygon points
        self.__position_list : List[Point2] = []

        # Lookup (point->index) for deduping points
        self.__position_lookup : dict[Point2, int] = {}

        # Mapping from polygon -> tuple (start, count) for drawing a polygon's triangles
        # or outlines
        self.__tri_draw_ranges = {}
        self.__outline_draw_ranges = {}

        self.__tri_index_list = []
        self.__outline_index_list = []

    @property
    def position_list(self):
        return self.__position_list

    @property
    def tri_index_list(self):
        return self.__tri_index_list

    @property
    def outline_index_list(self):
        return self.__outline_index_list

    def __get_position_index(self, point: Point2) -> int:
        """
        Get the index in the point VBO for a given Point2 coordinate
        :type point: pcbre.matrix.Point2
        :param point:
        :return:
        """
        norm_pos = point.to_int_tuple()

        try:
            return self.__position_lookup[norm_pos]
        except KeyError:
            self.__position_lookup[norm_pos] = len(self.__position_list)
            self.__position_list.append(norm_pos)

        return self.__position_lookup[norm_pos]

    def add(self, polygon):
        tris = polygon.get_tris_repr()
        tri_index_first = len(self.__tri_index_list)

        for t in tris:
            for p in t.a, t.b, t.c:
                self.__tri_index_list.append(self.__get_position_index(Point2(p.x, p.y)))

        tr = (tri_index_first, len(self.__tri_index_list))
        self.__tri_draw_ranges[polygon] = tr

        outline_index_first = len(self.__outline_index_list)
        poly_repr = polygon.get_poly_repr()
        for edge in [poly_repr.exterior] + list(poly_repr.interiors):
            for pt in edge.coords:
                self.__outline_index_list.append(self.__get_position_index(Point2(pt[0], pt[1])))
            self.__outline_index_list.append(self.RESTART_INDEX)

        lr = (outline_index_first, len(self.__outline_index_list))
        self.__outline_draw_ranges[polygon] = lr


        return tr, lr

class PolygonRenderer:
    def __init__(self, view):
        self.__gls = view.gls

    def initializeGL(self) -> None:
        self.__vao = VAO()

        # Lookup for vertex positions
        self.__vert_vbo_dtype = numpy.dtype([("vertex", numpy.float32, 2)])
        self.__vert_vbo = VBO(numpy.zeros((0,), dtype=self.__vert_vbo_dtype),
                              GL.GL_DYNAMIC_DRAW)

        self.__index_vbo_dtype = numpy.uint32
        self.__index_vbo = VBO(numpy.zeros((0,), dtype=self.__index_vbo_dtype), GL.GL_DYNAMIC_DRAW, GL.GL_ELEMENT_ARRAY_BUFFER)
        GL.glObjectLabel(GL.GL_BUFFER, int(self.__index_vbo), -1, "Polygon Index VBO")

        self.__shader = self.__gls.shader_cache.get("basic_fill_vert", "basic_fill_frag")

        with self.__vao, self.__vert_vbo:
            VBOBind(self.__shader.program, self.__vert_vbo_dtype, "vertex").assign()
            self.__index_vbo.bind()

        self.__data_to_render = False

    def render_prepare(self, cache):
        self.__data_to_render = False

        if len(cache.position_list) == 0:
            return

        if len(cache.tri_index_list) == 0:
            return

        # Update VBOs
        ar = numpy.zeros(len(cache.position_list), dtype=self.__vert_vbo_dtype)
        ar["vertex"] = cache.position_list
        self.__vert_vbo.set_array(ar)

        self.__tri_count = self.__outline_index_offset = len(cache.tri_index_list)
        self.__outline_count = len(cache.outline_index_list)

        data = numpy.array(cache.tri_index_list + cache.outline_index_list, dtype=self.__index_vbo_dtype)
        self.__index_vbo.set_array(data)

        self.__data_to_render = True
        self.__restart_index = cache.RESTART_INDEX

    def render_solid(self, matrix, col):
        if not self.__data_to_render:
            return

        with self.__shader.program, self.__vao, self.__index_vbo, self.__vert_vbo:
            # Draw the polygons
            GL.glUniformMatrix3fv(self.__shader.uniforms.mat, 1, True, matrix.astype(numpy.float32))
            GL.glUniform4ui(self.__shader.uniforms.layer_info, 255, col, 0, 0)
            GL.glDrawElements(GL.GL_TRIANGLES, self.__tri_count, GL.GL_UNSIGNED_INT, ctypes.c_void_p(0))

    def render_outline(self, matrix, col):
        if not self.__data_to_render:
            return

        with self.__shader.program, self.__vao, self.__index_vbo, self.__vert_vbo:
            GL.glEnable(GL.GL_PRIMITIVE_RESTART)
            GL.glPrimitiveRestartIndex(self.__restart_index)
            GL.glDrawElements(
                GL.GL_LINE_STRIP,
                self.__outline_count,
                GL.GL_UNSIGNED_INT,
                ctypes.c_void_p((self.__outline_index_offset) * 4))
            
            GL.glDisable(GL.GL_PRIMITIVE_RESTART)


