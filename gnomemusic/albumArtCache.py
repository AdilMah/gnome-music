# Copyright (c) 2013 Vadim Rutkovsky <vrutkovs@redhat.com>
# Copyright (c) 2013 Arnel A. Borja <kyoushuu@yahoo.com>
# Copyright (c) 2013 Seif Lotfy <seif@lotfy.com>
# Copyright (c) 2013 Guillaume Quintard <guillaume.quintard@gmail.com>
# Copyright (c) 2013 Lubosz Sarnecki <lubosz@gmail.com>
# Copyright (c) 2013 Sai Suman Prayaga <suman.sai14@gmail.com>
#
# GNOME Music is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# GNOME Music is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with GNOME Music; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# The GNOME Music authors hereby grant permission for non-GPL compatible
# GStreamer plugins to be used and distributed together with GStreamer
# and GNOME Music.  This permission is above and beyond the permissions
# granted by the GPL license by which GNOME Music is covered.  If you
# modify this code, you may extend this exception to your version of the
# code, but you are not obligated to do so.  If you do not wish to do so,
# delete this exception statement from your version.


from gi.repository import Gtk, GdkPixbuf, Gio, GLib, Gdk, MediaArt
from gettext import gettext as _
import cairo
from math import pi
import os
from _thread import start_new_thread
from gnomemusic import log
from gnomemusic.grilo import grilo
import logging
logger = logging.getLogger(__name__)


@log
def _make_icon_frame(pixbuf, path=None):
    border = 1.5
    degrees = pi / 180
    radius = 3

    w = pixbuf.get_width()
    h = pixbuf.get_height()
    new_pixbuf = pixbuf.scale_simple(w - border * 2,
                                     h - border * 2,
                                     0)

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surface)
    ctx.new_sub_path()
    ctx.arc(w - radius, radius, radius - 0.5, -90 * degrees, 0 * degrees)
    ctx.arc(w - radius, h - radius, radius - 0.5, 0 * degrees, 90 * degrees)
    ctx.arc(radius, h - radius, radius - 0.5, 90 * degrees, 180 * degrees)
    ctx.arc(radius, radius, radius - 0.5, 180 * degrees, 270 * degrees)
    ctx.close_path()
    ctx.set_line_width(0.6)
    ctx.set_source_rgb(0.2, 0.2, 0.2)
    ctx.stroke_preserve()
    ctx.set_source_rgb(1, 1, 1)
    ctx.fill()
    border_pixbuf = Gdk.pixbuf_get_from_surface(surface, 0, 0, w, h)

    new_pixbuf.copy_area(border, border,
                         w - border * 4,
                         h - border * 4,
                         border_pixbuf,
                         border * 2, border * 2)
    return border_pixbuf


class AlbumArtCache:
    instance = None

    @classmethod
    def get_default(self):
        if not self.instance:
            self.instance = AlbumArtCache()
        return self.instance

    @classmethod
    def get_media_title(self, media, escaped=False):
        title = media.get_title()
        if title:
            if escaped:
                return GLib.markup_escape_text(title)
            else:
                return title
        uri = media.get_url()
        if uri is None:
            return _("Untitled")

        uri_file = Gio.File.new_for_path(uri)
        basename = uri_file.get_basename()

        try:
            title = GLib.uri_unescape_string(basename, '')
        except:
            title = _("Untitled")
            pass
        if escaped:
            return GLib.markup_escape_text(title)

        return title

    @log
    def __init__(self):
        try:
            self.cacheDir = os.path.join(GLib.get_user_cache_dir(), 'media-art')
            Gio.file_new_for_path(self.cacheDir).make_directory(None)
        except:
            pass

    @log
    def get_default_icon(self, width, height):
        # get a small pixbuf with the given path
        icon = Gtk.IconTheme.get_default().load_icon('folder-music-symbolic', max(width, height) / 4, 0)

        # create an empty pixbuf with the requested size
        result = GdkPixbuf.Pixbuf.new(icon.get_colorspace(),
                                      True,
                                      icon.get_bits_per_sample(),
                                      icon.get_width() * 4,
                                      icon.get_height() * 4)
        result.fill(0xffffffff)
        icon.composite(result,
                       icon.get_width() * 3 / 2,
                       icon.get_height() * 3 / 2,
                       icon.get_width(),
                       icon.get_height(),
                       icon.get_width() * 3 / 2,
                       icon.get_height() * 3 / 2,
                       1, 1,
                       GdkPixbuf.InterpType.NEAREST, 0xff)
        return _make_icon_frame(result)

    @log
    def lookup(self, item, width, height, callback, itr, artist, album):
        start_new_thread(self.lookup_worker, (item, width, height, callback, itr, artist, album))

    @log
    def lookup_worker(self, item, width, height, callback, itr, artist, album):
        try:
            width = width or -1
            height = height or -1
            path = MediaArt.get_path(artist, album, "album", None)[0]
            if not os.path.exists(path):
                self.cached_thumb_not_found(item, width, height, callback, itr, artist, album, path)
            else:
                self.read_cached_pixbuf(path, width, height, callback, itr)
        except Exception as e:
            logger.warn("Error: %s" % e)

    @log
    def read_cached_pixbuf(self, path, width, height, callback, itr):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, width, height, True)
            self.finish(_make_icon_frame(pixbuf), path, callback, itr)
        except Exception as e:
            logger.debug("Error: %s" % e)

    @log
    def finish(self, pixbuf, path, callback, itr):
        try:
            GLib.idle_add(callback, pixbuf, path, itr)
        except Exception as e:
            logger.warn("Error: %s" % e)

    @log
    def cached_thumb_not_found(self, item, width, height, callback, itr, artist, album, path):
        try:
            uri = item.get_thumbnail()
            if uri is None:
                new_item = grilo.get_album_art_for_album_id(item.get_id())[0]
                uri = new_item.get_thumbnail()
                if uri is None:
                    logger.warn("can't find URL for album '%s' by %s" % (album, artist))
                    self.finish(None, path, callback, itr)
                    return

            data = [item, width, height, callback, itr, artist, album, path, uri]
            if item.get_url() is None:
                # No URL, probably an album. Get a single song.
                grilo.populate_album_songs(item.get_id(), self._on_album_item_found, 1, data)
            else:
                self.process_media_art(data)
        except Exception as e:
            logger.warn("Error: %s" % e)

    @log
    def _on_album_item_found(self, source, param, item, remaining, data):
        try:
            item_album, width, height, callback, itr, artist, album, path, uri = data
            data[0] = item
            self.process_media_art(data)
        except Exception as e:
            logger.warn("Error: %s" % e)

    @log
    def process_media_art(self, data):
        try:
            item, width, height, callback, itr, artist, album, path, uri = data
            f = Gio.File.new_for_uri(uri)
            success, contents, etag = f.load_contents(None)
            streamInfo = f.query_info('standard::content-type', Gio.FileQueryInfoFlags.NONE, None)
            contentType = streamInfo.get_content_type()

            MediaArt.process(contents, contentType, MediaArt.Type.ALBUM,
                             artist, album, item.get_url())
            self.read_cached_pixbuf(path, width, height, callback, itr)
        except Exception as e:
            logger.warn("Error: %s" % e)
