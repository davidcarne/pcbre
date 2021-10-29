from distutils.version import StrictVersion


def __version_assert(imported: str, required: str, desc: str) -> None:
    if StrictVersion(imported) < StrictVersion(required):
        print("Error: PCBRE Requires %s" % desc)
        exit(1)


def check_pkg_versions() -> None:
    import OpenGL  # type: ignore
    __version_assert(OpenGL.__version__, '3.1.0', "PyOpenGL version greater than 3.1.0 due to a shader bug")
