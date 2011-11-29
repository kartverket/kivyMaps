import kivy
kivy.require('1.0.7')

from kivy.loader import Loader
from kivy.cache import Cache
from kivy.logger import Logger
from kivy.factory import Factory

from kivy.core.image import Image

from os.path import join, dirname, exists, isdir, isfile, sep
from os import makedirs, mkdir, _exit
from collections import deque
from threading import Condition, Thread, Event
#from httplib import HTTPConnection
from urllib2 import urlopen
from random import randint

from projections import *

### static configuration - TODO: parametrize ####################################
# number of threads to use
TILESERVER_POOLSIZE = 10
TILESERVER_MAXPIPELINE = 2
#################################################################################

### init cache - TODO: parametrize ##############################################
Cache.register('tileserver.tiles', limit=10, timeout=10) #1000/10000
Cache.register('tileserver.tilesalpha', limit=10, timeout=10)
#################################################################################

class TileServer(object):
    '''Base implementation for a tile provider.
    Check GoogleTileServer and YahooTileServer if you intend to use more
    '''
    provider_name = 'unknown'
    providers = dict()
    
    @staticmethod
    def register(cls):
        TileServer.providers[cls.provider_name] = cls

    def __init__(self, poolsize=TILESERVER_POOLSIZE):
        self.cache_path = join(dirname(__file__), 'cache', self.provider_name)
        if not isdir(self.cache_path):
            makedirs(self.cache_path)

        black = Loader.image(join('documents','black.png'))
        #Loader._loading_image = black
            
        self.q_in       = deque()
        self.q_out      = deque()
        self.q_count    = 0
        self.c_in       = Condition()
        self.workers    = []
        self.poolsize   = poolsize
        self.uniqid     = 1
        self.want_close = False
        self.available_maptype = dict(roadmap='Roadmap')
        self.hcsvnt     = Loader.image(join('documents','hcsvnt.png'))
        

    def start(self):
        '''Start all the workers
        '''
        for i in xrange(self.poolsize):
            self.create_worker()

    def create_worker(self):
        '''Create a new worker, and append to the list of current workers
        '''
        thread = Thread(target=self._worker_run,
                        args=(self.c_in, self.q_in, self.q_out))
        thread.daemon = True
        thread.start()
        self.workers.append(thread)

    def stop(self, wait=False):
        '''Stop all workers
        '''
        self.want_close = True
        if wait:
            for x in self.workers:
                x.join()


    def post_download(self, filename):
        '''Callback called after the download append. You can use it for
        doing some image processing, like cropping

        .. warning::
            This function is called inside a worker Thread.
        '''
        pass

    def to_filename(self, nx, ny, zoom, maptype, format):
        fid = self.to_id(nx, ny, zoom, maptype, format)
        hash = fid[0:2]
        return join(self.cache_path, hash, fid)

    def to_id(self, nx, ny, zoom, maptype, format):
        return '%d_%d_%d_%s.%s' % (nx, ny, zoom, maptype, format)

    def exist(self, nx, ny, zoom, maptype, format='png'):
        filename = self.to_filename(nx, ny, zoom, maptype, format)
        img = Cache.get('tileserver.tiles', filename)
        return bool(img)

    def get(self, nx, ny, zoom, maptype, format='png'):
        '''Get a tile
        '''
        filename = self.to_filename(nx, ny, zoom, maptype, format)
        img = Cache.get('tileserver.tiles', filename)

        # check if the tile is already being loaded
        if img is False:
            return None

        # check if the tile exist in the cache
        if img is not None:
            return img

        # no tile, ask to workers to download 
        Cache.append('tileserver.tiles', filename, False)
        self.q_count += 1
        self.q_in.append((nx, ny, zoom, maptype, format))
        self.c_in.acquire()
        self.c_in.notify()
        self.c_in.release()
        return None

    def update(self):
        '''Must be called to get pull image from the workers queue
        '''
        
        pop = self.q_out.pop
        while True:
            try:
                filename, image = pop()
                self.q_count -= 1
            except:
                return
            Cache.append('tileserver.tiles', filename, image)

    def _worker_run(self, c_in, q_in, q_out):
        '''Internal. Main function for every worker
        '''
        do = self._worker_run_once

        while not self.want_close:
            try:
                do(c_in, q_in, q_out) 
            except:
                Logger.exception('TileServerWorker: Unknown exception, stop the worker')
                return
                
    def _worker_run_once(self, c_in, q_in, q_out):
        '''Internal. Load one image, process, and push.
        '''
        # get one tile to process
        try:
            nx, ny, zoom, maptype, format = q_in.pop()
        except:
            c_in.acquire()
            c_in.wait()
            c_in.release()
            return

        # check if the tile already have been downloaded
        filename = self.to_filename(nx, ny, zoom, maptype, format)
        loaded = True
        if not isfile(filename):
            loaded = False

            # calculate the good tile index
            tz = pow(2, zoom)
            lx, ly = unit_to_latlon(2.0 * (nx + 0.5) / tz - 1, 1 - 2.0 * (ny + 0.5) / tz)
            lx, ly = map(fix180, (lx, ly))

            # get url for this specific tile
            url = self.geturl(
                nx=nx, ny=ny,
                lx=lx, ly=ly,
                tilew=256, tileh=256,
                zoom=zoom,
                format=format,
                maptype=maptype
            )

            for i in xrange(1,3):
              try:
                conn = urlopen("http://%s%s" % (self.provider_host, url))
              except Exception,ex:
                print "ERROR IN %s/%s \n%s" % (self.provider_host, url, str(ex))
                continue
              
              try:
                  data = conn.read()
                  conn.close()
              except Exception, e:
                  print 'Exception %s' % (url)
                  Logger.error('TileServer: "%s": %s' % (str(e), filename))
                  Logger.error('TileServer: "%s": URL=%s' % (str(e),url))
                  continue
            
              # discard error messages
              if data[:5] == "<?xml":
                  msg = ""
                  try: 
                    msg = data[data.index("<ServiceException>")+18 : data.index("</ServiceException")]
                  except:
                    pass
                  Logger.error('Tileserver: Received error fetching %s: %s' % (url, msg))
                  continue
                
            
              # write data on disk
              try:
                  directory = sep.join(filename.split(sep)[:-1])
                  if not isdir(directory):
                    try:
                      mkdir(directory)
                    except:
                      pass # that was probably just a concurrency error - if dir is missing, all threads report it
                  with open(filename, 'wb') as fd:
                      fd.write(data)
              except:
                  Logger.exception('Tileserver: Unable to write %s' % filename)
                  continue

              # post processing
              self.post_download(filename)
              loaded = True
              break
        
        if not loaded:
          return        

        # load image
        try:
          image = Loader.image(filename)
        except Exception,e:
          Logger.error('TileServer|HCSVNT "%s": file=%s' % (str(e), filename))
          image = self.hcsvnt
        image.id = 'img%d' % self.uniqid
        self.uniqid += 1

        # push image on the queue
        q_out.appendleft((filename, image))



class GoogleTileServer(TileServer):
    '''Google tile server.

    .. warning::
        This tile server will not work, cause of limitation of Google.
        It's just for testing purpose, don't use it !
    '''

    provider_name = 'google'
    provider_host = 'maps.google.com'
    available_maptype = dict(roadmap='Roadmap')

    def geturl(self, **infos):
        infos['tileh'] += GMAPS_CROPSIZE * 2 # for cropping
        return '/maps/api/staticmap?center=' + \
               "%(lx)f,%(ly)f&zoom=%(zoom)d&size=%(tilew)dx%(tileh)d" \
               "&sensor=false&maptype=%(maptype)s&format=%(format)s" % \
               infos

    def post_download(self, filename):
        # Reread the file with pygame to crop it
        import pygame
        img = pygame.image.load(filename)
        img = img.subsurface((0, GMAPS_CROPSIZE, 256, 256))
        pygame.image.save(img, filename)

class YahooTileServer(TileServer):
    '''Yahoo tile server implementation
    '''

    provider_name = 'yahoo'
    provider_host = 'us.maps2.yimg.com'
    available_maptype = dict(roadmap='Roadmap')

    def geturl(self, **infos):
        def toYahoo(col, row, zoom):
            x = col
            y = int(pow(2, zoom - 1) - row - 1)
            z = 18 - zoom
            return x, y, z
        coordinates = 'x=%d&y=%d&z=%d' % toYahoo(infos['nx'], infos['ny'], infos['zoom'])
        return '/us.png.maps.yimg.com/png?v=%s&t=m&%s' % \
            ('3.52', coordinates)

            
class BlueMarbleTileServer(TileServer):
    '''Blue Marble tile server implementation
    '''

    provider_name = 'bluemarble'
    provider_host = 's3.amazonaws.com'
    available_maptype = dict(roadmap='Satellite')
    def geturl(self, **infos):
        return '/com.modestmaps.bluemarble/%d-r%d-c%d.jpg' % (
            infos['zoom'], infos['ny'], infos['nx']
        )


class BingTileServer(TileServer):
    '''Bing tile server implementation. Support road and satellite
    '''

    provider_name = 'bing'
    available_maptype = dict(roadmap='Roadmap', satellite='Satellite')

    def geturl(self, **infos):
        octalStrings = ('000', '001', '010', '011', '100', '101', '110', '111')
        microsoftToCorners = {'00': '0', '01': '1', '10': '2', '11': '3'}
        def toBinaryString(i):
            return ''.join([octalStrings[int(c)] for c in oct(i)]).lstrip('0')
        def toMicrosoft(col, row, zoom):
            x = col
            y = row
            y, x = toBinaryString(y).rjust(zoom, '0'), toBinaryString(x).rjust(zoom, '0')
            string = ''.join([microsoftToCorners[y[c]+x[c]] for c in range(zoom)])
            return string
        if infos['maptype'] in ('satellite', 'aerial'):
            mapprefix = 'h'
        else:
            mapprefix = 'r'
        return '/tiles/%s%s.png?g=90&shading=hill' % \
            (mapprefix, toMicrosoft(infos['nx'], infos['ny'], infos['zoom']))

    @property
    def provider_host(self):
        return 'r%d.ortho.tiles.virtualearth.net' % randint(0, 3)

class OpenStreetMapTileServer(TileServer):
    '''OSM tile server implementation
    '''

    provider_name = 'openstreetmap'
    provider_host = 'tile.openstreetmap.org'
    available_maptype = dict(roadmap='Roadmap')

    def geturl(self, **infos):
        row, col, zoom = infos['nx'], infos['ny'], infos['zoom']
        return '/%d/%d/%d.png' % (zoom, row, col)


#
# Registers
#
TileServer.register(BlueMarbleTileServer)
TileServer.register(BingTileServer)
TileServer.register(YahooTileServer)
TileServer.register(OpenStreetMapTileServer)
#TileServer.register(GoogleTileServer) # disfunct

Factory.register('TileServer', TileServer)
