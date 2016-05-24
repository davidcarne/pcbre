from collections import defaultdict
from pcbre.accel.vert_array import VA_xy, VA_via, VA_tex, VA_thickline
from pcbre.model.artwork_geom import Trace, Via
from pcbre.model.component import Component
from pcbre.model.const import SIDE
from pcbre.model.pad import Pad

from pcbre.view.componentview import cmp_border_va


class RenderPCBLayer:
    # PCB layers have traces, text
    def __init__(self):
        self.va_traces = VA_thickline(1024)
        self.va_text = VA_tex(1024)

    def clear(self):
        self.va_traces.clear()
        self.va_text.clear()

    def extend(self, other):
        self.va_traces.extend(other.va_traces)
        self.va_text.extend(other.va_text)

class RenderSide:
    # On the sides, we only have component outlines and component text
    def __init__(self):
        self.va_outlines = VA_xy(1024)
        self.va_text = VA_tex(1024)

    def clear(self):
        self.va_outlines.clear()
        self.va_text.clear()

    def extend(self, other):
        self.va_outlines.extend(other.va_outlines)
        self.va_text.extend(other.va_text)


class RenderVia:
    # Multilayer, we only have vias, and pin labels
    def __init__(self):
        self.va_vias = VA_via(1024)
        self.va_text = VA_tex(1024)

    def clear(self):
        self.va_vias.clear()
        self.va_text.clear()

    def extend(self, other):
        self.va_vias.extend(other.va_vias)
        self.va_text.extend(other.va_text)

class StackupRenderCommands:
    def __init__(self):
        self.layers = defaultdict(RenderPCBLayer)
        self.sides = {
            SIDE.Top: RenderSide(),
            SIDE.Bottom: RenderSide()
        }
        self.multi = RenderVia()
        self.vias = defaultdict(RenderVia)

    def clear(self):
        for i in self.layers.values():
            i.clear()

        for i in self.sides.values():
            i.clear()

        for i in self.vias.values():
            i.clear()

        self.multi.clear()

    def extend(self, other):
        for k, v in self.layers.items():
            v.extend(other.layers[k])

        for k, v in self.sides.items():
            v.extend(other.sides[k])

        for k, v in self.vias.items():
            v.extend(other.vias[k])

        self.multi.extend(other.multi)

class CADCache:
    def __init__(self, project):
        """
        :type project: pcbre.model.project.Project
        :param project:
        :return:
        """
        self.__project = project

        self.__traces_cache = StackupRenderCommands()
        self.__vias_cache = StackupRenderCommands()
        self.__cmp_cache = StackupRenderCommands()

        self.__trace_generation = None
        self.__vias_generation = None
        self.__cmp_generation = None


    def update_if_necessary(self):

        # Update traces as necessary
        if self.__trace_generation != self.__project.artwork.traces_generation:

            self.__trace_generation = self.__project.artwork.traces_generation
            self.__traces_cache.clear()
            for t in self.__project.artwork.traces:
                self.__traces_cache.layers[t.layer].va_traces.add_trace(t)


        if self.__vias_generation != self.__project.artwork.vias_generation:
            self.__vias_generation = self.__project.artwork.vias_generation

            self.__vias_cache.clear()
            for v in self.__project.artwork.vias:
                self.__vias_cache.vias[v.viapair].va_vias.add_via(v)


        if self.__cmp_generation != self.__project.artwork.components_generation:
            self.__cmp_generation = self.__project.artwork.components_generation

            self.__cmp_cache.clear()

            for cmp in self.__project.artwork.components:
                cmp_border_va(self.__cmp_cache.sides[cmp.side].va_outlines, cmp)

                for pad in cmp.get_pads():
                    if pad.is_through():
                        self.__cmp_cache.multi.va_vias.add_th_pad(pad)
                        # TODO, add text
                    else:
                        self.__cmp_cache.layers[self.__project.stackup.layer_for_side(pad.side)].va_traces.add_trace(pad.trace_repr)

    def extendTo(self, target):
        """
        :type target: StackupRenderCommands
        :param target:
        :return:
        """

        target.extend(self.__traces_cache)
        target.extend(self.__vias_cache)
        target.extend(self.__cmp_cache)

class SelectionHighlightCache:
    def __init__(self, project):
        self.__project = project

        self.__via_generation = None
        self.__traces_generation = None
        self.__component_generation = None
        self.__last_selection = None

        self.thickline_va = VA_thickline(1024)
        self.thinline_va = VA_xy(1024)
        self.via_va = VA_via(1024)


    def update_if_necessary(self, selection_list):
        if (self.__last_selection == selection_list and
            self.__project.artwork.components_generation == self.__component_generation and
            self.__project.artwork.traces_generation == self.__traces_generation and
            self.__project.artwork.vias_generation == self.__via_generation):
            return

        self.__via_generation = self.__project.artwork.vias_generation
        self.__traces_generation = self.__project.artwork.traces_generation
        self.__component_generation = self.__project.artwork.components_generation

        self.__last_selection = selection_list

        self.thickline_va.clear()
        self.thinline_va.clear()
        self.via_va.clear()

        for i in selection_list:
            if isinstance(i, Trace):
                self.thickline_va.add_trace(i)
            elif isinstance(i, Via):
                self.via_va.add_via(i)
            elif isinstance(i, Pad):
                if i.is_through():
                    self.via_va.add_th_pad(i)
                else:
                    self.thickline_va.add_trace(i.trace_repr)
            elif isinstance(i, Component):
                cmp_border_va(self.thinline_va, i)
                for j in i.get_pads():
                    if j.is_through():
                        self.via_va.add_th_pad(j)
                    else:
                        self.thickline_va.add_trace(j.trace_repr)






