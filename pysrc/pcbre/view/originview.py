from OpenGL import GL  # type: ignore

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from  pcbre.ui.gl.glshared import GLShared

class OriginView(object):
    def initializeGL(self, gls: 'GLShared') -> None:
        self.gls = gls

        self.prog = self.gls.shader_cache.get("vert2", "frag1")
        self.mat_loc = GL.glGetUniformLocation(self.prog.program, "mat")

    def render(self, viewState: Any) -> None:
        pass
