from pcbre.model.artwork_geom import Via
from pcbre.model.project import Project
from pcbre.model.stackup import Layer, ViaPair

__author__ = 'davidc'



def setup2Layer(obj):
    obj.p = Project()
    obj.top_layer = Layer(obj.p, "top", (1,0,0))
    obj.bottom_layer = Layer(obj.p, "bottom", (0, 0, 1))
    
    obj.p.stackup.add_layer(obj.top_layer)
    obj.p.stackup.add_layer(obj.bottom_layer)
    
    obj.via_pair = ViaPair(obj.p, obj.top_layer, obj.bottom_layer)
    obj.p.stackup.add_via_pair(obj.via_pair)
