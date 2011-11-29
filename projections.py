try: 
  from pyproj import Proj, transform

  ### utility methods for projection - pyproj support ########################################
  pLatlon = Proj(init='epsg:4326')
  p32633  = Proj(init='epsg:32633')
  pGoogle = Proj(init='epsg:3857')
  
  def project_to_unit(proj, x, y):
    '''Projects any coordinate system to a bent mercator unit square.'''
    lon, lat = transform(proj, pLatlon, x, y)
    return latlon_to_unit(lat, lon)

  def unit_to_project(proj, x, y):
    '''Unprojects unit square to any coordinate system.'''
    lat, lon = unit_to_latlon(x,y)
    return transform(pLatlon, proj, lon, lat)
  #############################################################################################
    
except ImportError:
  pass
from math import pi, sin, cos, atan2, sqrt, radians, log, atan, exp, tan

### utility methods for projection ############################################################

def latlon_to_unit(lat, lon):
  '''Projects the given lat/lon to bent mercator image
     coordinates [-1,1] x [-1,1]. (as defined by Google)
  '''
  return (lon / 180.0, log(tan(pi / 4.0 + (lat * pi / 180.0) / 2.0)) / pi) #exact calculation


def unit_to_latlon(x, y):
  '''Unprojects the given bent mercator image coordinates [-1,1] x [-1,1] to
     the lat/lon space.
  '''
  return ((2 * atan(exp(y * pi)) - pi / 2) * 180.0 / pi, x * 180)

def p4326_to_unit(lon, lat):
  return lon / 180.0, lat / 90.0
  
def unit_to_p4326(x, y):
  return x * 180.0, y * 90.0

GCONST = 20037508.342789244
def latlon_to_google(lat, lon):
  x,y = latlon_to_unit(lat, lon)
  return x*GCONST, y*GCONST

def google_to_latlon(x, y):
  return unit_to_latlon(x / GCONST, y / GCONST)  
  
def unit_to_custom(x, y, bounds):
  ulx, uly, orx, ory = bounds
  dx, dy = orx-ulx, ory-uly
  return ulx + (x + 1.0) / 2.0 * dx , uly + (y + 1.0) / 2.0 * dy

def custom_to_unit(x, y, bounds):
  ulx, uly, orx, ory = bounds
  dx, dy = orx-ulx, ory-uly
  return (x - ulx) * 2.0 / dx - 1.0, (y-uly) * 2.0 / dy - 1.0

# !NOTE! These method map the given local bounds to a global lat/lon system. This is not a proper reprojection.
# While the overlays operate within the bounds, the map itself believes to operate in WGS84.
def latlon_to_custom(lat, lon, bounds):
  ux, uy = latlon_to_unit(lat, lon)
  x, y   = unit_to_custom(ux, uy, bounds)  
  return x,y
def custom_to_latlon(x, y, bounds):
  u, v   = custom_to_unit(x, y, bounds)  
  l, m   = unit_to_latlon(u, v)
  return l, m
  
###############################################################################################

def fix180(x):
  '''wrap all coordinates into [-180;180]'''
  return ((x + 180) % 360) - 180
