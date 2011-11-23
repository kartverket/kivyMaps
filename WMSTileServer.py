from TileServer import *
from projections import *

try:
  from pyproj import Proj
  from xml.etree import ElementTree as ET
except:
  pass

class WMSTileServer(TileServer):
    '''Generic WMS tile server (see below for extending it to a specific provider)'''
    def geturl(self, nx, ny, lx, ly, tilew, tileh, zoom, format, maptype):
      tz = pow(2, zoom)
      
      if self.customBounds:
        ulx, uly, orx, ory = self.bounds
        dx, dy = orx-ulx, ory-uly
        x1 = ulx + dx * nx / tz
        x2 = ulx + dx * (nx+1.0) / tz
        y1 = uly + dy * (1.0 - (ny + 1.0) / tz)
        y2 = uly + dy * (1.0 - (ny + 0.0) / tz)
        return self.url + "&BBOX=%f,%f,%f,%f&WIDTH=256&HEIGHT=256&LAYERS=%s" % (x1, y1, x2, y2, maptype)

      if self.isPLatLon:
        y1, x1 = unit_to_p4326(1 - 2.0 * (ny) / tz, 2.0 * (nx) / tz - 1)
        y2, x2 = unit_to_p4326(1 - 2.0 * (ny + 1.0) / tz, 2.0 * (nx + 1.0) / tz - 1)
      else:
        x1, y1 = unit_to_project(self.projection, 2.0 * (nx) / tz - 1, 1 - 2.0 * (ny) / tz)
        x2, y2 = unit_to_project(self.projection, 2.0 * (nx + 1.0) / tz - 1, 1 - 2.0 * (ny + 1.0) / tz)
      return self.url + "&BBOX=%f,%f,%f,%f&WIDTH=256&HEIGHT=256&LAYERS=%s" % (x1, y2, x2, y1, maptype)
      
    def initFromGetCapabilities(self, host, baseurl, index = 0, srs = None, layer = None):
      # GetCapabilities (Layers + SRS)
      self.customBounds = False
      capabilities = urlopen(host + baseurl + "?SERVICE=WMS&VERSION=1.1.1&Request=GetCapabilities").read().strip()
      if layer == None or srs == None:
        try:
          tree = ET.fromstring(capabilities)
          layers = tree.findall("Capability/Layer/Layer")
          data = {}
          for layer in layers:
            name = layer.find("Name").text
            srss = layer.findall("SRS")
            data[name] = map(lambda x:x.text, srss)
            #print name,data[name]
          
          # Choose Layer and SRS by (alphabetical) index
          layer = sorted(data.keys())[index]
          if srs is None:
            srs = sorted(data[layer])[0]
        except:
          pass
      
      # generate tile URL and init projection by EPSG code
      self.url = baseurl + "?SRS=%s&FORMAT=image/png&SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap" % (srs)
      self.isPLatLon = False
      try:
        if srs == "EPSG:4326":  # android patches for common projections
          self.isPLatLon = True
        else:
          self.projection = Proj(init=srs)
      except:
        pass

class OSMWMSTileServer(WMSTileServer):
    '''Connect to OSM-WMS worldwide tile service
       (i.e., we actually talk to a WMS-T server, but the syntax is WMS)
    '''    
    provider_name = 'osmwms'
    provider_host = '129.206.229.158'
    available_maptype = dict(roadmap = 'Roadmap') 

    def __init__(self, **kwargs):
      self.initFromGetCapabilities('http://129.206.229.158', '/cached/osm', index=1)
      super(WMSTileServer, self).__init__(**kwargs) 

TileServer.register(OSMWMSTileServer)    
