import math
from pcbre import units
from pcbre.matrix import Rect, Point2, project_point, Vec2
from pcbre.model.dipcomponent import DIPComponent
from pcbre.model.passivecomponent import Passive2BodyType, Passive2Component
from pcbre.model.smd4component import SMD4Component

__author__ = 'davidc'

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy.typing as ndt
    from pcbre.model.pad import Pad
    import numpy
    from pcbre.model.component import Component
    from pcbre.ui.boardviewwidget import BoardViewWidget
    from pcbre.accel.vert_array import VA_xy, VA_thickline


TRANSITION_POINT_1 = 20
TRANSITION_POINT_2 = 50
RATIO = 0.6
RGAP = 0.1


def _text_to(view: 'BoardViewWidget', pad: 'Pad', r: Rect, mat: 'ndt.NDArray[numpy.float64]', textcol_a: float) -> None:
    mat = mat.dot(pad.translate_mat)

    # zero-out rotation
    mat[0:2, 0:2] = view.viewState.glMatrix[0:2, 0:2]

    # Hack
    text_height_px = view.viewState.scale_factor * r.height

    # Hack
    pname = pad.pad_name

    if text_height_px < 14:
        alpha = 0
        textcol_a[3] = (text_height_px - 6) / 8

        if text_height_px < 6:
            return
    elif 14 <= text_height_px <= TRANSITION_POINT_1:
        alpha = 0
    elif text_height_px > TRANSITION_POINT_1:
        if pname != "":
            if text_height_px > TRANSITION_POINT_2:
                alpha = 1
            else:
                alpha = (text_height_px - TRANSITION_POINT_1) / (TRANSITION_POINT_2 - TRANSITION_POINT_1)
        else:
            alpha = 0

    h_delta_1 = r.height * (1 - RATIO * alpha)
    h_delta_2 = r.height * (RATIO - RGAP) * alpha

    r_top = Rect.fromRect(r)
    r_top.bottom = r_top.top - h_delta_1

    r.top = r.bottom + h_delta_2

    view.text_batch.submit_text_box(mat, "%s" % pad.pad_no, r_top, textcol_a, None)
    if alpha:
        view.text_batch.submit_text_box(mat, "%s" % pname, r, textcol_a, None)


def passive_border_va(va: 'VA_xy', cmp: 'Passive2Component') -> None:
    """
    :type cmp: pcbre.model.passivecomponent.Passive2Component
    :type va: pcbre.accel.vert_array.VA_xy
    :param cmp:
    :return:
    """

    if cmp.body_type == Passive2BodyType.CHIP:
        bx = cmp.body_corner_vec.x
        by = cmp.body_corner_vec.y
        va.add_box(cmp.center.x, cmp.center.y, bx * 2, by * 2, cmp.theta)

    elif cmp.body_type == Passive2BodyType.TH_AXIAL:
        bx = cmp.body_corner_vec.x
        by = cmp.body_corner_vec.y
        va.add_box(cmp.center.x, cmp.center.y, bx * 2, by * 2, cmp.theta)

        vec = Vec2(math.cos(cmp.theta), math.sin(cmp.theta))

        # Add legs
        pa = cmp.pin_d * vec
        pb = cmp.body_corner_vec.x * vec
        va.add_line(pa.x + cmp.center.x, pa.y + cmp.center.y, pb.x + cmp.center.x, pb.y + cmp.center.y)
        va.add_line(-pa.x + cmp.center.x, -pa.y + cmp.center.y, -pb.x + cmp.center.x, -pb.y + cmp.center.y)

    elif cmp.body_type == Passive2BodyType.TH_RADIAL:
        raise NotImplementedError()
    else:
        raise NotImplementedError()


def dip_border_va(va_xy: 'VA_xy', dip: 'DIPComponent') -> None:
    by = dip.body_length() / 2

    r = units.MM

    va_xy.add_box(dip.center.x, dip.center.y, dip.body_width(), dip.body_length(), dip.theta)

    pt_center = project_point(dip.matrix, Point2(0, by))
    va_xy.add_arc(pt_center.x, pt_center.y, r, dip.theta + math.pi, dip.theta, 28)


def smd_border_va(va_xy: 'VA_xy', smd: 'SMD4Component') -> None:
    va_xy.add_box(smd.center.x, smd.center.y, smd.dim_2_body, smd.dim_1_body, smd.theta)

    # Calculate size / position of marker
    scale = min(smd.dim_1_body, smd.dim_2_body) / 5
    if scale > units.MM:
        scale = units.MM
    if scale < units.MM/5:
        scale = units.MM/5

    size = scale/2
    offs = scale
    posx = -smd.dim_2_body/2 + offs
    posy = smd.dim_1_body/2 - offs

    pt = project_point(smd.matrix, Point2(posx, posy))
    va_xy.add_circle(pt.x, pt.y, size, 40)


def cmp_border_va(dest: 'VA_xy', component: 'Component') -> None:
    if isinstance(component, DIPComponent):
        dip_border_va(dest, component)
    elif isinstance(component, SMD4Component):
        smd_border_va(dest, component)
    elif isinstance(component, Passive2Component):
        passive_border_va(dest, component)


def cmp_pad_periph_va(va_xy: "VA_xy", va_trace: 'VA_thickline', component: 'Component'):
    for i in component.get_pads():
        if i.is_through():
            va_xy.add_circle(i.center.x, i.center.y, i.width/2)
        else:
            va_trace.add_trace(i.trace_repr)
