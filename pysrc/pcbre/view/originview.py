from OpenGL import GL


class OriginView(object):
    def initializeGL(self, gls):
        self.gls = gls

        self.prog = self.gls.shader_cache.get("vert2", "frag1")
        self.mat_loc = GL.glGetUniformLocation(self.prog, "mat")

        # Build a VBO for rendering square "drag-handles"
        # Coords are pixel coords
        # self.vbo_triangles_ar = numpy.ndarray(4, dtype=[("vertex", numpy.float32, 2, "color", numpy.float32, j)])
        # self.vbo_triangles_ar["vertex"][]

    def render(self, viewState):
        pass
