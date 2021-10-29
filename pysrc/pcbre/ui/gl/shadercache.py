__author__ = 'davidc'

from typing import Dict, Tuple, FrozenSet, Optional

import OpenGL.GL as GL  # type: ignore
import pkg_resources

from pcbre.ui.gl.shader import compileProgram, compileShader, EnhShaderProgram


class UniformProxy:
    def __init__(self, parent: EnhShaderProgram):
        self._prog = parent

        self._dict: Dict[str, int] = {}

    def __getattr__(self, key: str) -> int:
        try:
            return self._dict[key]
        except KeyError:
            pass

        v: int = GL.glGetUniformLocation(self._prog.program, key)
        if v == -1:
            raise KeyError(key)
        self._dict[key] = v
        return v


class ShaderCache:
    def __init__(self) -> None:
        self.cache: Dict[
            Tuple[str, str, Tuple[FrozenSet[Tuple[str, str]], FrozenSet[Tuple[str, str]]]],
            EnhShaderProgram] = {}

    def __build_s(self, d: Dict[str, str]) -> str:
        return "".join("#define %s %s\n" % (k, v) for k, v in d.items())

    def extract_version(self, s: str) -> Tuple[str, str]:
        lines = s.split("\n")

        if lines[0].startswith("#version"):
            return "%s\n" % lines[0], "\n".join(lines[1:])
        else:
            return "", "\n".join(lines)

    @staticmethod
    def __get_shader_text(name: str) -> str:
        byte_str = pkg_resources.resource_string('pcbre.resources', "shaders/%s.glsl" % name)
        return byte_str.decode('ascii')

    def get(self, vert_name: str, frag_name: str,
            defines: Optional[Dict[str, str]] = None,
            vertex_defines: Optional[Dict[str, str]] = None,
            fragment_defines: Optional[Dict[str, str]] = None,
            fragment_bindings: Optional[Dict[str, int]] = None) -> EnhShaderProgram:

        _fragment_defines = {}
        if fragment_defines is not None:
            _fragment_defines.update(fragment_defines)

        if defines is not None:
            _fragment_defines.update(defines)

        _vertex_defines = {}
        if vertex_defines is not None:
            _vertex_defines.update(vertex_defines)

        if defines is not None:
            _vertex_defines.update(defines)

        if fragment_bindings is None:
            fragment_bindings = {}

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
                obj = compileProgram([vert, frag], fragment_bindings)
            except RuntimeError as e:
                msg, shader, _ = e.args
                print("During Shader Compilation: ", msg)
                shader_body = b"".join(shader).decode('ascii')
                lines = shader_body.split("\n")
                for i in lines:
                    print("\t%s" % i.strip())
                raise

            # TODO - determine if this is needed
            obj.uniforms = UniformProxy(obj)  # type: ignore

            self.cache[key] = obj
        return self.cache[key]
