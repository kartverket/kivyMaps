# -*- coding: utf-8 -*-

import kivy
kivy.require('1.0.7')

from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from sidepanel import SidePanel
from MapViewer import MapViewer
import WMSTileServer
from WMSOverlayServer import *


class KVMaps(App):
  def add_kart(self, menu, name, provider, maptype):
    def change_kart(bself):
      self.mv.map.provider = provider
      self.mv.map.maptype = maptype
    button = Button(text=name)
    button.bind(on_press=change_kart)
    menu.add_widget(button)

  def build(self):
    layout = FloatLayout()
    self.mv = MapViewer(maptype="Roadmap", provider="openstreetmap")
    layout.add_widget(self.mv)

    sidelay = BoxLayout(orientation='vertical')
    sidelay.size = (200,200)
    menu = SidePanel(layout=sidelay, align='center', side='left')
    menu.add_widget(Label(text="Select Map", font_size=25))
    self.add_kart(menu, "OpenStreetMap", 'openstreetmap', 'Roadmap')
    self.add_kart(menu, "Microsoft Bing Roads", 'bing', 'Roadmap')
    self.add_kart(menu, "Microsoft Bing Satellite", 'bing', 'Satellite')
    self.add_kart(menu, "OSM-WMS", 'osmwms', 'Roadmap')
    layout.add_widget(menu)

    return layout
    
if __name__ in ('__android__','__main__'):
  KVMaps().run()

