from pcbre.ui.gl.shadercache import ShaderCache
from pcbre.ui.gl.textrender import SDFTextAtlas, TextRender
import OpenGL.GL as GL
__author__ = 'davidc'

import pkg_resources


sans_serif_atlas = SDFTextAtlas(pkg_resources.resource_filename('pcbre.resources', 'Vera.ttf'))


class GLShared(object):
    def __init__(self):
        self.shader_cache = ShaderCache()

        self.text = TextRender(self, sans_serif_atlas)

    def initializeGL(self):
        #self.shader_cache.initializeGL()

        self.text.initializeGL()
        self.text.updateTexture()
