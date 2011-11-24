# -*- coding: utf-8 -*-

import kivy
kivy.require('1.0.7')

from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from MapViewer import MapViewer

class KVMaps(App):
  def build(self):
    layout = FloatLayout()
    self.mv = MapViewer(maptype="Roadmap", provider="openstreetmap")
    layout.add_widget(self.mv)
    return layout
    
if __name__ in ('__android__','__main__'):
  KVMaps().run()
