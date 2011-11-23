import kivy
kivy.require('1.0.7')

from kivy.app import App
from MapViewer import MapViewer

class BingMap(App):
  def build(self):
    return MapViewer(maptype="satellite", provider="bing")
  
if __name__ in ('__android__','__main__'):
  BingMap().run()

