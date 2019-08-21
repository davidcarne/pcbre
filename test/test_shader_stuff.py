
__author__ = 'davidc'

import pcbre.ui.gl.shader as S
import unittest
from PySide2 import QtOpenGL, QtGui, QtCore
import OpenGL.GL as GL
import numpy


VERT_1 = """
uniform mat3 mat;
attribute vec2 vertex;
attribute vec2 texpos;

varying vec2 pos;

void main(void)
{
    vec3 calc = mat * vec3(vertex, 1);
    gl_Position = vec4(calc.x, calc.y, 0, calc.z);
    pos = texpos;
}
"""

FRAG_1 = """
varying vec2 pos;

uniform vec4 col;
uniform sampler2D tex1;

void main(void)
{
    vec4 tex = texture2D(tex1, pos);
    gl_FragColor = vec4(tex.r, tex.g, tex.b, 1) + col;
}
"""


# Ensure we have a qapplication - another testcase might have created it though
if QtGui.qApp == None: QtGui.QApplication([])

class test_shader_stuff(unittest.TestCase):
    ctx = None

    def setUp(self):

        if self.ctx is None:
            f = QtOpenGL.QGLFormat()
            f.setVersion(3, 2)
            f.setProfile(QtOpenGL.QGLFormat.CoreProfile)

            self.ctx = QtOpenGL.QGLContext(f)
            self.mockWidget = QtOpenGL.QGLWidget(self.ctx)

        self.assertTrue(self.ctx.isValid())
        self.ctx.makeCurrent()


        # Compile the two shaders individually
        s1 = S.compileShader(VERT_1, GL.GL_VERTEX_SHADER)
        s2 = S.compileShader(FRAG_1, GL.GL_FRAGMENT_SHADER)

        # now build the whole program
        self.prog = S.compileProgram(s1, s2)

    # Basic tests
    def test_fetches_names(self):
        attrs = self.prog._get_attribs()
        unifs = self.prog._get_uniforms()

        self.assertSetEqual(set(attrs.keys()), {"vertex", "texpos"})
        self.assertSetEqual(set(unifs.keys()), {"mat", "col", "tex1"})

    def test_check_size_type(self):
        self.prog._update_bindings()
        self.assertEqual(self.prog._attribs["vertex"].size, 1)
        self.assertEqual(self.prog._attribs["vertex"].type, GL.GL_FLOAT_VEC2)

        self.assertEqual(self.prog._attribs["texpos"].size, 1)
        self.assertEqual(self.prog._attribs["texpos"].type, GL.GL_FLOAT_VEC2)

        self.assertEqual(self.prog._uniforms["mat"].type, GL.GL_FLOAT_MAT3)
        self.assertEqual(self.prog._uniforms["mat"].size, 1)
        self.assertEqual(self.prog._uniforms["col"].type, GL.GL_FLOAT_VEC4)
        self.assertEqual(self.prog._uniforms["col"].size, 1)
        self.assertEqual(self.prog._uniforms["tex1"].type, GL.GL_SAMPLER_2D)
        self.assertEqual(self.prog._uniforms["tex1"].size, 1)

    def test_binding_unbound(self):
        """
        Verify that we actually throw an exception if we're missing a uniform
        :return:
        """
        self.prog._update_bindings()

        def _():
            self.prog.check_bindings()

        self.assertRaises(S.UnboundUniformException, _)

        ar = numpy.identity(3, dtype=numpy.float32)
        self.prog.glUniformMatrix3fv("mat", 1, False, ar)
        self.prog.glUniform4f("col", 1,1,1,1)
        self.prog.glUniform1i("tex1", 0)

        self.assertRaises(S.UnboundAttributeException, _)

    def test_binding_bound(self):
        self.prog._update_bindings()

        # Now setup all the bindings, and validate
        self.prog.glUniform4f("col", 1,1,1,1)
        self.prog.glUniform1i("tex1", 0)

        ar = numpy.identity(3, dtype=numpy.float32)
        self.prog.glUniformMatrix3fv("mat", 1, False, ar)
        i = self.prog.attributes.vertex
        i = self.prog.attributes.texpos


        self.prog.check_bindings()


