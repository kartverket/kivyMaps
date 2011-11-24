from projections import *
from urllib2 import urlopen
from httplib import HTTPConnection
from threading import Thread
from kivy.logger import Logger
from kivy.loader import Loader
from os.path import join, dirname
import time, os
import hashlib

GMLNS = "http://www.opengis.net/gml"

try:
    from pyproj import Proj
    from lxml.etree import ElementTree as ET 
except:
#    try: 
        from xml.etree import ElementTree as ET
#    except:
#        pass

class WFSOverlayServer(object):
    cache = {} 
    available_maptype = dict(roadmap = 'Roadmap') # default
    type = "wfs" # TODO: replace handling in mapviewer with action handlers in the overlay class
 
    '''Generic WMS server'''
    def __init__(self, progress_callback=None):    
      self.progress_callback = progress_callback
      
    def setProgressCallback(self, progress_callback):
      self.progress_callback = progress_callback

    def load(self, url):
        # read from internet
        blocksize = 4096
        self.progress_callback(0)
        fd = urlopen(url)
        idata = fd.read(blocksize)
        loaded = blocksize
        while True:
          bdata = fd.read(blocksize)
          if not bdata: break
          loaded += blocksize
          if self.progress_callback:
              self.progress_callback(loaded)
          idata += bdata
        fd.close()
        self.progress_callback(-1)
        return idata

    def findGeometry(self, elem):
        geoms = elem.find("{%s}Point" % GMLNS)
        if geoms is not None:
            return geoms
        geoms = elem.find("{%s}LinearRing" % GMLNS)
        if geoms is not None:
            return geoms
        for c in elem.getchildren():
            geom = self.findGeometry(c)
            if geom is not None:
                return geom
                    
    def findGeometries(self, members):
        geoms = []
        for m in members:
            geom = self.findGeometry(m)
            if geom is not None:
                geoms.append(geom)
        return geoms
        
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
        xml = self.load('http://' + self.provider_host + url)
        
        tree = ET.fromstring(xml)
        members = tree.findall("{%s}featureMember" % GMLNS)
        
        self.geometries = self.findGeometries(members)
        self.cache[key] = self.geometries
        return self.geometries
        
      except Exception,e:
        Logger.error('OverlayServer could not find (or read) WFS from %s [%s]' % (url, e))
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
        return self.url + "&bbox=%f,%f,%f,%f" % (x1, y1, x2, y2)
      except RuntimeError, e:
        return None
      
    def parseFeature(self, feature, data):
      try:
        name  = feature.find("Name").text
        title = feature.find("Title").text
      except:
        name  = None
        title = None
      srss = feature.findall("DefaultSRS")
      if name:# and srss:
        data[name] = map(lambda x:x.text, srss)
        if self.debug:
          print "Provider %s provides feature %s in projections %s" % (self.provider_host, name, data[name])
      
    def initFromGetCapabilities(self, host, baseurl, feature = None, index = 0, srs = None):
      self.debug = (feature == None) and (index == 0)
      # GetCapabilities (Features + SRS)
      capabilities = urlopen(host + baseurl + "?SERVICE=WFS&Request=GetCapabilities").read().strip()
      try:
          tree = ET.fromstring(capabilities)
          if self.debug:
            ET.dump(tree)
          features = tree.findall("FeatureType") #TODO: proper parsing of cascading layers and their SRS
          data = {}
          for f in features:
            self.parseFeature(f, data)
          
          # Choose Feature and SRS by (alphabetical) index
          if feature is None:
            feature = sorted(data.keys())[index]
          if srs is None:
            srs = sorted(data[feature])[0]
      except:
          pass
      print "Displaying from %s/%s: feature %s in SRS %s." % (host, baseurl, feature, srs)
      
      # generate tile URL and init projection by EPSG code
      self.url = baseurl + "?typeName=namespace:%s&SERVICE=WFS&VERSION=1.1.0&REQUEST=GetFeature&maxFeatures=50" % (feature)
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