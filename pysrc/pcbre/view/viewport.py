import numpy
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
        self.__update()

    @property
    def scale_factor(self):
        return self.__scale_factor

    # Forward Matrix (world to viewport)
    @property
    def fwdMatrix(self):
        return self.__fwdMatrix

    # GL Matrix - world to natural device coordinates
    @property
    def glMatrix(self):
        return self.__glMatrix

    # GLWMatrix - transform from viewport space to normalized device space
    @property
    def glWMatrix(self):
        return self.__glWMatrix

    @property
    def viewPortMatrix(self):
        return self.__ndc2v

    @property
    def revMatrix(self):
        return self.__revMatrix

    @property
    def width(self):
        return self.__width

    @property
    def height(self):
        return self.__height

    def tfW2V(self, pt):
        return projectPoint(self.fwdMatrix, pt)

    def tfV2W(self, pt):
        return projectPoint(self.revMatrix, pt)

    def tfV2P(self, pt):
        return projectPoint(self.__v2w, pt)

    def tfP2V(self, pt):
        return projectPoint(self.__w2ndc, pt)

    def tfW2V_s(self, s):
        return abs(self.fwdMatrix[0][0]) * s

    def __update(self):
        self.__fwdMatrix = self.__ndc2v.dot(self.__w2ndc.dot(self._transform))
        self.__scale_factor = max(map(abs, [self.fwdMatrix[0][0], self.fwdMatrix[0][1], self.fwdMatrix[1][0], self.fwdMatrix[1][1]]))
        self.__revMatrix = numpy.linalg.inv(self.fwdMatrix)

        self.__glMatrix = self.__w2ndc.dot(self._transform)
        self.__glWMatrix = numpy.linalg.inv(self.__ndc2v)
        self.__v2w = numpy.linalg.inv(self.__ndc2v.dot(self.__w2ndc))

    def resize(self, newwidth, newheight):
        self.__width = newwidth
        self.__height = newheight

        # World to natural device coordinates matrix
        self.__w2ndc = numpy.array([
                                       [1, 0, 0],
                                       [0, 1, 0],
                                       [0, 0, 1]
                                   ], dtype=numpy.float32)

        # Natural device coordinates to viewport matrix
        xh = self.__width/2
        yh = self.__height/2

        rs = max(self.__width, self.__height)/2
        self.__ndc2v = numpy.array([
            [rs, 0, xh],
            [0, -rs, yh],
            [0, 0, 1],
            ])

        self.__update()
