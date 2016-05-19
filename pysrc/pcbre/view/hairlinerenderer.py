from collections import defaultdict
from pcbre.model.artwork_geom import Airwire
from pcbre.model.component import Component
from pcbre.model.const import SIDE
from pcbre.model.dipcomponent import DIPComponent
from pcbre.model.passivecomponent import PassiveComponent
from pcbre.model.smd4component import SMD4Component
from pcbre.view.componentview import dip_border_va, smd_border_va, passive_border_va, cmp_border_va
from pcbre.view.rendersettings import RENDER_STANDARD, RENDER_OUTLINES, RENDER_SELECTED, RENDER_HINT_NORMAL, \
    RENDER_HINT_ONCE
from pcbre.view.target_const import COL_SEL, COL_AIRWIRE, COL_CMP_LINE
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

from pcbre.accel.vert_array import VA_xy

class HairlineBatcher:
    """
    The HairLine Batcher manages 3 batches of hairlines:
        - Those showing component perimeters on the backside of the board
        - Those showing component perimeters on the frontside of the board

        - That showing Airwires
            Note: airwires are always drawn on the top side of the PCB, and are draw on unions of layers that are selected
            Therefore, the hairline batch is also updated on layer visibility changes
    """

    def __init__(self, hr, project):
        self.project = project

        self.hr = hr

        self.__last_selection_list = None
        self.__last_component_generation = None
        self.__last_airwire_generation = None
        self.__last_visible_lut = None

        self.__backside_va = VA_xy(1024)
        self.__frontside_va = VA_xy(1024)
        self.__airwire_va = VA_xy(1024)

        # We split each VA into two halves, so we draw the nonselected in one color,
        # and the selected in another
        self.__frontside_selected = None
        self.__backside_selected = None
        self.__airwire_selected = None

    def update_if_necessary(self, selection_list, layers_visible):

        # We only care about component or airwire selections
        filtered_selection_list = set(i for i in selection_list if isinstance(i, (Component, Airwire)))

        update_components = False
        update_airwires = False

        if self.__last_selection_list != filtered_selection_list:
            update_airwires = True
            update_components = True

        if self.__last_component_generation != self.project.artwork.components_generation:
            update_components = True

        if self.__last_airwire_generation != self.project.artwork.airwires_generation:
            update_airwires = True

        # We rebuild the airwire list on change-of-layers, since we don't expect many airwires
        # and they may start and end on different PCB layers
        if self.__last_visible_lut != layers_visible:
            update_airwires = True

        if not update_components and not update_airwires:
            return

        self.__last_selection_list = filtered_selection_list
        self.__last_component_generation = self.project.artwork.components_generation
        self.__last_airwire_generation = self.project.artwork.airwires_generation

        # reset the VAs for drawing
        self.__frontside_va.clear()
        self.__backside_va.clear()

        cmp_sel = [(x, x in filtered_selection_list) for x in self.project.artwork.components]

        seen_selected = False
        for component, selected in sorted(cmp_sel, key=lambda x: x[1]):

            # Update the split point. Since we draw all nonselected before selected
            # This is true for both frontside and backside
            if not seen_selected and selected:
                seen_selected = True
                self.__frontside_selected = self.__frontside_va.tell()
                self.__backside_selected = self.__backside_va.tell()

            #
            if component.side == SIDE.Top:
                dest = self.__frontside_va
            else:
                dest = self.__backside_va

            cmp_border_va(dest, component)


        # If we haven't updated the split point, do so now with nothing selected
        if not seen_selected:
            seen_selected = True
            self.__frontside_selected = self.__frontside_va.tell()
            self.__backside_selected = self.__backside_va.tell()

    def render_frontside(self, mat):
        self.hr.render_va(mat, self.__frontside_va, self.__frontside_selected, COL_CMP_LINE)

    def render_backside(self, mat):
        self.hr.render_va(mat, self.__backside_va, self.__backside_selected, COL_CMP_LINE)

    def render_airwires(self, mat):
        self.hr.render_va(mat, self.__airwire_va, self.__airwire_selected, COL_AIRWIRE)

class HairlineRenderer:


    def __init__(self, view):
        self.__view = view

    def initializeGL(self):
        self.__dtype = numpy.dtype([('vertex', numpy.float32, 2)])
        self.__shader = self.__view.gls.shader_cache.get("basic_fill_vert", "basic_fill_frag")

        self._va_vao = VAO()
        self._va_batch_vbo = VBO(numpy.array([], dtype=self.__dtype), GL.GL_STREAM_DRAW)


        with self._va_vao, self._va_batch_vbo:
            vbobind(self.__shader, self.__dtype, "vertex").assign()


    def render_va(self, mat, va, splitpoint, col):
        self._va_batch_vbo.set_array(va.buffer()[:])

        mat = numpy.array(mat, dtype=numpy.float32)
        with self.__shader, self._va_vao, self._va_batch_vbo:
            GL.glUniformMatrix3fv(self.__shader.uniforms.mat, 1, True, mat.ctypes.data_as(GLI.c_float_p))

            if splitpoint is None or splitpoint > 0:
                GL.glUniform4ui(self.__shader.uniforms.layer_info, 255, col, 0, 0)
                if splitpoint is None:
                    splitpoint = va.tell()
                GL.glDrawArrays(GL.GL_LINES, 0, splitpoint)

            if splitpoint is not None and va.tell() - splitpoint > 0:
                GL.glUniform4ui(self.__shader.uniforms.layer_info, 255, COL_SEL, 0, 0)
                GL.glDrawArrays(GL.GL_LINES, splitpoint, va.tell() - splitpoint)
