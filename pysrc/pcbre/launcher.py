from typing import List, Dict, Tuple, Optional

# Launcher to look for required packages and
# fail with a nice error and suggestions on how to proceed

required_packages = [
    "qtpy",
    "qtpy.QtCore",
    "qtpy.QtGui",
    "qtpy.QtWidgets",
    "qtpy.QtOpenGL",
    "capnp",
    "numpy",
    "shapely",
    "p2t",
    "rtree",
    "cv2",
    "OpenGL",
    "scipy",
    "freetype"
]

required_objects: List[str] = []


def error(msg: str) -> None:
    try:
        import subprocess
        subprocess.call([
            "zenity", "--error", "--width", "640", "--text", msg])
    except FileNotFoundError:
        pass

    print(msg)


def missing_package_error(missing_py_packages: List[str], other: Optional[str]) -> None:
    error_message = ((
                             "PCBRE cannot start because the following " +
                             "python packages are missing: {}\n\n"
                     ).format(", ".join(sorted(missing_py_packages)))
                     )

    if other:
        error_message += other

    error(error_message)


def missing_package_error_install(
        missing_py_packages: List[str], distro_command: str) -> None:
    install_cmd = (
        "You may be able to install some or all of these packages by running the following command:\n\n{}"
    ).format(distro_command)

    missing_package_error(missing_py_packages, install_cmd)


class DependencyInstaller:
    def show(self, missing_py_packages: List[str], missing_objects: List[str]) -> None:
        missing_package_error(missing_py_packages, None)
        # TODO - objects


class OutdatedDistroInstaller(DependencyInstaller):
    def __init__(self, distro: str, version: float, min_supported: float):
        self.distro = distro
        self.version = version
        self.min_supported = min_supported

    def show(self, missing_py_packages: List[str], missing_objects: List[str]) -> None:
        missing_package_error(
            missing_py_packages,
            "Your distribution (%s %s) is not officially supported by PCBRE. The minimum supported version of %s is %s"
            % (self.distro, self.version, self.distro, self.min_supported))


class AptDistroInstaller(DependencyInstaller):
    PY_PKG_STEPS: Dict[str, Tuple[str, str]] = {}

    def show(self, missing_py_packages: List[str], missing_objects: List[str]) -> None:
        from collections import defaultdict
        targets = defaultdict(list)

        for pkg in missing_py_packages:
            target, name = self.PY_PKG_STEPS[pkg]
            targets[target].append((pkg, name))

        # TODO - objects

        commands = []
        if len(targets["apt"]):
            commands.append("\tsudo apt install %s" % " ".join(sorted([i[1] for i in targets["apt"]])))

        if len(targets["pip"]):
            commands.append("\t# You may wish to use a virtualenv or install with --user")
            commands.append("\tpip install %s" % " ".join(sorted([i[1] for i in targets["pip"]])))

        missing_package_error_install(missing_py_packages, "\n".join(commands))


class DebianBusterInstaller(AptDistroInstaller):
    PY_PKG_STEPS = {
        "qtpy.QtCore": ("apt", "python3-pyside2.qtcore"),
        "qtpy.QtGui": ("apt", "python3-pyside2.qtgui"),
        "qtpy.QtWidgets": ("apt", "python3-pyside2.qtwidgets"),
        "qtpy.QtOpenGL": ("apt", "python3-pyside2.qtopengl"),
        "capnp": ("pip", "pycapnp"),
        "numpy": ("apt", "python3-numpy"),
        "shapely": ("apt", "python3-shapely"),
        "p2t": ("pip", "git+https://github.com/davidcarne/poly2tri.python.git"),
        "rtree": ("apt", "python3-rtree"),
        "cv2": ("apt", "python3-opencv"),
        "OpenGL": ("apt", "python3-opengl"),
        "scipy": ("apt", "python3-scipy"),
        "freetype": ("pip", "freetype-py"),
    }


def detect_distro_debian(kv: Dict[str, str]) -> Optional[DependencyInstaller]:
    vers_id = kv.get("VERSION_ID", None)

    if vers_id is None:
        return None
    try:
        vers_no = float(vers_id)
    except ValueError:
        return None

    if vers_no < 10:
        return OutdatedDistroInstaller('Debian', vers_no, 10)

    else:
        return DebianBusterInstaller()


def detect_distro_linux() -> Optional[DependencyInstaller]:
    try:
        lines = open("/etc/os-release").readlines()

        kv = {}
        for line in lines:
            hash_pos = line.find('#')
            if hash_pos != -1:
                line = line[:hash_pos]

            line = line.strip()
            if line:
                first, second = line.split('=', maxsplit=1)

                if second.startswith('"'):
                    second = second[1:-1]
                kv[first] = second

        if kv["ID"] == "debian":
            return detect_distro_debian(kv)

        # elif kv["ID"] == "ubuntu":
        #    return detect_distro_ubuntu(kv)

        # elif kv["ID"] == "gentoo":
        #    return detect_distro_gentoo(kv)

    except IOError:
        pass

    return None


def detect_distro() -> DependencyInstaller:
    try:
        import platform
        found = None

        if platform.system() == "Linux":
            found = detect_distro_linux()

        if found:
            return found

        return DependencyInstaller()
    except Exception as e:
        print("Error during distro detection:", e)
        return DependencyInstaller()


def launcher_main() -> None:
    import pkgutil

    missing_pkgs = []
    for pkg_name in required_packages:
        mods = pkg_name.split('.')
        for n in range(len(mods)):
            gen_pkg_name = ".".join(mods[:n + 1])
            if not pkgutil.get_loader(gen_pkg_name):
                missing_pkgs.append(pkg_name)
                break

    if missing_pkgs:
        distro_helper = detect_distro()
        distro_helper.show(missing_pkgs, [])
        return

    import pcbre.ui.main_gui

    pcbre.ui.main_gui.main()


if __name__ == "__main__":
    launcher_main()
