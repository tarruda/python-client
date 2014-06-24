# This file is a basic example of how one can build a custom UI for neovim. It
# uses python Tkinter module which is distributed with python

import sys, neovim, pprint
from Tkinter import *
import tkFont
from threading import Thread
from collections import deque
# import cProfile, pstats, StringIO



class NvimTkUI(object):
    def __init__(self, address):
        self.address = address
        # keep a variable to reference to the top-level frame to destroy when
        # layout changes
        self.toplevel = None
        # windows_id -> text widget map
        self.windows = None
        # pending nvim events
        self.nvim_events = deque()

    def on_tk_select(self, arg):
        arg.widget.tag_remove('sel', '1.0', 'end')
        # TODO: this should change nvim visual range

    def on_nvim_event(self, arg):
        def handle(event):
            event_type = event.name[7:]
            event_arg = event.arg
            handler = getattr(self, 'on_nvim_' + event_type)
            handler(event_arg)

        ev = self.nvim_events.popleft()
        if hasattr(ev, 'name'):
            handle(ev)
        else:
            for e in ev:
                handle(e)

    def on_nvim_exit(self, arg):
        self.root.destroy()

    def on_nvim_layout(self, arg):
        windows = {}
        # Recursion helper to build a tk frame graph from data received with
        # the layout event
        def build_widget_graph(parent, node, arrange='row'):
            widget = None
            if node['type'] in ['row', 'column']:
                widget = Frame(parent)
            else:
                widget = Text(parent, width=node['width'],
                              height=node['height'], state='normal',
                              font=self.font, exportselection=False,
                              fg=self.fg_color, bg=self.bg_color,
                              wrap='none', undo=False)
                setattr(widget, 'added_tags', {})
                # fill the widget one linefeed per row to simplify updating
                widget.insert('1.0', '\n' * node['height'])
                # We don't want the user to edit
                widget['state'] = 'disabled'
                windows[node['window_id']] = widget
            if 'children' in node:
                for child in node['children']:
                    build_widget_graph(widget, child, arrange=node['type'])
            if arrange == 'row':
                widget.pack(side=LEFT, anchor=NW)
            else:
                widget.pack(side=TOP, anchor=NW)
        
        # build the new toplevel frame
        toplevel = Frame(self.root, takefocus=True)
        build_widget_graph(toplevel, arg)
        # destroy the existing one if exists
        if self.toplevel:
            self.toplevel.destroy()
        self.windows = windows
        # save a reference for future removal when the layout changes again
        self.toplevel = toplevel
        # display the frame 
        self.toplevel.pack()

    def on_nvim_foreground_color(self, arg):
        self.fg_color = arg['color']

    def on_nvim_background_color(self, arg):
        self.bg_color = arg['color']

    def on_nvim_insert_line(self, arg):
        widget = self.windows[arg['window_id']]
        line = arg['row'] + 1
        count = arg['count']
        startpos = '%d.0' % line
        widget['state'] = 'normal'
        # insert
        widget.insert(startpos, arg['count'] * '\n')
        # delete at the end
        widget.delete('end - %d lines' % count, 'end')
        widget['state'] = 'disabled'

    def on_nvim_delete_line(self, arg):
        widget = self.windows[arg['window_id']]
        line = arg['row'] + 1
        count = arg['count']
        startpos = '%d.0' % line
        endpos = '%d.0' % (line + count)
        widget['state'] = 'normal'
        # delete
        widget.delete(startpos, endpos)
        # insert at the end(they will be updated soon
        widget.insert('end', '\n' * count)
        widget['state'] = 'disabled'

    def on_nvim_win_end(self, arg):
        widget = self.windows[arg['window_id']]
        line = arg['row'] + 1
        endline = arg['endrow'] + 1
        marker = arg['marker']
        fill = arg['fill']
        startpos = '%d.0' % line
        endpos = '%d.0' % endline
        widget['state'] = 'normal'
        # delete
        widget.delete(startpos, endpos)
        line_fill = '%s%s\n' % (marker, fill * (widget['width'] - 1))
        # insert markers/fillers
        widget.insert('end', line_fill * (endline - line))
        widget['state'] = 'disabled'

    def on_nvim_update_line(self, arg):
        widget = self.windows[arg['window_id']]
        contents = ''.join(map(lambda c: c['content'], arg['line']))
        line = arg['row'] + 1
        startpos = '%d.0' % line
        endpos = '%d.end' % line
        widget['state'] = 'normal'
        widget.delete(startpos, endpos)
        widget.insert(startpos, contents)
        widget['state'] = 'disabled'
        if 'attributes' in arg:
            for name, positions in arg['attributes'].items():
                for position in positions:
                    self.apply_attribute(widget, name, line, position)

    def apply_attribute(self, widget, name, line, position):
        # Ensure the attribute name is associated with a tag configured with
        # the corresponding attribute format
        if name not in widget.added_tags:
            prefix = name[0:2]
            if prefix in ['fg', 'bg']:
                color = name[3:]
                if prefix == 'fg':
                    widget.tag_configure(name, foreground=color)
                else:
                    widget.tag_configure(name, background=color)
            widget.added_tags[name] = True
        # Now clear occurences of the tags in the current line
        ranges = widget.tag_ranges(name)
        for i in range(0, len(ranges), 2):
            start = ranges[i]
            stop = ranges[i+1]
            widget.tag_remove(start, stop)
        if isinstance(position, list):
            start = '%d.%d' % (line, position[0])
            end = '%d.%d' % (line, position[1])
            widget.tag_add(name, start, end)
        else:
            pos = '%d.%d' % (line, position)
            widget.tag_add(name, pos)

    def run(self):
        def get_nvim_events(queue, vim, root):
            # Send the screen to ourselves
            vim.request_screen()
            buffered = None
            while True:
                try:
                    message = vim.next_message()
                except IOError:
                    root.event_generate('<<nvim_exit>>', when='tail')
                    break
                event_type = message.name
                if event_type == 'redraw:start':
                    buffered = []
                elif event_type == 'redraw:end':
                    queue.append(buffered)
                    buffered = None
                    root.event_generate('<<nvim>>', when='tail')
                else:
                    if buffered is None:
                        # handle non-buffered events
                        queue.append(message)
                        root.event_generate('<<nvim>>', when='tail')
                    else:
                        buffered.append(message)
        # Setup the root window
        self.root = Tk()
        self.root.bind('<<nvim>>', self.on_nvim_event.__get__(self, NvimTkUI))
        self.root.bind('<<nvim_exit>>', self.on_nvim_exit.__get__(self, NvimTkUI))
        self.root.bind('<<Selection>>', self.on_tk_select)
        # setup font
        self.font = tkFont.Font(family='Monospace', size=13)
        # setup nvim connection
        self.vim = neovim.connect(self.address)
        # Subscribe to all redraw events
        # self.vim.subscribe('redraw:tabs')
        self.vim.subscribe('redraw:start')
        self.vim.subscribe('redraw:end')
        self.vim.subscribe('redraw:insert_line')
        self.vim.subscribe('redraw:delete_line')
        self.vim.subscribe('redraw:win_end')
        self.vim.subscribe('redraw:update_line')
        # self.vim.subscribe('redraw:status_line')
        # self.vim.subscribe('redraw:ruler')
        self.vim.subscribe('redraw:layout')
        self.vim.subscribe('redraw:background_color')
        self.vim.subscribe('redraw:foreground_color')
        # self.vim.subscribe('redraw:cursor')
        # Start a thread for receiving nvim events
        t = Thread(target=get_nvim_events, args=(self.nvim_events,
                                                 self.vim,
                                                 self.root,))
        t.daemon = True
        t.start()
        # Start handling tk events
        self.root.mainloop()

if len(sys.argv) < 2:
    print >> sys.stderr, 'Need neovim listen address as argument'

address = sys.argv[1]
ui = NvimTkUI(address)
# pr = cProfile.Profile()
# pr.enable()
try:
    ui.run()
except IOError:
    print >> sys.stderr, 'Cannot connect to %s' % address
    sys.exit(1)
# pr.disable()
# s = StringIO.StringIO()
# ps = pstats.Stats(pr, stream=s)
# ps.strip_dirs().sort_stats('tottime').print_stats(10)
# print s.getvalue()
