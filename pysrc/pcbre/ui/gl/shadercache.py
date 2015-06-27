__author__ = 'davidc'

import pkg_resources
import OpenGL.GL as GL
from pcbre.ui.gl.shader import compileProgram, compileShader

class UniformProxy(object):
    def __init__(self, parent):
        self._prog = parent

        self._dict = {}

    def __getattr__(self, key):
        v = GL.glGetUniformLocation(self._prog, key)
        if v == -1:
            raise KeyError(key)
        self.__dict__[key] = v
        return v

class ShaderCache(object):
    def __init__(self):
        self.cache = {}

    def __build_s(self, d):
        return "".join("#define %s %s\n" % (k,v) for k, v in d.items())

    def extract_version(self, s):
        lines = s.split("\n")

        if lines[0].startswith("#version"):
            return "%s\n" % lines[0], "\n".join(lines[1:])
        else:
            return "", "\n".join(lines)

    @staticmethod
    def __get_shader_text(name):
            byte_str = pkg_resources.resource_string('pcbre.resources', "shaders/%s.glsl" % name)
            return byte_str.decode('ascii')

    def get(self, vert_name, frag_name, defines={}, vertex_defines={}, fragment_defines={}):

        _fragment_defines={}
        _fragment_defines.update(fragment_defines)
        _fragment_defines.update(defines)

        _vertex_defines={}
        _vertex_defines.update(vertex_defines)
        _vertex_defines.update(defines)

        frag_prepend = self.__build_s(_fragment_defines)
        vert_prepend = self.__build_s(_vertex_defines)

        # The defines to a shader affect compilation, create an unordered key
        _defines_key = (frozenset(_fragment_defines.items()), frozenset(_vertex_defines.items()))

        key = vert_name, frag_name, _defines_key

        if key not in self.cache:
            frag1s = self.__get_shader_text(frag_name)
            vert1s = self.__get_shader_text(vert_name)

            frag_version, frag1s = self.extract_version(frag1s)
            vert_version, vert1s = self.extract_version(vert1s)
            try:
                frag = compileShader([frag_version, frag_prepend, frag1s], GL.GL_FRAGMENT_SHADER)
                vert = compileShader([vert_version, vert_prepend, vert1s], GL.GL_VERTEX_SHADER)
                obj = compileProgram(vert, frag)
            except RuntimeError as e:
                print("During Shader Compilation: ", e)
                raise e

            obj.uniforms = UniformProxy(obj)

            self.cache[key] = obj
        return self.cache[key]

