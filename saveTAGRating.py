# -*- coding: utf8 -*-
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.
#
#       This is based on saveTAGCover plugin write by (Copyright (C) 2010 Jeronimo Buencuerpo Fariña jerolata@gmail.com)
#       Matthieu Bosc (mbosc77@gmail.com)
#




import rhythmdb, rb
import gobject, gtk
from subprocess import Popen
from os import path
from urllib import url2pathname
import pynotify

ui_str = """
<ui>
  <popup name="BrowserSourceViewPopup">
    <placeholder name="PluginPlaceholder">
      <menuitem name="saveTAGRatingPopup" action="saveTAGRating"/>
    </placeholder>
  </popup>

  <popup name="PlaylistViewPopup">
    <placeholder name="PluginPlaceholder">
      <menuitem name="saveTAGRatingPopup" action="saveTAGRating"/>
    </placeholder>
  </popup>

  <popup name="QueuePlaylistViewPopup">
    <placeholder name="PluginPlaceholder">
      <menuitem name="saveTAGRatingPopup" action="saveTAGRating"/>
    </placeholder>
  </popup>
</ui>
"""

class saveTAGRating(rb.Plugin):

    def __init__(self):
        rb.Plugin.__init__(self)
            
    def activate(self, shell):
        self.action = gtk.Action('saveTAGRating', _('Synchronize rating with file'),
                     _('Synchronize rating with file'),
                     'saveTAGRating')
        self.activate_id = self.action.connect('activate', self.tidy_Rating, shell)
        
        self.action_group = gtk.ActionGroup('saveTAGRatingPluginActions')
        self.action_group.add_action(self.action)
        
        uim = shell.get_ui_manager ()
        uim.insert_action_group(self.action_group, 0)
        self.ui_id = uim.add_ui_from_string(ui_str)
        uim.ensure_update()
    def notificame(self, num_saved, num_already_done):
        pynotify.init('notify_user')
        if num_saved + num_already_done != 0 :
            imageURI = path.expanduser("~/.gnome2/rhythmbox/plugins/saveTAGRating_en/Cover.png")
            n = pynotify.Notification("%s synchronized" % (num_saved), "%s failed " % (num_already_done), imageURI)
            n.show()
        else:
            imageURI = path.expanduser("~/.gnome2/rhythmbox/plugins/saveTAGRating_en/NoCover.png")
            n = pynotify.Notification("¡Error! No Rating found", "Please add some Rating to the library", imageURI)
            n.show()
            
        
    def save_Rating_inside(self, pathSong, ratingValue, count):
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3, TXXX, POPM
        audio = ID3(pathSong)
#        if isinstance(audio, MP3):
        if (pathSong[-4:] == ".mp3") or (pathSong[-4:] == ".MP3"):  #for safety reutilization of the code
            audio.delall('POPM')
            audio.add(POPM(email=u"Banshee", rating=int(51 * ratingValue), count=count))
            print "saving"
            print int(51 * ratingValue)
#            rating = TXXX(encoding=3, desc=u"RATING", text=[u"%s" % ratingValue])
#            audio.add(rating)

            audio.save()
#        else:
#            audio["Rating"] = str(ratingValue)
#
            #mySong= MP3(pathSong)
            #hasRating = mySong.__str__()
            return True
                      
    def get_Rating(self, pathSong):
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3, TXXX, POPM
        if (pathSong[-4:] == ".mp3") or (pathSong[-4:] == ".MP3"):  #for safety reutilization of the code
            #mySong= ID3(pathSong)
            #hasRating = mySong.__str__()
        #print hasRating
        #print "teeeeest"
            audio = ID3(pathSong)
            if len(audio.getall('POPM')) != 0:
                rating = audio.getall('POPM')[0].rating
                print "real rating"
                print rating
		if (rating > 8 and rating < 50):
			print rating
			return 1;
		if (rating > 49 and rating < 114):
			return 2;
		if (rating > 113 and rating < 168):
			return 3;
		if (rating > 167 and rating < 219):
			return 4;
		if (rating > 218):
			return 5;
		return 0;		
            else:
                return 0
 
    def get_Count(self, pathSong):
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3, TXXX, POPM
        if (pathSong[-4:] == ".mp3") or (pathSong[-4:] == ".MP3"):  #for safety reutilization of the code
            #mySong= ID3(pathSong)
            #hasRating = mySong.__str__()
        #print hasRating
        #print "teeeeest"
            audio = ID3(pathSong)
            if len(audio.getall('POPM')) != 0:
		if hasattr(audio.getall('POPM')[0], 'count'):
	                count = audio.getall('POPM')[0].count or 0
	                return count
		else:
			return 0
#            if len(audio.getall(u'TXXX:RATING')) != 0:
#                rating = audio[u'TXXX:RATING'].text[0].__str__()
#                return int(rating[:1])
            else:
                return 0
      
    def tidy_Rating(self, action, shell):
        source = shell.get_property("selected_source")
        print source
        entry = rb.Source.get_entry_view(source)
        selected = entry.get_selected_entries()
        num_saved = 0
        num_already_done = 0
        if selected != []:
            errors = False
            for element in selected:
                db = shell.get_property("db")
        		#rating = db.get ("rating", -1.0)
                rating = shell.props.db.entry_get(element, rhythmdb.PROP_RATING)
                count = shell.props.db.entry_get(element, rhythmdb.PROP_PLAY_COUNT)
                uri = element.get_playback_uri()
                dirpath = uri.rpartition('/')[0]
                uri_normalizado = url2pathname(dirpath.replace("file://", ""))
                path_normalizado = url2pathname(uri.replace("file://", ""))
                print "BEFORE DECISION"
                if rating == 0:
                            rating = self.get_Rating(path_normalizado)
                            print "rating lu"
                            print rating
                            count = self.get_Count(path_normalizado)
                            shell.props.db.set(element, rhythmdb.PROP_RATING, rating)
                            shell.props.db.set(element, rhythmdb.PROP_PLAY_COUNT, count)
                            shell.props.db.commit()
                            num_saved = num_saved + 1
                else:
                            if self.save_Rating_inside(path_normalizado, rating, count):
                                num_saved = num_saved + 1
                            else:
                                num_already_done = num_already_done + 1
        if errors == False :
                self.notificame(num_saved, num_already_done)
        elif num_saved + num_already_done > 0:
                self.notificame(num_saved, num_already_done)
    
    def deactivate(self, shell):
        uim = shell.get_ui_manager()
        self.action_group = None
        uim.remove_ui (self.ui_id)
        uim.remove_action_group (self.action_group)

        self.action = None
