from setuptools import setup, find_packages, Extension

extmods = [
        
        Extension('pcbre.accel._edtaa3', sources=['csrc/edtaa3func.c']),
        Extension('pcbre.accel._va', sources=[
            'csrc/va/va_template.c',
            'csrc/va/va_trace.c',
            'csrc/va/va_via.c',
            'csrc/va/va_xy.c',
            'csrc/va/va_char.c'

            ],
            include_dirs=['csrc/va'],
            extra_compile_args=['--std=c99','-Wall','-Wextra','-Werror']
        )
        ]
setup(  name="pcbre",
        version='0',
        description="PCB Reverse Engineering package",
        author="David Carne",
        author_email="davidcarne@gmail.com",
        url="https://github.com/davidcarne/pcbre",
        packages = find_packages("pysrc"),
        package_dir = {'': 'pysrc'},

        package_data = {
            '': ['*.svg', '*.glsl', '*.capnp', '*.ttf']
        },

        entry_points = { 'console_scripts': [
                "pcbre-launcher = pcbre.launcher:launcher_main",
                "pcbre-app = pcbre.ui.main_gui:main"
            ],
        },

# No deps, since this seems to autoinstall wrong things. see readme.md
#        install_requires = [
#            'PySide',
#            'pycapnp',
#            'pypotrace==0.1.2+dcpatch',
#            'poly2tri==0.3.3+dcpatch',
#            'shapely',
#            'signalslot',
#            'mock',
#            'freetype_py'
#            'numpy',
#            'scipy',
#            'cv2'
#            ],
#        dependency_links = [
#            'https://github.com/davidcarne/pypotrace/tarball/master#egg=pypotrace-0.1.2+dcpatch',
#            'https://github.com/davidcarne/poly2tri.python/tarball/master#egg=poly2tri-0.3.3+dcpatch'
#            
#            ],


        ext_modules = extmods
)


