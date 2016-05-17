from collections import defaultdict
from pcbre.view.rendersettings import RENDER_STANDARD, RENDER_OUTLINES, RENDER_SELECTED, RENDER_HINT_NORMAL, \
    RENDER_HINT_ONCE
from pcbre.view.target_const import COL_SEL, COL_AIRWIRE
from pcbre.view.util import get_consolidated_draws_1, get_consolidated_draws

__author__ = 'davidc'
import math
from OpenGL import GL
from OpenGL.arrays.vbo import VBO
import numpy
from pcbre import units
from pcbre.matrix import Rect, translate, rotate, Point2, scale, Vec2
from pcbre.ui.gl import VAO, vbobind, glimports as GLI
import ctypes


class HairlineRenderer:

    # VBOs and associated VAOs for drawing data
    class _RenderData:
        def __init__(self, dtype, shader, glhint):
            self.__dtype = dtype

            self.vao = VAO()
            self.batch_vbo = VBO(numpy.array([], dtype=dtype), glhint)

            with self.vao, self.batch_vbo:
                vbobind(shader, dtype, "vertex").assign()

            self.clear()

        def clear(self):
            self.__vbo_update = True
            self.__groups = defaultdict(list)
            self.__group_lookup = {}
            self.group_offsets = {}


        def build_vbo(self):
            if not self.__vbo_update:
                return

            self.__vbo_update = False

            self.group_offsets = {}

            built_list = []
            for group, points in self.__groups.items():
                self.group_offsets[group] = len(built_list)
                built_list.extend([(i,) for i in points])

            if not built_list:
                return

            ar = numpy.array(built_list, dtype=self.__dtype)

            self.batch_vbo.data = ar
            self.batch_vbo.size = None
            self.batch_vbo.copied = False
            self.batch_vbo.bind()

        def last_index(self, group):
            return len(self.__groups[group])


        def add_point(self, p1, p2, group):
            group = self.__groups[group]
            idx = len(group) // 2
            group.append(p1)
            group.append(p2)
            self.__vbo_update = True
            return idx

        def get_point_index(self, p1, p2, group):
            key = group, p1.intTuple(), p2.intTuple()
            try:
                return self.__group_lookup[key]
            except KeyError:
                pass

            idx = self.__group_lookup[key] = self.add_point(p1, p2, group)
            return idx

    class _Reservation:
        def __init__(self, group, first, last):
            self.first = first
            self.last = last
            self.group = group

    class _ReservationBuilder:
        def __init__(self, group, adder, first):
            self.__group = group
            self.__adder = adder
            self.__first = first
            self.__last = first
            self.__done = False

        def add(self, p1, p2):
            assert not self.__done
            self.__last = self.__adder(p1, p2, self.__group)

        def finalize(self):
            self.__done = True
            return HairlineRenderer._Reservation(self.__group, self.__first, self.__last)

    def __init__(self, view):
        self.__view = view

    def initializeGL(self):
        self.__dtype = numpy.dtype([('vertex', numpy.float32, 2)])
        self.__shader = self.__view.gls.shader_cache.get("basic_fill_vert", "basic_fill_frag")

        self.__recurring_draws = HairlineRenderer._RenderData(self.__dtype, self.__shader, GL.GL_STATIC_DRAW)
        self.__once_draws = HairlineRenderer._RenderData(self.__dtype, self.__shader, GL.GL_DYNAMIC_DRAW)

    def restart(self):
        self.__once_draws.clear()

        self.__draw_tags_once = defaultdict(list)
        self.__draw_tags_recur = defaultdict(list)
        self.__draw_resv = defaultdict(list)

    def new_reservation(self, group):
        return HairlineRenderer._ReservationBuilder(group, self.__recurring_draws.add_point, self.__recurring_draws.last_index(group)//2)

    def deferred(self, p1, p2, group, hint=RENDER_HINT_NORMAL):
        if hint & RENDER_HINT_ONCE:
            idx = self.__once_draws.add_point(p1, p2, group)
            self.__draw_tags_once[group].append((idx, COL_SEL))
        else:
            idx = self.__recurring_draws.get_point_index(p1, p2, group)
            self.__draw_tags_recur[group].append((idx, COL_AIRWIRE))

    def deferred_reservation(self, reservation, info, group):
        self.__draw_resv[group].append((reservation, info))


    def __render_class(self, offset, tags, reservations=[]):
        info_batches = defaultdict(list)
        for idx, info in tags:
            info_batches[info].append((idx, idx + 1))

        for reservation, info in reservations:
            info_batches[info].append((reservation.first, reservation.last + 1))

        for info, indicies in info_batches.items():
            batches = get_consolidated_draws(indicies)
            GL.glUniform4ui(self.__shader.uniforms.layer_info, 255, info, 0, 0)
            for first, last in batches:
                GL.glDrawArrays(GL.GL_LINES, offset + first * 2, (last - first) * 2)

    def render_group(self, mat, group):
        self.__recurring_draws.build_vbo()
        self.__once_draws.build_vbo()

        recur_tags = self.__draw_tags_recur[group]
        res_tags = self.__draw_resv[group]
        once_tags = self.__draw_tags_once[group]

        # Skip expensive parts if no draws
        if not recur_tags and not res_tags and not once_tags:
            return

        # Overall, setup the shader and the matrix
        mat = numpy.array(mat, dtype=numpy.float32)
        with self.__shader:
            GL.glUniformMatrix3fv(self.__shader.uniforms.mat, 1, True, mat.ctypes.data_as(GLI.c_float_p))

            # For the one-off draws, render that data
            if once_tags:
                with self.__once_draws.vao:
                    self.__render_class(self.__once_draws.group_offsets[group], once_tags)

            # For the recurring draws, render that data
            if recur_tags or res_tags:
                with self.__recurring_draws.vao:
                    self.__render_class(self.__recurring_draws.group_offsets[group], recur_tags, res_tags)

