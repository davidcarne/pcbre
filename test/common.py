from tempfile import TemporaryFile, TemporaryDirectory

from pcbre.model.artwork_geom import Via
from pcbre.model.project import Project, StorageType
from pcbre.model.serialization_capnp import CapnpIO
from pcbre.model.serialization_dirtext import DirTextIO
from pcbre.model.stackup import Layer, ViaPair
from functools import wraps

__author__ = 'davidc'



def setup2Layer(obj):
    obj.p = Project()

    obj.top_layer = obj.p.stackup.add_layer("top", (1, 0, 0))
    obj.bottom_layer = obj.p.stackup.add_layer("bottom", (0,0,1))
    
    obj.via_pair = obj.p.stackup.add_via_pair(obj.top_layer, obj.bottom_layer)

def saverestore(p: Project, mode: StorageType) -> Project:
    if mode == StorageType.Packed:
        with TemporaryFile(buffering=0) as fd:

            CapnpIO.save_fd(p, fd)
            fd.seek(0)

            p_new = CapnpIO.open_fd(fd)
        return p_new
    elif mode == StorageType.Dir:
        with TemporaryDirectory() as temp_dir:
            DirTextIO.save_path(temp_dir, p)

            return DirTextIO.open_path(temp_dir)
    else:
        raise ValueError("Unknown mode %s" % mode)


class StorageTestMeta(type):
    def __new__(mcs, name, bases, dt):

        def gen_test(f, storage_type: StorageType):
            @wraps(f)
            def test(self):
                f(self, storage_type)
            return test

        for v in list(dt.keys()):
            if v.startswith("PARAM"):
                test_name = "test_%s_dir" % v[6:]
                dt[test_name] = gen_test(dt[v],StorageType.Dir)

                test_name = "test_%s_packed" % v[6:]
                dt[test_name] = gen_test(dt[v], StorageType.Packed)

                del dt[v]

        return type.__new__(mcs, name, bases, dt)
