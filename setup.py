from setuptools import setup, find_packages, Extension

extmods = [
        
        Extension('pcbre.accel._edtaa3', sources=['csrc/edtaa3func.c'])
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
            '': ['*.svg', '*.glsl', '*.capnp']
        },

        entry_points = { 'console_scripts': [
                "pcbre = pcbre.ui.main_gui:main"
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


