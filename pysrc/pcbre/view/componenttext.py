import math
from pcbre.matrix import Rect, Point2, Vec2
from pcbre.model.const import SIDE
from pcbre.ui.gl.textrender import TextBatch

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from pcbre.model.project import Project
    from pcbre.ui.gl.textrender import TextRender
    from pcbre.ui.boardviewwidget import BoardViewWidget
    import numpy
    

class ComponentTextBatcher:
    def __init__(self,
            view: "BoardViewWidget",
            project: "Project",
            text_renderer: "TextRender") -> None:

        self.__text = text_renderer
        self.__project = project
        self.__view = view

        self.__top_side_labels = TextBatch(text_renderer)
        self.__top_side_pads = TextBatch(text_renderer)
        self.__bottom_side_labels = TextBatch(text_renderer)
        self.__bottom_side_pads = TextBatch(text_renderer)

        self.__last_generation : Optional[int] = None

        self.__up_vector = Vec2(0, 1)
        self.__ltor_vector = Vec2(1, 0)

    def initializeGL(self) -> None:
        self.__top_side_pads.initializeGL()
        self.__bottom_side_pads.initializeGL()
        self.__top_side_labels.initializeGL()
        self.__bottom_side_labels.initializeGL()

    def needs_rebuild(self, update:bool=False) -> bool:
        needs_rebuild = False
        # Check if we need to rebuild component text
        if self.__project.artwork.components_generation != self.__last_generation:
            needs_rebuild = True

        up_unit_vector = Point2.from_mat(self.__view.viewState.revMatrix.dot((0, 1, 0))[:2]).norm()
        ltor_unit_vector = Point2.from_mat(self.__view.viewState.revMatrix.dot((1, 0, 0))[:2]).norm()

        if math.acos(round(float(up_unit_vector.dot(self.__up_vector)), 8)) > 0.01:
            needs_rebuild = True

        if math.acos(round(float(ltor_unit_vector.dot(self.__ltor_vector)), 8)) > 0.01:
            needs_rebuild = True

        if update:
            self.__up_vector = up_unit_vector
            self.__ltor_vector = ltor_unit_vector
            self.__last_generation = self.__project.artwork.components_generation

        return needs_rebuild

    def update_if_necessary(self) -> None:
        if not self.needs_rebuild(update=True):
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
                    r = Rect.from_center_size(Point2(0, 0), pad.length * 0.6, pad.width * 0.6)
                else:
                    r = Rect.from_center_size(Point2(0, 0), pad.length * 0.8, pad.width * 0.8)

                mat = cmp.matrix.dot(pad.translate_mat)

                r_top = r.copy()

                s = "%s: %s" % (pad.pad_no, pad.pad_name)

                ti = pad_batch.get_string(s)
                text_mat = mat.dot(ti.get_render_to_mat(r_top))
                pad_batch.add(text_mat, ti)

        self.__top_side_pads.prepare()
        self.__top_side_labels.prepare()
        self.__bottom_side_labels.prepare()
        self.__bottom_side_pads.prepare()

    def render_layer(self, mat: 'numpy.ArrayLike', side: SIDE, labels: bool) -> None:
        {
            (SIDE.Top, True): self.__top_side_labels,
            (SIDE.Top, False): self.__top_side_pads,
            (SIDE.Bottom, True): self.__bottom_side_labels,
            (SIDE.Bottom, False): self.__bottom_side_pads
        }[side, labels].render(mat)
