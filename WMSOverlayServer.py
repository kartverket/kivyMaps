from projections import *
from urllib2 import urlopen
from httplib import HTTPConnection
from threading import Thread
from kivy.logger import Logger
from kivy.loader import Loader
from os.path import join, dirname
import time, os
import hashlib

try: 
  from pyproj import Proj
  from xml.etree import ElementTree as ET
except:
  pass

class WMSOverlayServer(object):
    cache = {} 
    available_maptype = dict(roadmap = 'Roadmap') # default
    type = "wms"
 
    '''Generic WMS server'''
    def __init__(self, progress_callback=None):    
      self.progress_callback = progress_callback
      
    def setProgressCallback(self, progress_callback):
      self.progress_callback = progress_callback
    
    def get(self, parent, width, height): 
    
      self.bl = parent.bottom_left
      self.tr = parent.top_right
      self.zoom = parent.zoom
      
      url = self.geturl(self.bl[0], self.bl[1], self.tr[0], self.tr[1], self.zoom, width, height)
      if not url:
        return None

      key = hashlib.md5(url).hexdigest()
        
      if key in self.cache:
        return self.cache[key]
        
      try:
        image = Loader.image('http://' + self.provider_host + url, progress_callback = self.progress_callback)
        self.cache[key] = image
      except Exception,e:
        Logger.error('OverlayServer could not find (or read) image %s [%s]' % (url, e))
        image = None

    def geturl(self, lat1, lon1, lat2, lon2, zoom, w, h):
      try:
        if self.customBounds: 
          x1, y1 = latlon_to_custom(lat1, lon1, self.bounds)
          x2, y2 = latlon_to_custom(lat2, lon2, self.bounds)
        elif self.isPLatLon:   # patch for android - does not require pyproj library
          x1, y1 = lon1, lat1
          x2, y2 = lon2, lat2
        elif self.isPGoogle: # patch for android - does not require pyproj library
          x1, y1 = latlon_to_google (lat1, lon1)
          x2, y2 = latlon_to_google (lat2, lon2)
        else:
          x1, y1 = transform(pLatlon, self.projection, lon1, lat1)
          x2, y2 = transform(pLatlon, self.projection, lon2, lat2)
        return self.url + "&BBOX=%f,%f,%f,%f&WIDTH=%i&HEIGHT=%i&ext=.png" % (x1, y1, x2, y2, w, h)
      except RuntimeError, e:
        return None
      
    def parseLayer(self, layer, data):
      try:
        name = layer.find("Name").text
      except:
        name = None
      srss = layer.findall("SRS")
      if name:# and srss:
        data[name] = map(lambda x:x.text, srss)
        if self.debug:
          print "Provider %s provides layer %s in projections %s" % (self.provider_host, name, data[name])
      subs = layer.findall("Layer")
      for sub in subs:
        self.parseLayer(sub, data)
      
    def initFromGetCapabilities(self, host, baseurl, layer = None, index = 0, srs = None):
      self.debug = (layer == None) and (index == 0)
      # GetCapabilities (Layers + SRS)
      capabilities = urlopen(host + baseurl + "?SERVICE=WMS&VERSION=1.1.1&Request=GetCapabilities").read().strip()
      try:
          tree = ET.fromstring(capabilities)
          if self.debug:
            ET.dump(tree)
          layers = tree.findall("Capability/Layer") #TODO: proper parsing of cascading layers and their SRS
          data = {}
          for l in layers:
            self.parseLayer(l, data)
          
          # Choose Layer and SRS by (alphabetical) index
          if layer is None:
            layer = sorted(data.keys())[index]
          if srs is None:
            srs = sorted(data[layer])[0]
      except:
          pass
      print "Displaying from %s/%s: layer %s in SRS %s." % (host, baseurl, layer, srs)
      
      # generate tile URL and init projection by EPSG code
      self.url = baseurl + "?LAYERS=%s&SRS=%s&FORMAT=image/png&TRANSPARENT=TRUE&SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap" % (layer, srs)
      self.isPGoogle = False
      self.isPLatLon = False
      if srs=="EPSG:4326":
        self.isPLatLon = True
      elif srs=="EPSG:900913" or srs == "EPSG:3857":
        self.isPGoogle = True
        try:
          self.projection = pGoogle
        except:
          pass
      else:
        try:
          self.projection = Proj(init=srs)
        except:
          pass