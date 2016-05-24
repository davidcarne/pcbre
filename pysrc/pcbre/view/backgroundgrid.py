from OpenGL.arrays.vbo import VBO

from pcbre.accel.vert_array import VA_xy
from pcbre.ui.gl import VAO

__author__ = 'davidc'


import OpenGL.GL as GL
import numpy
import ctypes

MIN_PIXEL_SPACE = 4

class BackgroundGridRender:
    def __init__(self):
        self.__width = 0
        self.__height = 0

        self.__vbo_dtype = numpy.dtype([("vertex". numpy.float32, 2)])

    def initializeGL(self, gls, width, height):
        # Get shader

        self.__shader = gls.shader_cache.get("basic_fill_vert", "basic_fill_frag")
        
        
        self.__vbo = VBO(numpy.ndarray(0, dtype=self.__vbo_dtype), GL.GL_STATIC_DRAW)
        self.__vao = VAO()



        # Create array of lines sufficient to fill screen
        self.resize(width, height)

    def __get_vbo_data(self):
        va = VA_xy(1024)


        # Unit steps from -n/2..n/2 along X axis. Y lines from -1 to +1
        for i in range(0, self.n_steps * 2, 2):
            i_ = i - int(self.n_steps / 2)
            va.add_line(i_, -1, i_, 1)

        return va




    def resize(self, width, height):
        self.n_steps = max(self.__width, self.__height) // MIN_PIXEL_SPACE
        self.__vbo.set_array(self.__get_vbo_data())




    def set_grid(self, step):
        pass

    def draw(self, transform_matrix):
        pass