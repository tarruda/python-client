"""Neovim TKinter UI."""
from Tkinter import Canvas, Tk

from tkFont import Font

from ..compat import IS_PYTHON3


__all__ = ('NvimTk',)


SPECIAL_KEYS = {
    'Escape': 'Esc',
    'Return': 'CR',
    'BackSpace': 'BS',
    'Prior': 'PageUp',
    'Next': 'PageDown',
    'Delete': 'Del',
}


if not IS_PYTHON3:
    range = xrange


class NvimTk(object):

    """Wraps all nvim/tk event handling."""

    def __init__(self, nvim):
        """Initialize with a Nvim instance."""
        self._nvim = nvim
        self._attrs = {}
        self._canvas = None
        self._handle_resize = False
        self._fg = '#000000'
        self._bg = '#ffffff'

    def run(self):
        """Start the UI."""
        self._root = Tk()
        self._root.bind('<Key>', self._tk_key)
        self._root.bind('<Configure>', self._tk_configure)
        self._root.protocol("WM_DELETE_WINDOW",
                            lambda: self._nvim.session.stop())

        def setup_cb():
            self._nvim.ui_attach(80, 24)
            self._nvim.session.schedule(lambda: self._root.update(), 50, True)

        self._nvim.session.run(self._nvim_request,
                               self._nvim_notification,
                               setup_cb)

    def _nvim_request(self, method, args):
        raise Exception('This UI does not implement any methods')

    def _nvim_notification(self, method, args):
        if method == 'redraw':
            self._tk_nvim_redraw(args)

    def _tk_nvim_redraw(self, updates):
        for update in updates:
            handler = getattr(self, '_tk_nvim_' + update[0])
            for args in update[1:]:
                handler(*args)
        self._root.update_idletasks()

    def _tk_nvim_detach(self, *args):
        self._root.destroy()

    def _tk_nvim_resize(self, width, height):
        self._tk_redraw_canvas(width, height)

    def _tk_nvim_clear(self):
        self._tk_clear_region(0, self._height - 1, 0, self._width - 1)

    def _tk_nvim_eol_clear(self):
        row, col = (self._cursor_row, self._cursor_col,)
        self._tk_clear_region(row, row, col, self._scroll_right)

    def _tk_nvim_cursor_goto(self, row, col):
        self._cursor_row = row
        self._cursor_col = col

    def _tk_nvim_cursor_on(self):
        pass

    def _tk_nvim_cursor_off(self):
        pass

    def _tk_nvim_mouse_on(self):
        pass

    def _tk_nvim_mouse_off(self):
        pass

    def _tk_nvim_insert_mode(self):
        pass

    def _tk_nvim_normal_mode(self):
        pass

    def _tk_nvim_set_scroll_region(self, top, bot, left, right):
        self._scroll_top = top
        self._scroll_bot = bot
        self._scroll_left = left
        self._scroll_right = right

    def _tk_nvim_scroll(self, count):
        top, bot = (self._scroll_top, self._scroll_bot,)
        left, right = (self._scroll_left, self._scroll_right,)
        # We'll perform operations in various regions. The first step is to
        # determine the affected regions, which depends on the scroll direction
        #
        # - The moved region is the scroll region minus anything that would be
        #   left out of the scroll region after the move
        # - The destroyed region is where part of the moved region will go
        #   to. It is destroyed before the move.
        # - The fill region is where the moved region left empty. It is
        #   filled after the move
        if count > 0:
            destroy_top = top
            destroy_bot = top + count - 1
            move_top = destroy_bot + 1
            move_bot = bot
            fill_top = bot - count + 1
            fill_bot = bot
            shift_start = top
            shift_stop = bot - count + 1
            shift_step = 1
        else:
            destroy_top = bot + count + 1
            destroy_bot = bot
            move_top = top
            move_bot = destroy_top - 1
            fill_top = top
            fill_bot = top - count - 1
            shift_start = bot
            shift_stop = top - count - 1
            shift_step = -1
        # shift cell index
        for rownum in range(shift_start, shift_stop, shift_step):
            target_row = self._index[rownum]
            source_row = self._index[rownum + count]
            for colnum in range(left, right + 1):
                target_row[colnum] = source_row[colnum]
        # destroy items in a region that will be occupied by the moved items
        self._tk_destroy_region(destroy_top, destroy_bot, left, right)
        # tag all items in the region to me moved and perform the move
        self._tk_tag_region('move', move_top, move_bot, left, right)
        self._canvas.move('move', 0, -count * self._rowsize)
        self._canvas.dtag('move', 'move')
        # fill the region left empty with new items
        self._tk_fill_region(fill_top, fill_bot, left, right)

    def _tk_nvim_highlight_set(self, attrs):
        self._attrs = attrs

    def _tk_nvim_put(self, data):
        # choose a Font instance
        font = self._fnormal
        if self._attrs.get('bold', False):
            font = self._fbold
        if self._attrs.get('italic', False):
            font = self._fbolditalic if font == self._fbold else self._fitalic
        # colors
        fg = "#{0:0{1}x}".format(self._attrs.get('foreground', self._fg), 6)
        bg = "#{0:0{1}x}".format(self._attrs.get('background', self._bg), 6)
        # get the "text" and "rect" which correspond to the current cell
        rect, text = self._index[self._cursor_row][self._cursor_col]
        # update properties
        self._canvas.itemconfig(text, fill=fg, font=font, text=data or ' ')
        self._canvas.itemconfig(rect, fill=bg)
        # update cursor
        self._tk_nvim_cursor_goto(self._cursor_row, self._cursor_col + 1)

    def _tk_nvim_bell(self):
        self._root.bell()

    def _tk_nvim_update_fg(self, fg):
        self._fg = "#{0:0{1}x}".format(fg, 6)

    def _tk_nvim_update_bg(self, bg):
        self._bg = "#{0:0{1}x}".format(bg, 6)

    def _tk_setup_fonts(self, size):
        self._fnormal = Font(family='Monospace', size=size)
        self._fbold = Font(family='Monospace', weight='bold', size=size)
        self._fitalic = Font(family='Monospace', slant='italic', size=size)
        self._fbolditalic = Font(family='Monospace', weight='bold',
                                 slant='italic', size=size)
        self._colsize = self._fnormal.measure('A')
        self._rowsize = self._fnormal.metrics('linespace')

    def _tk_redraw_canvas(self, width, height):
        if self._canvas:
            self._canvas.destroy()
        self._tk_setup_fonts(13)
        self._canvas = Canvas(self._root, width=self._colsize * width,
                              height=self._rowsize * height)
        # To make finding rows and columns fast, we store their ids in a index
        self._index = [[None for j in range(width)] for i in range(height)]
        self._tk_fill_region(0, height - 1, 0, width - 1)
        self._cursor_row = 0
        self._cursor_col = 0
        self._scroll_top = 0
        self._scroll_bot = height - 1
        self._scroll_left = 0
        self._scroll_right = width - 1
        self._width, self._height = (width, height,)
        self._canvas.pack()
        self._handle_resize = True

    def _tk_fill_region(self, top, bot, left, right):
        # Create cells in the bot->top/right->left order, which will make cells
        # with higher indexes have lower z-indexes. This is required for
        # properly displaying characters that cross cell boundaries
        for rownum in range(bot, top - 1, -1):
            row = self._index[rownum]
            for colnum in range(right, left - 1, -1):
                x1 = colnum * self._colsize
                y1 = rownum * self._rowsize
                x2 = (colnum + 1) * self._colsize
                y2 = (rownum + 1) * self._rowsize
                # for each cell, create two items:
                #  - The rectangle for cell background
                #  - The text for cell contents and formatting
                rect = self._canvas.create_rectangle(x1, y1, x2, y2,
                                                     fill=self._bg, width=0)
                text = self._canvas.create_text(x1, y1, anchor='nw',
                                                font=self._fnormal, width=1,
                                                fill=self._fg, text=' ')
                # update the index
                row[colnum] = (rect, text,)

    def _tk_clear_region(self, top, bot, left, right):
        self._tk_tag_region('clear', top, bot, left, right)
        self._canvas.itemconfig('clear', fill=self._bg)
        self._canvas.dtag('clear', 'clear')

    def _tk_destroy_region(self, top, bot, left, right):
        self._tk_tag_region('destroy', top, bot, left, right)
        self._canvas.delete('destroy')
        self._canvas.dtag('destroy', 'destroy')

    def _tk_tag_region(self, tag, top, bot, left, right):
        x1, y1 = self._tk_get_coords(top, left)
        x2, y2 = self._tk_get_coords(bot, right)
        self._canvas.addtag_overlapping(tag, x1, y1, x2 + 1, y2 + 1)

    def _tk_get_coords(self, row, col):
        x = col * self._colsize
        y = row * self._rowsize
        return x, y

    def _tk_key(self, event):
        if 0xffe1 <= event.keysym_num <= 0xffee:
            # this is a modifier key, ignore. Source:
            # https://www.tcl.tk/man/tcl8.4/TkCmd/keysyms.htm
            return
        # Translate to Nvim representation of keys
        send = []
        if event.state & 0x1:
            send.append('S')
        if event.state & 0x4:
            send.append('C')
        if event.state & (0x8 | 0x80):
            send.append('A')
        special = len(send) > 0
        key = event.char
        if _is_invalid_key(key):
            special = True
            key = event.keysym
        send.append(SPECIAL_KEYS.get(key, key))
        send = '-'.join(send)
        if special:
            send = '<' + send + '>'
        nvim = self._nvim
        nvim.session.schedule(lambda: nvim.input(send))

    def _tk_configure(self, event):
        if not self._handle_resize:
            return
        width = event.width / self._colsize
        height = event.height / self._rowsize
        if self._width == width and self._height == height:
            return
        nvim = self._nvim
        nvim.session.schedule(lambda: nvim.ui_try_resize(width, height))


def _is_invalid_key(c):
    try:
        return len(c.decode('utf-8')) != 1 or ord(c[0]) < 0x20
    except UnicodeDecodeError:
        return True
