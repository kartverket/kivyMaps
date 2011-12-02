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
    
    def getInfo(self, lat, lon, epsilon):
      return None
    
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
        
    def getLegendGraphic(self):
      if self.legend is None and not self.triedlegend:
        self.triedlegend = True
        layer = self.layer
        if "," in layer:
          layer=layer[layer.rindex(",")+1:]
        if self.legendlayer: 
          layer = self.legendlayer
        url = self.baseurl + "?REQUEST=GetLegendGraphic&VERSION=1.0.0&FORMAT=image/png&LAYER=%s&ext=.png" % (layer)
        try:
          print 'http://' + self.provider_host + url
          image = Loader.image('http://' + self.provider_host + url)
          self.legend = image
        except Exception,e:
          Logger.error('OverlayServer could not find LEGENDGRAPHICS for %s %s' % (self.baseurl, layer))
      return self.legend

    def xy_to_co(self, lat, lon):
      if self.customBounds: 
        x, y = latlon_to_custom(lat, lon, self.bounds)
      elif self.isPLatLon:   # patch for android - does not require pyproj library
        x, y = lon, lat
      elif self.isPGoogle: # patch for android - does not require pyproj library
        x, y = latlon_to_google (lat, lon)
      else:
        x, y = transform(pLatlon, self.projection, lon, lat)
      return x,y

    def co_to_ll(self, x,y):
      if self.customBounds: 
        u, v = custom_to_unit(lat, lon, self.bounds)
        l, m = unit_to_latlon(u, v)
      elif self.isPLatLon:   # patch for android - does not require pyproj library
        l, m = y, x
      elif self.isPGoogle: # patch for android - does not require pyproj library
        l, m = google_to_latlon (y, x)
      else:
        l, m = transform(self.projection, pLatlon, y, x)
      return l, m
      
    def geturl(self, lat1, lon1, lat2, lon2, zoom, w, h):
      try:
        x1, y1 = self.xy_to_co(lat1, lon1)
        x2, y2 = self.xy_to_co(lat2, lon2)
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
      if layer is None or srs is None:
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
      self.layer = layer
      self.baseurl = baseurl
      self.url = baseurl + "?LAYERS=%s&SRS=%s&FORMAT=image/png&TRANSPARENT=TRUE&SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&STYLES=" % (layer, srs)
      self.isPGoogle = False
      self.isPLatLon = False
      self.legend = None
      self.legendlayer = None
      self.triedlegend = False
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