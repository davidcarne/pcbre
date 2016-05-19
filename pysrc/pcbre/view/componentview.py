import math

import weakref

from pcbre import units
from pcbre.matrix import Rect, Point2, projectPoint, projectPoints, Vec2
from pcbre.model.const import SIDE
from pcbre.model.dipcomponent import DIPComponent
from pcbre.model.passivecomponent import PassiveBodyType, PassiveComponent
from pcbre.model.smd4component import SMD4Component
from pcbre.view.rendersettings import RENDER_STANDARD, RENDER_SELECTED, RENDER_HINT_NORMAL, \
    RENDER_HINT_ONCE
from pcbre.view.target_const import COL_CMP_LINE

__author__ = 'davidc'


TRANSITION_POINT_1 = 20
TRANSITION_POINT_2 = 50
RATIO = 0.6
RGAP = 0.1

def _text_to(view, pad, r, mat, textcol_a):
    mat = mat.dot(pad.translate_mat)

    # zero-out rotation
    mat[0:2,0:2] = view.viewState.glMatrix[0:2,0:2]

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







#class PadRender:
    #def __init__(self, parent_view):
    #    self.parent = parent_view
    #    pass

    #def initializeGL(self, view, gls):
    #    """
    #    :type gls: GLShared
    #    :param gls:
    #    :return:
    #    """
    #    self.gls = gls
    #    self.view = view
    #    self.text_cache = {}


    #def render(self, mat, pad, render_mode=RENDER_STANDARD, render_hint=RENDER_HINT_NORMAL):
    #    """
    #    :type pad: Pad
    #    :param mat:
    #    :param pad:
    #    :return:
    #    """


        #textcol = self.parent.text_color()
        #textcol_a = textcol + [1]

        #color = self.parent.color_for_pad(pad)
        #color_a = color + [1]
        #if render_mode & RENDER_SELECTED:
        #    color_a = [1,1,1,1]


        #if pad.is_through():
        #    self.parent.via_renderer.deferred(pad.center, pad.l/2, pad.th_diam/2, render_mode, render_hint)

            #r = Rect.fromCenterSize(Point2(0,0), pad.l * 0.6, pad.w * 0.6)

            #_text_to(self.view, pad,r, mat, textcol_a)
        #else:
        #    t = pad.trace_repr
        #    self.parent.trace_renderer.deferred(t, render_mode, render_hint)
            #r = Rect.fromCenterSize(Point2(0,0), pad.l*0.8, pad.w*0.8)
            #_text_to(self.view, pad, r, mat, textcol_a)


class ComponentRender:
    def __init__(self, view):
        self.__cache = weakref.WeakKeyDictionary()
        self.view = view

    def initializeGL(self, gls):
        pass


    def render(self, mat, cmp, render_mode=RENDER_STANDARD, render_hint=RENDER_HINT_NORMAL):
        group = None
        pass


    def _build_points(self, cmp):
        return []

def passive_border_va(va, cmp):
    """
    :type cmp: pcbre.model.passivecomponent.PassiveComponent
    :type va: pcbre.accel.vert_array.VA_xy
    :param cmp:
    :return:
    """

    if cmp.body_type == PassiveBodyType.CHIP:
        bx = cmp.body_corner_vec.x
        by = cmp.body_corner_vec.y
        va.add_box(cmp.center.x, cmp.center.y, bx * 2, by * 2, cmp.theta)

    elif cmp.body_type == PassiveBodyType.TH_AXIAL:
        bx = cmp.body_corner_vec.x
        by = cmp.body_corner_vec.y
        va.add_box(cmp.center.x, cmp.center.y, bx * 2, by * 2, cmp.theta)

        vec = Vec2(math.cos(cmp.theta), math.sin(cmp.theta))

        # Add legs
        pa = cmp.pin_d * vec
        pb = cmp.pin_corner_vec.x * vec
        va.add_line( pa.x,  pa.y,  pb.x,  pb.y)
        va.add_line(-pa.x, -pa.y, -pb.x, -pb.y)

    elif cmp.body_type == PassiveBodyType.TH_RADIAL:
        raise NotImplementedError()
    else:
        raise NotImplementedError()


def dip_border_va(va_xy, dip):
    by = dip.body_length() / 2

    r = units.MM

    va_xy.add_box(dip.center.x, dip.center.y, dip.body_width(), dip.body_length(), dip.theta)

    pt_center = projectPoint(dip.matrix, Point2(0, by))
    va_xy.add_arc(pt_center.x, pt_center.y, r, dip.theta + math.pi, dip.theta, 28)

def smd_border_va(va_xy, smd):
    #va_xy.add_box()
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


    pt = projectPoint(smd.matrix, Point2(posx, posy))
    va_xy.add_circle(pt.x, pt.y, size, 40)

def cmp_border_va(dest, component):
    if isinstance(component, DIPComponent):
        dip_border_va(dest, component)
    elif isinstance(component, SMD4Component):
        smd_border_va(dest, component)
    elif isinstance(component, PassiveComponent):
        passive_border_va(dest, component)

def cmp_pad_periph_va(va_xy, component):
    for i in component.get_pads():
        if i.is_through():
            va_xy.add_circle(i.center.x, i.center.y, i.w/2)
        else:
            va_xy.add_box(i.center.x, i.center.y, i.w, i.l, i.theta)
