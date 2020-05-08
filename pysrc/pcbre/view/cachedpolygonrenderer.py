from collections import defaultdict
from OpenGL import GL
from OpenGL.arrays.vbo import VBO
from pcbre.ui.gl import VAO, vbobind, glimports as GLI
import ctypes
import numpy
from pcbre.matrix import Point2
from pcbre.view.rendersettings import RENDER_STANDARD, RENDER_OUTLINES, RENDER_SELECTED, RENDER_HINT_NORMAL
from pcbre.view.util import get_consolidated_draws

__author__ = 'davidc'


class PolygonVBOPair:
    __RESTART_INDEX = 2 ** 32 - 1

    def __init__(self, view):
        """
        :type gls: pcbre.ui.gl.glshared.GLShared
        :param gls:
        :return:
        """
        self.__view = view
        self.__gls = view.gls

        self.__position_list = []
        self.__position_lookup = {}

        # Known_polys is a list of (start,end) indicies in self.__index_list
        self.__tri_draw_ranges = {}
        self.__outline_draw_ranges = {}

        self.__tri_index_list = []
        self.__outline_index_list = []

        self.__vert_vbo_current = False
        self.__index_vbo_current = False

        self.restart()

    def restart(self):
        self.__deferred_tri_render_ranges = defaultdict(list)
        self.__deferred_line_render_ranges = defaultdict(list)

    def initializeGL(self):
        self.__vao = VAO()

        # Lookup for vertex positions
        self.__vert_vbo_dtype = numpy.dtype([("vertex", numpy.float32, 2)])
        self.__vert_vbo = VBO(numpy.ndarray(0, dtype=self.__vert_vbo_dtype),
                              GL.GL_DYNAMIC_DRAW)
        self.__vert_vbo_current = False

        self.__index_vbo_dtype = numpy.uint32
        self.__index_vbo = VBO(numpy.ndarray(0, dtype=self.__index_vbo_dtype), GL.GL_DYNAMIC_DRAW, GL.GL_ELEMENT_ARRAY_BUFFER)
        self.__index_vbo_current = False

        self.__shader = self.__gls.shader_cache.get("vert2", "frag1")

        with self.__vao, self.__vert_vbo:
            vbobind(self.__shader, self.__vert_vbo_dtype, "vertex").assign()
            self.__index_vbo.bind()

    def __update_vert_vbo(self):
        if self.__vert_vbo_current or not len(self.__position_list):
            return

        ar = numpy.ndarray(len(self.__position_list), dtype=self.__vert_vbo_dtype)
        ar["vertex"] = self.__position_list
        self.__vert_vbo.data = ar
        self.__vert_vbo.copied = False
        self.__vert_vbo.bind()
        self.__vert_vbo_current = True

    def __update_index_vbo(self):
        if self.__index_vbo_current or not len(self.__tri_index_list):
            return

        self.__outline_index_offset = len(self.__tri_index_list)
        self.__index_vbo.data = numpy.array(self.__tri_index_list + self.__outline_index_list, dtype=self.__index_vbo_dtype)
        self.__index_vbo.copied = False
        self.__index_vbo.bind()
        self.__index_vbo_current = True

    def __get_position_index(self, point):
        """
        Get the index in the point VBO for a given Point2 coordinate
        :type point: pcbre.matrix.Point2
        :param point:
        :return:
        """
        norm_pos = point.intTuple()

        try:
            return self.__position_lookup[norm_pos]
        except KeyError:
            self.__position_lookup[norm_pos] = len(self.__position_list)
            self.__position_list.append(norm_pos)
            self.__vert_vbo_current = False

        return self.__position_lookup[norm_pos]

    def __add(self, polygon):
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
                self.__outline_index_list.append(self.__get_position_index(Point2(pt)))
            self.__outline_index_list.append(self.__RESTART_INDEX)

        lr = (outline_index_first, len(self.__outline_index_list))
        self.__outline_draw_ranges[polygon] = lr

        self.__index_vbo_current = False

        return tr, lr

    def deferred(self, polygon, render_settings=RENDER_STANDARD):
        if polygon in self.__tri_draw_ranges:
            trange, lrange = self.__tri_draw_ranges[polygon], self.__outline_draw_ranges[polygon]
        else:
            trange, lrange = self.__add(polygon)

        if render_settings & RENDER_OUTLINES:
            self.__deferred_line_render_ranges[render_settings].append(lrange)
        else:
            self.__deferred_tri_render_ranges[render_settings].append(trange)

    def render(self, matrix, layer):
        self.__update_vert_vbo()
        self.__update_index_vbo()

        overall_color = self.__view.color_for_layer(layer)
        sel_color = self.__view.sel_colormod(True, overall_color)

        def _c_for_rs(rs):
            if rs & RENDER_SELECTED:
                return tuple(sel_color) + (1,)
            else:
                return tuple(overall_color) + (1,)

        with self.__shader, self.__vao:
            GL.glUniformMatrix3fv(self.__shader.uniforms.mat, 1, True, matrix.ctypes.data_as(GLI.c_float_p))

            for rs, ranges in self.__deferred_tri_render_ranges.items():
                tri_draw_list = get_consolidated_draws(ranges)
                GL.glUniform4f(self.__shader.uniforms.color, *_c_for_rs(rs))

                for first, last in tri_draw_list:
                    GL.glDrawElements(GL.GL_TRIANGLES, last - first, GL.GL_UNSIGNED_INT, ctypes.c_void_p(first * 4))

            GL.glEnable(GL.GL_PRIMITIVE_RESTART)
            GL.glPrimitiveRestartIndex(self.__RESTART_INDEX)
            for rs, ranges in self.__deferred_line_render_ranges.items():
                GL.glUniform4f(self.__shader.uniforms.color, *_c_for_rs(rs))
                line_draw_list = get_consolidated_draws(ranges)
                for first, last in line_draw_list:
                    GL.glDrawElements(
                        GL.GL_LINE_STRIP,
                        last - first,
                        GL.GL_UNSIGNED_INT,
                        ctypes.c_void_p((first + self.__outline_index_offset) * 4))

            GL.glDisable(GL.GL_PRIMITIVE_RESTART)


class CachedPolygonRenderer:
    def __init__(self, view):
        self.__layer_arrays = {}
        self.__view = view

    def initializeGL(self):
        for v in self.__layer_arrays.values():
            v.initializeGL()

    def restart(self):
        for v in self.__layer_arrays.values():
            v.restart()

    def deferred(self, polygon, rendersettings, render_hint=RENDER_HINT_NORMAL):
        if polygon.layer not in self.__layer_arrays:
            self.__layer_arrays[polygon.layer] = PolygonVBOPair(self.__view)
            self.__layer_arrays[polygon.layer].initializeGL()

        self.__layer_arrays[polygon.layer].deferred(polygon, rendersettings)

    def render(self, matrix, layer):
        if layer in self.__layer_arrays:
            self.__layer_arrays[layer].render(matrix, layer)
