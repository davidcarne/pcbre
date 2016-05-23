import pkg_resources
import sysconfig

def find_so(name):
    # This terrible hack seems to be able to find the compiled acceleration library
    extension = sysconfig.get_config_var('SO')
    dllname = pkg_resources.resource_filename('pcbre.accel', name + extension)
    return dllname
