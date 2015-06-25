# PCBRE

PCB is an open source package for semiautomated and manual PCB reverse engineering

## Documentation and Support

PCBRE currently doesn't have any documentation. This will likely change fairly soon.

For support, please join #pcbre on freenode. 

## Install

PCBRE requires the following dependencies. Some will probably need to come from your systems package manager. Some might come from pip. Some need to be custom installed.

**System Packages**

- python3.4
- numpy
- scipy
- PySide
- geos (not a python package, needed for shapely)
- capnp
- libspatialindex
- opencv3

**Python Packages**

- pycapnp
- shapely
- signalslot
- mock
- rtree
- freetype\_py
- git+https://github.com/davidcarne/pypotrace.git
- git+https://github.com/davidcarne/poly2tri.python.git
- pyopengl


Personally, I use the following sequence to setup a test environment

    virtualenv --system-site-packages -p python3.4 .env
    . .env/bin/activate
    pip install shapely signalslot mock freetype_py git+https://github.com/davidcarne/pypotrace.git git+https://github.com/davidcarne/poly2tri.python.git
    python setup.py develop

Then you can just run pcbre by typing `pcbre` into your shell (its in the virtualenv path)

## Debian/Ubuntu Specific Installation notes

   apt-get install libcapnp-dev python3-numpy python3-scipy libgeos-dev python3-mock python3-pyside cython3 libpotrace-dev libagg-dev

## License and Contribution Information

All source with the excluding of the following is licensed under GPLv2-or-later. That said, if you need a different license, feel free to contact me. I'm likely to grant such requests, unless its to make a commercial, closed source fork of the entire codebase.

csrc/edtaa3func.\*  is licensed under the license in its file headers (BSD)
pysrc/pcbre/resources/Vera.ttf is under the Bistream Vera Fonts copyright (BSD-like)
