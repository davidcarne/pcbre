import math
from pcbre.matrix import Rect, Point2, Vec2
from pcbre.model.const import SIDE
import weakref
from pcbre.ui.gl.textrender import TextBatch

class ComponentTextBatcher:
    def __init__(self, view, project, text_renderer):
        self.__text = text_renderer
        self.__project = project
        self.__view = view

        self.__top_side_labels = TextBatch(text_renderer)
        self.__top_side_pads = TextBatch(text_renderer)
        self.__bottom_side_labels = TextBatch(text_renderer)
        self.__bottom_side_pads = TextBatch(text_renderer)

        self.__last_generation = None

        self.__up_vector = Vec2(0, 1)
        self.__ltor_vector = Vec2(1, 0)


    def initializeGL(self):
        self.__top_side_pads.initializeGL()
        self.__bottom_side_pads.initializeGL()
        self.__top_side_labels.initializeGL()
        self.__bottom_side_labels.initializeGL()

    def __needs_rebuild(self):
        needs_rebuild = False
        # Check if we need to rebuild component text
        if self.__project.artwork.components_generation != self.__last_generation:
            needs_rebuild = True

        up_unit_vector = Point2(self.__view.viewState.revMatrix.dot((0,1,0))[:2]).norm()
        ltor_unit_vector = Point2(self.__view.viewState.revMatrix.dot((1,0,0))[:2]).norm()

        if math.acos(round(float(up_unit_vector.dot(self.__up_vector)), 8)) > 0.01:
            needs_rebuild = True

        if math.acos(round(float(ltor_unit_vector.dot(self.__ltor_vector)), 8)) > 0.01:
            needs_rebuild = True


        self.__up_vector = up_unit_vector
        self.__ltor_vector = ltor_unit_vector
        self.__last_generation = self.__project.artwork.components_generation

        return needs_rebuild

    def update_if_necessary(self):
        if not self.__needs_rebuild():
            return

        components = self.__project.artwork.components

        self.__top_side_pads.restart()
        self.__top_side_labels.restart()
        self.__bottom_side_labels.restart()
        self.__bottom_side_pads.restart()

        for cmp in components:
            if cmp.side == SIDE.Top:
                pad_batch = self.__top_side_pads
            else:
                pad_batch = self.__bottom_side_pads

            for pad in cmp.get_pads():
                if pad.is_through():
                    r = Rect.fromCenterSize(Point2(0,0), pad.l * 0.6, pad.w * 0.6)

                else:
                    r = Rect.fromCenterSize(Point2(0,0), pad.l*0.8, pad.w*0.8)

                mat = cmp.matrix.dot(pad.translate_mat)

                r_top = Rect.fromRect(r)

                s = "%s: %s" % (pad.pad_no, pad.pad_name)

                ti = pad_batch.get_string(s)
                text_mat = mat.dot(ti.get_render_to_mat(r_top))
                pad_batch.add(text_mat, ti)

        self.__top_side_pads.prepare()
        self.__top_side_labels.prepare()
        self.__bottom_side_labels.prepare()
        self.__bottom_side_pads.prepare()

    def render_layer(self, mat, side, labels):
        { (SIDE.Top, True): self.__top_side_labels,
          (SIDE.Top, False): self.__top_side_pads,
          (SIDE.Bottom, True): self.__bottom_side_labels,
          (SIDE.Bottom, False): self.__bottom_side_pads
        }[side, labels].render(mat)

