__author__ = 'davidc'

from OpenGL.GL.shaders import ShaderProgram, compileShader
import OpenGL.GL as GL
from collections import namedtuple

_index_size_type = namedtuple("index_size_type", ["index", "size", "type"])

class UnboundUniformException(Exception):
    pass

class UnboundAttributeException(Exception):
    pass

class EnhShaderProgram(ShaderProgram):
    def _get_uniforms(self):
        _active_uniform = GL.glGetProgramiv(self, GL.GL_ACTIVE_UNIFORMS)

        _uniforms = {}

        for unif_index in range(_active_uniform):
            name, size, type =  GL.glGetActiveUniform(self, +unif_index)

            # in python3 shader names are bytestrings. Upconvert to UTF8 to play nice
            name = name.decode("ascii")
            _uniforms[name] = _index_size_type(unif_index, size, type)

        return _uniforms

    def _get_attribs(self):
        _active_attrib = GL.glGetProgramiv(self, GL.GL_ACTIVE_ATTRIBUTES)

        bufSize = 50
        ct_nameSize = GL.GLsizei()
        ct_size = GL.GLint()
        ct_type = GL.GLenum()
        ct_name = (GL.GLchar * bufSize)()

        _attribs = {}

        for attrib_index in range(_active_attrib):
            GL.glGetActiveAttrib(self, attrib_index, bufSize,
                ct_nameSize, ct_size, ct_type, ct_name
                )

            #in python3 attribute names are bytestrings. Convert to UTF8
            name = ct_name.value.decode("ascii")

            _attribs[name] = _index_size_type(attrib_index, ct_size.value, ct_type.value)

        return _attribs

    def _update_bindings(self):
        self._attribs = self._get_attribs()
        self._uniforms = self._get_uniforms()

        self._uniforms_to_be = set(self._uniforms.keys())


    def __getattr__(self, fname):
        if fname.startswith("glUniform"):
            func_attr = getattr(GL, fname)
            def binder(uniform_name, *args, **kwargs):
                # TODO: Check signature of func against argtype
                loc = self._uniforms[uniform_name].index
                GL.glUseProgram(self)
                func_attr(loc, *args, **kwargs)
                GL.glUseProgram(0)
                self._uniforms_to_be.remove(uniform_name)
            return binder

        raise AttributeError

    def __enter__(self):
        super(EnhShaderProgram, self).__enter__()
        if len(self._uniforms_to_be):
            raise UnboundUniformException(", ".join(self._uniforms_to_be))

def compileProgram(*shaders):
    program = GL.glCreateProgram()

    for shader in shaders:
        GL.glAttachShader(program, shader)

    program = EnhShaderProgram( program )

    GL.glLinkProgram(program)

    program.check_validate()
    program.check_linked()
    for shader in shaders:
        GL.glDeleteShader(shader)
    return program

