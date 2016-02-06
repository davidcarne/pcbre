import math

import weakref

from pcbre import units
from pcbre.matrix import Rect, Point2, projectPoint, projectPoints
from pcbre.model.passivecomponent import PassiveBodyType
from pcbre.view.rendersettings import RENDER_STANDARD, RENDER_SELECTED, RENDER_HINT_NORMAL, \
    RENDER_HINT_ONCE


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







class PadRender:
    def __init__(self, parent_view):
        self.parent = parent_view
        pass

    def initializeGL(self, view, gls):
        """
        :type gls: GLShared
        :param gls:
        :return:
        """
        self.gls = gls
        self.view = view
        self.text_cache = {}


    def render(self, mat, pad, render_mode=RENDER_STANDARD, render_hint=RENDER_HINT_NORMAL):
        """
        :type pad: Pad
        :param mat:
        :param pad:
        :return:
        """


        textcol = self.parent.text_color()
        textcol_a = textcol + [1]

        color = self.parent.color_for_pad(pad)
        color_a = color + [1]
        if render_mode & RENDER_SELECTED:
            color_a = [1,1,1,1]


        if pad.is_through():
            self.parent.via_renderer.deferred(pad.center, pad.l/2, pad.th_diam/2, render_mode, render_hint)

            #r = Rect.fromCenterSize(Point2(0,0), pad.l * 0.6, pad.w * 0.6)

            #_text_to(self.view, pad,r, mat, textcol_a)
        else:
            t = pad.trace_repr
            self.parent.trace_renderer.deferred(t, render_mode, render_hint)
            #r = Rect.fromCenterSize(Point2(0,0), pad.l*0.8, pad.w*0.8)
            #_text_to(self.view, pad, r, mat, textcol_a)


class ComponentRender:
    def __init__(self, view):
        self.__cache = weakref.WeakKeyDictionary()
        self.view = view
        self.pr = view.pad_renderer

    def initializeGL(self, gls):
        pass

    def __get_cached_reservation(self, cmp, group):
        try:
            gd = self.__cache[cmp]
            return gd[group]
        except KeyError:
            pass

        geom = self._build_points(cmp)
        rb = self.view.hairline_renderer.new_reservation(group)
        for p1, p2 in geom:
            rb.add(p1, p2)

        r = rb.finalize()
        if cmp in self.__cache:
            self.__cache[cmp][group] = r
        else:
            self.__cache[cmp] = {group: r}

        return r

        self.__text_cache = weakref.WeakKeyDictionary()
    def render(self, mat, cmp, render_mode=RENDER_STANDARD, render_hint=RENDER_HINT_NORMAL):
        group = None

        color = (1, 0, 1)
        if render_hint & RENDER_HINT_ONCE:
            geom = self._build_points(cmp)
            for p1, p2 in geom:
                self.view.hairline_renderer.deferred(p1, p2, color, group, RENDER_HINT_ONCE)
        else:
            res = self.__get_cached_reservation(cmp, group)
            self.view.hairline_renderer.deferred_reservation(res, color, group)

    def _build_points(self, cmp):
        return []

class PassiveRender(ComponentRender):
    def _build_points(self, cmp):
        """
        :type cmp: pcbre.model.passivecomponent.PassiveComponent
        :param cmp: 
        :return:
        """
        circ_groups = []

        if cmp.body_type == PassiveBodyType.CHIP:
            bx = cmp.body_corner_vec.x
            by = cmp.body_corner_vec.y
            circ_groups.append(map(Point2, [(-bx, by), (-bx,-by),(bx,-by),(bx,by) ]))

        elif cmp.body_type == PassiveBodyType.TH_AXIAL:
            bx = cmp.body_corner_vec.x
            by = cmp.body_corner_vec.y
            circ_groups.append(map(Point2, [(-bx, by), (-bx,-by),(bx,-by),(bx,by)]))

            d = cmp.pin_d - cmp.pin_corner_vec.x
            print(bx, d)
            circ_groups.append([Point2(bx, 0), Point2(d, 0)])
            circ_groups.append([Point2(-bx, 0), Point2(-d, 0)])

        elif cmp.body_type == PassiveBodyType.TH_RADIAL:
            g = []
            m = cmp.body_corner_vec.mag()
            for i in range(32):
                p = Point2.fromPolar(i/16*math.pi, m)
                g.append(p)
            circ_groups.append(g)


        ll = []
        for group in circ_groups:
            newpoints = projectPoints(cmp.matrix, group)
            ll += list(zip(newpoints, newpoints[1:] + newpoints[0:1]))
        return ll


class DIPRender(ComponentRender):
    def _build_points(self, dip):
        bx = dip.body_width() / 2
        by = dip.body_length() / 2

        points = []
        points.extend(projectPoints(dip.matrix, map(Point2, [(-bx, by), (-bx,-by),(bx,-by),(bx,by) ])))

        for i in range(28):
            theta = -math.pi * i / 27

            points.append(projectPoint(dip.matrix, Point2(math.cos(theta) * units.MM, math.sin(theta) * units.MM + by)))

        return list(zip(points, points[1:] + points[0:1]))

class SMDRender(ComponentRender):

    def _build_points(self, smd):
        lines =  []

        by = smd.dim_1_body/2
        bx = smd.dim_2_body/2

        corners = [projectPoint(smd.matrix, Point2(t)) for t in [(-bx, by), (-bx,-by),(bx,-by),(bx,by) ]]

        for p1, p2 in  zip(corners, corners[1:] + corners[0:1]):
            lines.append((p1, p2))

        scale = min(smd.dim_1_body, smd.dim_2_body) / 5
        if scale > units.MM:
            scale = units.MM
        if scale < units.MM/5:
            scale = units.MM/5

        size = scale/2
        offs = scale
        posx = -bx + offs
        posy = by - offs

        circle_points = []

        circ_center = projectPoint(smd.matrix, Point2(posx, posy))

        for i in range(28):
            theta = math.pi * 2 * i / 27
            d = Point2(math.cos(theta) * size, math.sin(theta) * size)
            circle_points.append(d + circ_center)



        for p1, p2 in zip(circle_points, circle_points[1:] + circle_points[0:1]):
            lines.append((p1, p2))

        return lines








