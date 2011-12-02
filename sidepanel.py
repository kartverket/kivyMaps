'''
Side panel: a panel widget that attach to a side of the screen
'''

__all__ = ('SidePanel', )

from kivy.animation import Animation
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.clock import Clock
from functools import partial

class SidePanel(Widget):
    '''A panel widget that attach to a side of the screen
    (similar to gnome-panel for linux user).

    :Parameters:
        `align` : str, default to 'center'
            Alignement on the side. Can be one of
            'left', 'right', 'top', 'bottom', 'center', 'middle'.
            For information, left-bottom, center-middle, right-top have the
            same meaning.
        `corner` : Widget object, default to None
            Corner object to use for pulling in/out the layout. If None
            is provided, the default will be a Button() with appropriate
            text label (depend of side)
        `corner_size` : int, default to 30
            Size of the corner, can be the width or height, it depend of side.
        `duration` : float, default to 0.5
            Animation duration for pull in/out
        `hide` : bool, default to True
            If true, the widget will be hide by default, otherwise,
            the panel is showed
        `layout` : AbstractLayout object, default to None
            Layout to use inside corner widget. If None is provided,
            the default will be a BoxLayout() with default parameters
        `side` : str, default to 'left'
            Side to attach the widget. Can be one of
            'left', 'right', 'top', 'bottom'.
    '''
    def __init__(self, **kwargs):
        kwargs.setdefault('hide', True)

        super(SidePanel, self).__init__(**kwargs)

        self.side        = kwargs.get('side', 'left')
        self.align       = kwargs.get('align', 'center')
        self.corner_size = kwargs.get('corner_size', 30)
        self.duration    = kwargs.get('duration', .5)
        self.relIndex    = kwargs.get('relative', 0)
        layout           = kwargs.get('layout', None)
        corner           = kwargs.get('corner', None)

        assert(self.side in ('bottom', 'top', 'left', 'right'))
        assert(self.align in ('bottom', 'top', 'left', 'right', 'middle', 'center'))

        if layout is None:
            from kivy.uix.boxlayout import BoxLayout
            layout = BoxLayout()
        self.layout = layout
        super(SidePanel, self).add_widget(layout)

        if corner is None:
            if self.side == 'right':
                label = '<'
            elif self.side == 'left':
                label = '>'
            elif self.side == 'top':
                label = 'v'
            elif self.side == 'bottom':
                label = '^'
            self.corner = Button(text=label)
        else:
            self.corner = Button()
            self.corner.texture = corner.texture
            self.corner.texture_size = corner.texture_size
            self.corner.size = corner.texture_size[0]+6, corner.texture_size[1]+6
            self.corner_size = None
        
        if corner:
          super(SidePanel, self).add_widget(self.corner)
        self.corner.bind(on_press = self._corner_on_press)

        self.initial_pos = self.pos
        self.need_reposition = True

        if kwargs.get('hide'):
            self.visible = False
            self.hide()
            
        Clock.schedule_once(self.update, .1)
    
    def add_widget(self, widget):
        self.layout.add_widget(widget)
        self.update()

    def remove_widget(self, widget):
        self.layout.remove_widget(widget)
        self.update()

    def _corner_on_press(self, *largs):
        if self.visible:
            self.hide()
        else:
            self.show()
        return True

    def _get_position_for(self, visible):
        # get position for a specific state (visible or not visible)
        w = self.get_parent_window()
        if not w:
            return

        side = self.side
        x = self.layout.x
        y = self.layout.y
        
        if visible:
            if side == 'right':
                x = w.width - self.layout.width 
            elif side == 'top':
                y = w.height - self.layout.height
            elif side == 'left':
                x = 0
            elif side == 'bottom':
                y = 0
        else:
            if side == 'left':
                x, y = (-self.layout.width, y)
            elif side == 'right':
                x, y = (w.width, y)
            elif side == 'top':
                x, y = (x, w.height)
            elif side == 'bottom':
                x, y = (x, -self.layout.height)
        return x, y

    def _get_corner_position_for(self, visible):
        # adjust size + configure position
        w = self.get_parent_window()
        if not w:
            return

        side = self.side
        align = self.align
        
        cw, ch = self.corner.size
        dx, dy = self._get_position_for(visible)
        if side in ('left', 'right'):
            if self.corner_size is not None:
                self.corner.size = (self.corner_size, self.layout.height)
            if align in ('bottom', 'left'):
                cy = ly = 0
            elif align in ('top', 'right'):
                ly = w.height - self.layout.height
                cy = w.height - ch
            elif align in ('center', 'middle'):
                ly = w.center[1] - self.layout.height / 2.
                cy = w.center[1] - ch / 2.
            self.layout.y = ly
        elif side in ('top', 'bottom'):
            if self.corner_size is not None:
                self.corner.size = (self.layout.width, self.corner_size)
            if align in ('bottom', 'left'):
                cx = lx = 0
            elif align in ('top', 'right'):
                lx = w.width - self.layout.width
                cx = w.width - cw
            elif align in ('center', 'middle'):
                lx = w.center[0] - self.layout.width / 2.
                cx = w.center[0] - cw / 2.
            self.layout.x = lx
        if side == 'left':
            cx = dx + self.layout.width
            cy = cy + self.corner.height * self.relIndex
        elif side == 'right':
            cx = dx - self.corner.width
            cy = cy + self.corner.height * self.relIndex
        elif side == 'top':
            cy = dy - self.corner.height
        elif side == 'bottom':
            cy = dy + self.layout.height
        return cx,cy
    
    def show(self, *largs):
        dpos = self._get_position_for(visible=True)
        cpos = self._get_corner_position_for(visible=True)
        
        # bring to front on activation
        parent = self.parent
        parent.remove_widget(self)
        parent.add_widget(self)
        self.visible = True
        
        Animation(d=self.duration, t='out_cubic', pos=dpos).start(self.layout)
        Animation(d=self.duration, t='out_cubic', pos=cpos).start(self.corner)

    def _on_animation_complete_hide(self, *largs):
        self.visible = False

    def hide(self, *largs):
        dpos = self._get_position_for(visible=False)
        cpos = self._get_corner_position_for(visible=False)
        if dpos is None:
            return
        anim = Animation(d=self.duration, t='out_cubic', pos=dpos)
        anim.bind(on_complete=self._on_animation_complete_hide)
        anim.start(self.layout)
        Animation(d=self.duration, t='out_cubic', pos=cpos).start(self.corner)

    def place(self, noop=None):
        self.need_reposition = True
        self.update(noop)
        
    def update(self, noop=None):
        w = self.get_parent_window()
        side = self.side
        align = self.align

        # first execution, need to place layout in the good size
        if self.need_reposition:
            dpos = self._get_position_for(self.visible)
            if dpos is not None:
              self.layout.pos = dpos
              self.corner.pos = self._get_corner_position_for(self.visible)
              self.need_reposition = False
              if self.visible:
                self.show()
              else:
                self.hide()
            else:
              return
                      
    def on_move(self, x, y):
        self.initial_pos = x, y
        self.layout.pos  = x, y

    def on_touch_down(self, touch):
        if self.corner.on_touch_down(touch):
            return True
        return super(SidePanel, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.corner.on_touch_move(touch):
            return True
        return super(SidePanel, self).on_touch_move(touch)

    def on_touch_up(self, touch):
        if self.corner.on_touch_up(touch):
            return True
        return super(SidePanel, self).on_touch_up(touch)
