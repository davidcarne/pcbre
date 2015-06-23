import numpy
import collections
from pcbre.matrix import projectPoint

# We use 4 types of coordinates:
# V - Viewport Coordinates - coords in the on-screen viewport. QT-style.
#    Used for mouse-picking, rendering handles/controls
#    0,0 = top-left
#    size.width(), size.height() = bottom-right
#
# NDC - Natural Device Coordinates - OpenGL style coordinates
#    Pretty useless, but we need to deal with them
#    0,0 = bottom-left
#    1,1 = top-right
#
# P - Projection Area coords
#    Based around -1 to +1 square, but normalized to rectangular viewports
#
# W - World coords. World coordinates are in mm
#

class ViewPort(object):
    def __init__(self, x, y):

        # _transform defines the mapping from physical (world) coordinates to the projection area
        self.__transform = numpy.identity(3, dtype=numpy.float32)
        self.__scale_factor = 1

        self.resize(x, y)

    @property
    def _transform(self):
        return self.__transform

    @_transform.setter
    def _transform(self, value):
        self.__transform = value
        self.__update_scale_factor()

    @property
    def scale_factor(self):
        return self.__scale_factor

    # Forward Matrix (world to viewport)
    @property
    def __fwdMatrix(self):
        return self.__ndc2v.dot(self.__w2ndc.dot(self._transform))

    # GL Matrix - world to natural device coordinates
    @property
    def glMatrix(self):
        return self.__w2ndc.dot(self._transform)

    # GLWMatrix - transform from viewport space to normalized device space
    @property
    def glWMatrix(self):
        return numpy.linalg.inv(self.__ndc2v)

    @property
    def viewPortMatrix(self):
        return self.__ndc2v

    @property
    def __revMatrix(self):
        return numpy.linalg.inv(self.__fwdMatrix)

    @property
    def width(self):
        return self.__width

    @property
    def height(self):
        return self.__height

    def tfW2V(self, pt):
        return projectPoint(self.__fwdMatrix, pt)

    def tfV2W(self, pt):
        return projectPoint(self.__revMatrix, pt)

    def tfV2P(self, pt):
        m = numpy.linalg.inv(self.__ndc2v.dot(self.__w2ndc))
        return projectPoint(m, pt)

    def tfP2V(self, pt):
        return projectPoint(self.__w2ndc, pt)

    def tfW2V_s(self, s):
        return abs(self.__fwdMatrix[0][0]) * s

    def __update_scale_factor(self):
        self.__scale_factor = self.__fwdMatrix[0][0]

    def resize(self, newwidth, newheight):
        self.__width = newwidth
        self.__height = newheight

        min_edge = min(self.__width, self.__height)

        xscale = min_edge/float(self.width)
        yscale = min_edge/float(self.height)

        # World to natural device coordinates matrix
        self.__w2ndc = numpy.array([
                                       [xscale,      0,     0],
                                       [     0, yscale,     0],
                                       [     0,      0,     1]
                                   ], dtype=numpy.float32)

        # Natural device coordinates to viewport matrix
        xh = self.width/2
        yh = self.height/2

        self.__ndc2v = numpy.array([
            [ xh,   0, xh],
            [  0, -yh, yh],
            [  0,   0,  1],
            ])

        self.__update_scale_factor()



