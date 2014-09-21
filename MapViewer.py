# -*- coding: utf-8 -*-

'''
  Generic map viewer widget for kivy. 
  sourced from mtMaps for pyMT by tito (Mathieu Virbel / kivy dev team)
  ported to kivy by relet (Thomas Hirsch / Statens kartverk)
'''

import kivy
kivy.require('1.0.7')

from kivy.factory import Factory
from kivy.cache import Cache
from kivy.logger import Logger
from kivy.loader import Loader
from kivy.clock import Clock

from kivy.uix.widget import Widget
from kivy.uix.scatter import ScatterPlane
from kivy.uix.stencilview import StencilView

from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.label import Label

from kivy.graphics import Color, Rectangle, Ellipse, Line
from kivy.graphics.transformation import Matrix
from kivy.vector import Vector

import time, pickle
from os.path import join, dirname

from TileServer import TileServer
from projections import *

from WFSOverlayServer import GMLNS

from os import _exit
INACTIVITY_TIMEOUT = 300 # in s - if close_on_idle is True, mapviewer will exit the application after prolonged inactivity

### static configuration - to be parametrized #################################################
# size of tiles
TILE_W = 256
TILE_H = 256
###############################################################################################


class MapViewerPlane(ScatterPlane):
  '''Infinite map plane, displays only tiles on the screen. Uses TileServer to provide tiles.

    :Parameters:
        `provider`: str, default to 'bing'
            Provider to use
        `tileserver`: TileServer, default to None
            Specify a custom tileserver class to use
  '''
  
  def __init__(self, **kwargs):
    kwargs.setdefault('do_rotation', False)
    #kwargs.setdefault('do_rotation', True)
    kwargs.setdefault('show_border', False)
    kwargs.setdefault('close_on_idle', False) 
    kwargs.setdefault('scale_min', 1)
    super(MapViewerPlane, self).__init__(**kwargs)    # init ScatterPlane with above parameters
    self.status_cb    = kwargs.get('status_cb', None) # return debug information to callback method
    self.legend_cb    = kwargs.get('legend_cb', None) # return debug information to callback method

    self._tileserver = None
    self.tileserver = kwargs.get('tileserver', None)
    self.maptype = kwargs.get('maptype', 'roadmap')
    if self.tileserver is None:
        self.provider = kwargs.get('provider', 'bing')
    self.tiles = []
    
    self._cache_bbox = None 
    self._dt = 1
    
    self.lastmove = 0
    self.overlays = []
    self.overlaycache = {}
    
    self.quality = 1
    self.maxzoomlevel = 35
    self.xy = self.get_xy_from_latlon(60,10)
    self.tilecount = 0

    self.minscale = 0
    self.scale = 3
    self.maxscale = pow(2, self.maxzoomlevel)
    
    self.loadtimes = {}
    
    Clock.schedule_interval(self.update, .1)

  def update(self, dt):
    self._dt = dt
    self.tileserver.update()
    self.draw()
    
  def _get_provider(self):
        if self._tileserver:
            return self._tileserver.provider_name
        return ''
  def _set_provider(self, x):
        if x == self.provider:
            return
        if x in TileServer.providers:
            self.tileserver = TileServer.providers[x]()
        else:
            raise Exception('Unknown map provider %s' % x)
  provider = property(_get_provider, _set_provider)

  def _get_tileserver(self):
        return self._tileserver
  def _set_tileserver(self, x):
        if x == self._tileserver:
            return
        if self._tileserver is not None:
            self._tileserver.stop()
        self._tileserver = x
        self._tileserver.start()
  tileserver = property(_get_tileserver, _set_tileserver)

  
  @property
  def zoom(self):
    '''Get zoom from current scale'''
    self._zoom = max(1, int(log(self.scale, 2))) + self.quality
    return self._zoom

  def tile_bbox(self, zoom):
    '''return tile bounding box for this zoom level'''
    pzoom = pow(2, zoom) # FIXME: grok and document
    pzw = pzoom / float(TILE_W)
    pzh = pzoom / float(TILE_H)
    minx, miny = self.omin
    maxx, maxy = self.omax
    adjust = 0
    minx = int(minx * pzw) - adjust
    miny = int(miny * pzh) - adjust
    maxx = int(maxx * pzw) + adjust
    maxy = int(maxy * pzh) + adjust
    return (minx, miny, maxx, maxy)

  def compute_tiles_for_zoom(self, zoom, tiles):
        '''Calculate and put on `tiles` all tiles needed to draw this zoom
        level.
        '''
        # initialize
        pzoom = pow(2, zoom - 1)
        bound = int(pow(2, zoom))
        tw = TILE_W / float(pzoom)
        th = TILE_H / float(pzoom)
        ret = True

        # clamp to texsize
        pzw = pzoom / float(TILE_W)
        pzh = pzoom / float(TILE_H)
        minx, miny = self.omin
        maxx, maxy = self.omax
        
        minx = int(minx * pzw)
        miny = int(miny * pzh)
        maxx = int(maxx * pzw)
        maxy = int(maxy * pzh)

        # Explanation about tile clamp
        #
        # if tilesize is 50
        # 0 ----------------------------- 100
        #           ^ value = 30
        # ^ clamped value = 0
        #                ^ value = 50
        #                ^ campled value = 50
        #                        ^ value = 65
        #                ^ campled value = 50
        # => value is clampled to the minimum
        #
        # So we have a trouble if the value is negative
        # -100 -------------------------- 0
        #                        ^ value = -30
        #                  ^ clamped value = -50
        #           ^ value = -75
        #  ^ clamped value = -100
        #
        # So we adjust clamp border for :
        # 1. take in account the clamp problem with negative value
        # 2. add one tile in every side to enhance user experience
        #    (load tile before it will be displayed)

        adjust = 1 
        minx -= adjust
        miny -= adjust
        maxx += adjust
        maxy += adjust

        # draw !
        self.tilecount = 0
        midx, lenx = (minx + maxx) / 2, (maxx - minx) / 2 +1
        midy, leny = (miny + maxy) / 2, (maxy - miny) / 2 +1
        
        #for x in xrange(minx, maxx):
        for dx in xrange(0, lenx):
          for x in [midx+dx, midx-1-dx]:
        #    for y in xrange(miny, maxy):
            for dy in xrange(0, leny):
              for y in [midy+dy, midy-1-dy]:
                # stats
                self.tilecount += 1

                # texture coord
                tx, ty = x * tw, y * th

                # get coordinate for x/y
                nx = x % int(bound) #x<bound and x or 0 
                ny = y % int(bound) #y<bound and y or 0 

                tile = (
                    nx, ny, tx, ty,
                    tw, th, zoom, bound
                )

                ret = ret and self.tile_exist(*tile)
                if zoom > self.zoom-1: #do not prefetch the whole pyramid
                    tiles.append(tile)

        return ret

  def tile_exist(self, nx, ny, tx, ty, sx, sy, zoom, bound):
    '''Check if a specific tile exists'''
    return self.tileserver.exist(nx, bound-ny-1, zoom, self.maptype)

  def tile_draw(self, nx, ny, tx, ty, sx, sy, zoom, bound):
        '''Draw a specific tile on the screen.
        Return False if the tile is not yet available.'''
        # nx, ny = index of tile
        # tx, ty = real position on scatter
        # sx, sy = real size on scatter
        # pzoom = current zoom level
        image = self.tileserver.get(nx, bound-ny-1, zoom, self.maptype)
        if image in (None, False):
            return

        if not image.texture:
          Logger.exception('Returned image has no texture.')
          return
        if image.texture.wrap is None:
          image.texture.wrap = GL_CLAMP

        alpha = Cache.get('tileserver.tilesalpha', image.id)
        if alpha is None:
          alpha = 0
        if image.loaded:          # as soon as we have the image
          alpha += min(self._dt * 4, 1.0)  # fade it in
        Cache.append('tileserver.tilesalpha', image.id, alpha)

        with self.canvas:
          Color(1, 1, 1, alpha)
          Rectangle(pos=(tx, ty), size=(sx, sy), texture=image.texture)
    
  def draw(self): 
    # calculate boundaries
    parent = self.parent
    
    #self.omin = self.to_local(*parent.pos)
    #self.omax = self.to_local(parent.x + parent.width, parent.y + parent.height)
    #osize = self.omax[0]-self.omin[0], self.omax[1]-self.omin[1]
    
    xmin = min(parent.x, parent.x + parent.width)
    xmax = max(parent.x, parent.x + parent.width)
    ymin = min(parent.y, parent.y + parent.height)
    ymax = max(parent.y, parent.y + parent.height)
    
    self.bottom_left  = self.get_latlon_from_xy(xmin, ymin) 
    self.top_right    = self.get_latlon_from_xy(xmax, ymax)  
    
    self.omin = self.to_local(xmin, ymin)
    self.omax = self.to_local(xmax, ymax)
    
    self.cmin  = self.to_local(xmin, ymin)
    self.cmax  = self.to_local(xmax, ymax)
    self.csize = self.cmax[0]-self.cmin[0], self.cmax[1]-self.cmin[1]
    
    # draw background
    self.canvas.clear()
    with self.canvas:
      Color(0, 0, 0)
      Rectangle(pos=(0,0), size=(2000,2000))

    # check if we must invalidate the tiles
    bbox = self.tile_bbox(self.zoom)
    if self._cache_bbox != bbox:
      self._cache_bbox = bbox
      self.tiles = []

    if not self.tiles:
      # precalculate every tiles needed for each zoom
      # from the current zoom to the minimum zoom
      # if the current zoom is completly loaded,
      # drop the previous zoom
      self.tiles = tiles = []
      will_break = False
      for z in xrange(self.zoom, 0, -1): #self.zoom-1
        if self.compute_tiles_for_zoom(z, tiles):
          if z > 0:
            self.compute_tiles_for_zoom(z - 1, tiles)
          break

    # now draw tiles, center first
    for tile in reversed(self.tiles):
      self.tile_draw(*tile)
    
    if (not self.lastmove is 0) and time.time() > self.lastmove + INACTIVITY_TIMEOUT: 
        _exit(1)

    if self.legend_cb:
        self.legend_cb(None)
        
    for overlay in self.overlays:
      if overlay.type == "wms":
          image = None
          if self.lastmove is None or time.time() > self.lastmove + 0.5: # wait a second after moving before we try to contact the WMS
            image = overlay.get(self, parent.width, parent.height)
          oldalpha = overlay.max_alpha
          if (image not in (None, False)) and image.loaded:
            if image not in self.loadtimes:
              self.loadtimes[image]=time.time()
            alpha = max(0,min((time.time()-self.loadtimes[image]) * 1, overlay.max_alpha))  # fadein
            oldalpha = overlay.max_alpha - alpha
            if oldalpha == 0: # as soon as the old image is faded out, put this one in the cache
              self.overlaycache[overlay.provider_name+overlay.layer] = image, self.cmin, self.csize # self.omin, osize
            with self.canvas:
              Color(1, 1, 1, alpha)
              Rectangle(pos=self.cmin, size=self.csize, texture=image.texture)

          # try displaying the previous image from this overlay, until the next one is fully displayed
          image, pos, isize = self.overlaycache.get(overlay.provider_name+overlay.layer, (None, None, None))
          if image:
            with self.canvas:
              Color(1, 1, 1, oldalpha)
              Rectangle(pos=pos, size=isize, texture=image.texture)
              
          if self.legend_cb:
            # display the legend graphic
            image = overlay.getLegendGraphic()
            if image.loaded:
              self.legend_cb(image)

      elif overlay.type == "wfs":
          geometries = None
          if self.lastmove is None or time.time() > self.lastmove + 0.5: # wait a second after moving before we try to contact the WFS
            geometries = overlay.get(self, parent.width, parent.height)
          if geometries is not None:
            with self.canvas:
              for geom in geometries:
                if geom.tag == "{%s}Point" % GMLNS:
                  copos = map(float,geom.getchildren()[0].text.split())
                  l, m = overlay.co_to_ll(copos[0], copos[1])
                  x,y = self.get_xy_from_latlon(l, m) 
                  
                  Color(0, 0, 0)
                  r = 10.0/self.scale
                  Ellipse(pos=(x-r/2, y-r/2), size=(r,r))
                  Color(1, 1, 1)
                  r = 8.0/self.scale
                  Ellipse(pos=(x-r/2, y-r/2), size=(r,r))
                  print x,y,r
                elif geom.tag == "{%s}LinearRing" % GMLNS:
                  #copos = map(float,geom.getchildren()[0].text.split())
                  #points = []
                  #for i in xrange(0,len(copos),2):
                  #  l, m = overlay.co_to_ll(copos[0], copos[1])
                  #  x, y = self.get_xy_from_latlon(l, m) 
                  #  points.append(x)
                  #  points.append(y)
                  #points.extend(points[0:1])
                  #Color(1, 0.5, 0.5)
                  #Line(points=points)
                  pass
          
    if self.status_cb:
      self.status_cb(self.tileserver.q_count, self.tilecount)

  def checkTooltips(self, touch):
    l, m = self.get_latlon_from_xy(*touch.pos)
    for overlay in self.overlays:
      tip = overlay.getInfo(l, m, 100.0/self.scale)
      if tip is not None:
        popup = Popup(title='WFS FeatureInfo',
            content=Label(text=tip),
            size_hint=(None, None), size=(800, 400))
        popup.open()
        break
      
  def on_touch_move(self, touch):
    super(MapViewerPlane, self).on_touch_move(touch) # delegate to scatterplane first
    self.lastmove = time.time()
    
  def on_touch_down(self, touch):
    super(MapViewerPlane, self).on_touch_down(touch) # delegate to scatterplane first
    # print self._get_pos(), self._get_scale()
    self.checkTooltips(touch)
    
  def get_latlon_from_xy(self, x, y):
    '''Get latitude/longitude from x/y in scatter (x/y will be transformed
       in scatter coordinate space)
    '''                                  # FIXME: grok + document
    x, y = self.to_local(x, y)           # transform into scatterplane space
    p = Vector(x, y) / (TILE_W, TILE_H)  # 
    nx = (p.x % 2) - 1                   # bind into range [-1, 1[
    ny = 1 - (p.y % 2)                   # bind into range ]-1, 1]
    lx, ly = unit_to_latlon(nx, (-ny))   # 
    return lx, ly                        #

  def get_xy_from_latlon(self, lat, lon):
    '''Return x/y location from latitude/longitude'''
    (ratio_x, ratio_y) = latlon_to_unit(lat % 180, lon % 360)
    return (ratio_x * TILE_W * self.scale, ratio_y * TILE_H * self.scale)
        

  def distance(self, latlon1, latlon2):
        '''Return distance between 2 latlon - FIXME: use proj library?'''
        lat1, lon1 = map(radians, latlon1)
        lat2, lon2 = map(radians, latlon2)

        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = (sin(dlat/2))**2 + cos(lat1) * cos(lat2) * (sin(dlon/2.0))**2
        c = 2 * atan2(sqrt(a), sqrt(1.0-a))
        km = 6371.0 * c
        return km

  def apply_angle_scale_trans(self, angle, scale, trans, point):
        #FIXME: this does not work as expected
        newscale = self.scale * scale
        if newscale < self.minscale or newscale > self.maxscale:
            newscale = 1
        tf = Matrix().rotate(angle,1,1,1).scale(scale,scale,1).translate(trans.x, trans.y, 0)
        super(MapViewerPlane, self).apply_transform(tf)
  
class MapViewer(StencilView):
  '''Objective: Display WMS-T, WMS and eventually WFS services on a zoomable/scrollable map'''
  
  def __init__(self, **kwargs):
    super(MapViewer, self).__init__(**kwargs)  # init StencilView
    self.map = MapViewerPlane(**kwargs)        # init content plane
    self.add_widget(self.map)                  # add content plane subwidget
    self.readonly    = kwargs.get('readonly',   False) # parameter readonly disables clicking/scrolling/zooming
        
  def world_diameter(self):
    "return size of displayed map in projection space"
    left = self.map.get_latlon_from_xy(self.x, self.y)
    center = self.map.get_latlon_from_xy(*self.center)
    return 2 * self.map.distance(left, center) 
    
  def on_touch_down(self, touch):
    if self.readonly: return                   # map is not to be clicked
    if not self.collide_point(*touch.pos):     # touch is not within bounds
      return False
    return super(MapViewer, self).on_touch_down(touch)  # delegate to stencil

  def on_touch_move(self, touch):
    if self.readonly: return                   # map is not to be scrolled/zoomed
    if not self.collide_point(*touch.pos):     # touch is not within bounds
      return False
    return super(MapViewer, self).on_touch_move(touch) # delegate to stencil

  def on_touch_up(self, touch):
    if self.readonly: return
    if not self.collide_point(*touch.pos):
      return False
    return super(MapViewer, self).on_touch_up(touch)
    
  def move_to(self,x,y,z):
    self.map._set_scale(z)
    self.map._set_pos((x,y))
    
  def center_to_latlon(self, coord_latlon, screen_w, screen_h):
    zero_xy = ( (screen_w*0.5)-(TILE_W*self.map.scale) , (screen_h*0.5)-(TILE_H*self.map.scale) )
    target_xy = self.map.get_xy_from_latlon( *coord_latlon )
    self.move_to( zero_xy[0]- target_xy[0], zero_xy[1]- target_xy[1], self.map.scale)

  def reset(self):
    #self.move_to(-6555.742468339471, -10304.331710006307,5.78284048773) #1920x1080
    self.move_to(-3748.8157983360124, -5857.7510923382652, 3.26647927983) #android
    
Factory.register('MapViewer', MapViewer)
