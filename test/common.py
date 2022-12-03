from pcbre.model.artwork_geom import Via
from pcbre.model.project import Project
from pcbre.model.stackup import Layer, ViaPair

__author__ = 'davidc'



def setup2Layer(obj):
    obj.p = Project()

    obj.top_layer = obj.p.stackup.add_layer("top", (1, 0, 0))
    obj.bottom_layer = obj.p.stackup.add_layer("bottom", (0,0,1))
    
    obj.via_pair = obj.p.stackup.add_via_pair(obj.top_layer, obj.bottom_layer)
