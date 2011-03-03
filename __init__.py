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
#       This is based on saveTAGCover plugin written by (Copyright (C) 2010 Jeronimo Buencuerpo Farina jerolata@gmail.com)
#       Matthieu Bosc (mbosc77@gmail.com)
#       Vysserk3  (vysserk3@gmail.com)
#
# Specs for tagging file : 
# http://www.freedesktop.org/wiki/Specifications/free-media-player-specs

from mutagen.flac import FLAC
from mutagen.id3 import ID3, POPM, PCNT, TXXX
from mutagen.mp4 import MP4
from mutagen.musepack import Musepack
from mutagen.oggspeex import OggSpeex
from mutagen.oggvorbis import OggVorbis
from saveTAGRatingConfigureDialog import saveTAGRatingConfigureDialog
from time import time
from urllib import url2pathname
import gconf
import gettext
import gobject
import gtk
import gtk.glade
try:
    import pynotify
    usepynotify = True
except ImportError:
    usepynotify = False
        
import rb
import rhythmdb
import sys


# Setup our own gettext locale domain (else, we should add our translation file inside rhythmbox sources)
t = gettext.translation('messages', sys.path[0] + "/locale")
_ = t.ugettext


# Some gconf keys to store user settings...
# autosaveenabled : if enabled, each time a database property is changed (rating or playcount), the change
# are automatically saved to the file
# ratingsenabled : if enabled, support rating save/restore/clean/autosave
# playcountsenabled : if enabled, support playcount save/restore/clean/autosave

gconf_keys = {'autosaveenabled' : '/apps/rhythmbox/plugins/saveTAGRating/autosave_enabled'
              , 'ratingsenabled' : '/apps/rhythmbox/plugins/saveTAGRating/ratings_enabled'
              , 'playcountsenabled':'/apps/rhythmbox/plugins/saveTAGRating/playcounts_enabled'
              }


class saveTAGRating(rb.Plugin):

    def __init__(self):
        rb.Plugin.__init__(self)
        

    def activate(self, shell):
        """ Activation method, initialization phase """
        # Store the shell
        self.shell = shell
        
        # Retrieve some gconf values
        self.autosaveenabled = gconf.client_get_default().get_bool(gconf_keys['autosaveenabled'])
        self.ratingsenabled = gconf.client_get_default().get_bool(gconf_keys['ratingsenabled'])
        self.playcountsenabled = gconf.client_get_default().get_bool(gconf_keys['playcountsenabled'])
        
        # Create stock id for icons (save,restore, clean)
        iconfactory = gtk.IconFactory()
        #stock_ids = gtk.stock_list_ids()
        for stock_id, file in [('save_rating_playcount', 'save.png'),
                               ('restore_rating_playcount', 'restore.png'),
                               ('clean_alltags', 'clean.png')]:
            # only load image files when our stock_id is not present
            #if stock_id not in stock_ids:
            iconset = gtk.IconSet(gtk.gdk.pixbuf_new_from_file(self.find_file(file)))
            iconfactory.add(stock_id, iconset)
        iconfactory.add_default()
        
        
        # Setup gtk.Action (for the right-click menu) (see method definition below)
        self.setup_gtkactions(shell)
        
        
        # Setup statusbar and progressbar
        player = shell.get_player()
        self.statusbar = player.get_property("statusbar")
        # Is there a better way to get access to it ???
        self.progressbar = self.statusbar.get_children()[1]
        
        # Store a reference to the db
        self.db = shell.props.db
            
#        entry_type = MyEntryType()
#        self.db.register_entry_type(entry_type)
#        self.mysource = gobject.new (MySource, shell=shell, name=_("My Source"), entry_type=entry_type)
#        group = rb.rb_display_page_group_get_by_id ("shared")
#        shell.append_display_page (self.mysource, group)
#        shell.register_entry_type_for_source(self.mysource, entry_type)
        
        
        # If autosave is enabled, each time an entry is changed call the given method
        if self.autosaveenabled:
            self.entrychanged_sig_id = self.db.connect('entry-changed', self._on_entry_change)

        # Variable to store processing stats
        self.num_saved = 0
        self.num_failed = 0
        self.num_restored = 0
        self.num_already_done = 0
        self.num_cleaned = 0
        
        # Index of the current selected item
        self.iel = 0
        
        # Start time
        self.t0 = 0
        
        print("Plugin activated")
        

    def create_configure_dialog(self, dialog=None):
        """ Create a configuration dialog for the plugin """
        if not dialog:
            # Use the ui glade interface file
            builder_file = self.find_file("savetagrating-prefs.ui")
            # Create the saveTAGRatingConfigureDialog object
            dialog = saveTAGRatingConfigureDialog(builder_file, gconf_keys, self).get_dialog()
        
        dialog.present()
        
        return dialog
    
            
    def deactivate(self, shell):
        """ Dereference any fields that has been initialized in activate"""
        if self.create_gtkAction:
            self.uim.remove_ui (self.ui_id)
            del self.ui_id
            self.uim.remove_action_group (self.action_group)
            del self.uim
            del self.action_group
            del self.action
            del self.action2
            del self.action3
        del self.create_gtkAction
        del self.statusbar
        del self.progressbar
        del self.num_saved
        del self.num_failed
        del self.num_restored
        del self.num_already_done
        del self.num_cleaned
        del self.iel
        del self.t0
        if self.autosaveenabled:
            self.db.disconnect(self.entrychanged_sig_id)
            del self.entrychanged_sig_id
        del self.db
        print("Plugin deactivated")





    def setup_gtkactions(self, shell):
        """ Method to be called to create gtk.Action and menu entries 
        AND to update existing menu (meaning, it can be called several times during plugin runtime) 
        That's why we need to "clean" any existing menu ui before...
        """
        
        
        # Clean previous ui (if any)
        if "uim" in dir(self):
                self.uim.remove_ui(self.ui_id)
                self.uim.ensure_update()
                
        # If both rating support and playcount support are enabled...
        if self.ratingsenabled and self.playcountsenabled:
            savetext = _('Save rating and playcount to file')
            restoretext = _('Restore rating and playcount from file')
            cleantext = _('Remove rating and playcount tags')
            self.create_gtkAction = True
        
        else:
            # If only rating support is enabled...
            if self.ratingsenabled:
                savetext = _('Save rating to file')
                restoretext = _('Restore rating from file')
                cleantext = _('Remove rating tag')
                self.create_gtkAction = True
            # If only playcount support is enabled...
            elif self.playcountsenabled:
                savetext = _('Save playcount to file')
                restoretext = _('Restore playcount from file')
                cleantext = _('Remove playcount tag')
                self.create_gtkAction = True
            else:
                # Nothing is enabled, we don't need to create gtk.Action
                self.create_gtkAction = False
        
        
        
        if self.create_gtkAction:
            # Create three gtkAction
            
            # One to save to file
            self.action = gtk.Action('savetofile', #name 
                                     savetext, #label
                                     savetext, #tooltip
                                     'save_rating_playcount' # icon
                                     )
            # One to restore from file
            self.action2 = gtk.Action('restorefromfile', #name 
                                     restoretext, #label
                                     restoretext, #tooltip
                                     'restore_rating_playcount' # icon
                                     )
            
            # One to clean all tag (POPM,PCNT, TXXX, FMPS, etc...)
            self.action3 = gtk.Action('cleanalltags', #name 
                                     cleantext, #label
                                     cleantext, #tooltip
                                     'clean_alltags' # icon
                                     )
            
            # Define callback methods on these actions
            self.action.connect('activate', self.executedoActionOnSelected, self.saveRhythmDBToFile, shell)       
            self.action2.connect('activate', self.executedoActionOnSelected, self.restoreRhythmDBFromFile, shell)
            self.action3.connect('activate', self.executedoActionOnSelected, self.cleanAllTags, shell)
            

            # Create a group of actions, add the previously defined actions to it, and insert it to the ui manager
            self.action_group = gtk.ActionGroup('saveTAGRatingPluginActions')
            self.action_group.add_action(self.action)
            self.action_group.add_action(self.action2)
            self.action_group.add_action(self.action3)
            self.uim = shell.get_ui_manager ()
            self.uim.insert_action_group(self.action_group, 0)
            
            # Load the ui structure from the xml file
            self.ui_id = self.uim.add_ui_from_file(self.find_file("saveratings_ui.xml"))
            
            # Refresh user interface
            self.uim.ensure_update()


               
      
      


    def executedoActionOnSelected(self, action, doaction, shell):
        """ Function to apply doaction method on each element that has been selected """        
        # Get a rb.Source instance of the selected page
        try:
            source = shell.get_property("selected_source")
        except TypeError:
            source = shell.get_property("selected_page")
        
        # Push a message in the statusbar
        self.statusbar.push(1111, _("Processing..."))
        
        # Initiate progress bar at 0
        self.progressbar.set_fraction(0.0)
        
        # remove text if there is
        self.progressbar.set_text("")
        
        # Show the progress bar
        self.progressbar.set_visible(1)
        # Get an EntryView for the selected source (the track list)
        entryview = source.get_entry_view()
        # Get the list of selected entries from the track list
        selected = entryview.get_selected_entries()
        
        # Variables to store statistics
        #global num_saved, num_failed, num_restored, num_already_done, num_cleaned
        self.num_saved = 0
        self.num_failed = 0
        self.num_restored = 0 
        self.num_already_done = 0
        self.num_cleaned = 0
        
        # Variable to store the index of the current selected element
        # iel is set to 0 and will be increased during the loop of the idle callback 
        #global iel
        self.iel = 0
        
        # Store the start time before we start a long computation
        #global t0
        self.t0 = time()

        gobject.idle_add(self.idle_cb_loop_on_selected, # name of the callback  
                        selected, # additionnal parameters
                        self.db, #  --
                        doaction, # --
                        # named parameter to set an idle priority (background)
                        priority=gobject.PRIORITY_LOW) 
        
        
        
 
    
    def idle_cb_loop_on_selected(self, selected, db, doaction):
        """ Use chunked idle callbacks to perform IO operation in an asynchronous way
        See http://live.gnome.org/RhythmboxPlugins/WritingGuide#Using_idle_callbacks_for_repeated_tasks
        """
        gtk.gdk.threads_enter()
        finished = False
        
        # Count is used for chunked idle callbacks (to limit overhead of calling threads_enter())
        # maximum value to be properly defined (if N=size of the collection > N/2, N/3, N/4, N ????)
        count = 0
        
        # Selected elements list size
        selected_size = float(len(selected))
        
        while self.iel < selected_size and count < 5:
            element = selected[self.iel]
            uri = element.get_playback_uri()
            
            # Update progress bar advancement, for the moment, only updated every 5 songs due to count...
            self.progressbar.set_fraction(self.iel / selected_size)
            # Transform the URI into a standard UNIX path
            path_normalizado = url2pathname(uri[7:])
            
            # ...Execute the doaction function
            doaction(db, element, path_normalizado)
            count += 1
            self.iel += 1
            
        if self.iel < selected_size:
            gtk.gdk.threads_leave()
            # Computation is not over, still have work to do...
            return True


        gtk.gdk.threads_leave()
        # Computation is over....
        
        # Compute the total processing time (in seconds)
        t1 = time()
        totaltime = round(t1 - self.t0, 2)
        
        # Clear the message from the statusbar
        self.statusbar.pop(1111) 
        
        # remove progress bar and reset it to 0
        self.progressbar.set_visible(0)
        self.progressbar.set_fraction(0.0)

        # Notification at the end of process
        # Use pynotify if the import pynotify did not fail
        if usepynotify:
            pynotify.init('notify_user')
            pynotify.Notification(_("Status"),
                                  str(self.num_saved) + " " + _("saved") + "\n" + 
                                  str(self.num_restored) + " " + _("restored") + "\n" + 
                                  str(self.num_failed) + " " + _("failed") + "\n" + 
                                  str(self.num_already_done) + " " + _("already done") + "\n" + 
                                  str(self.num_cleaned) + " " + _("cleaned") + "\n" + 
                                  _("Total time : ") + str(totaltime) + " s"
                                  ).show()
        
        # In all the cases, use the status bar to print the stats
        self.statusbar.push(2222, str(self.num_saved) + " " + _("saved") + ", " + 
                                  str(self.num_restored) + " " + _("restored") + ", " + 
                                  str(self.num_failed) + " " + _("failed") + ", " + 
                                  str(self.num_already_done) + " " + _("already done") + ", " + 
                                  str(self.num_cleaned) + " " + _("cleaned") + ", " + 
                                  _("Total time : ") + str(totaltime) + " s")
        return False
        
    

        
    
    
    def _convert_ID3v2_rating_to_rhythmbdb_rating(self, rating):
        """ Function to convert ID3v2 POPM standard rating (from 0 to 255) to rhythmbox
        rating (from 0 to 5) """
        rhytm_rating = 0
        if (rating > 8 and rating < 52):
            rhytm_rating = 1
        if (rating > 51 and rating < 114):
            rhytm_rating = 2
        if (rating > 113 and rating < 168):
            rhytm_rating = 3
        if (rating > 167 and rating < 219):
            rhytm_rating = 4
        if (rating > 218):
            rhytm_rating = 5
        
        return rhytm_rating

    def _convert_fmps_rating_to_rhythmbdb_rating(self, rating):
        """ Function to convert FMPS standard rating (from 0.0 to 1.0) to rhythmbox
        rating (from 0 to 5) """
        rhytm_rating = 5 * float(rating)
        return rhytm_rating
        
        
        
    def _check_recognized_format(self, pathSong):
        """ 
        Format detection is extension based, so please name well your audio files
        Return the type of tag that is going to be used for the selected format
        mp3 >>>> id3v2
        ogg and oga >>> oggvorbis
        flac >>> flac
        mp4 and m4a >>> mp4
        etc...
        return value should be xxx where xxx is in a method _save_db_to_xxx
        return None if unknown format
        """
        
        ext4 = pathSong[-5:].lower()
        ext3 = ext4[1:]
        
        if ext3 == ".mp3":
            return "id3v2"
        elif ext3 == ".ogg" or ext3 == ".oga":
            return "oggvorbis"
        elif ext4 == ".flac":
            return "flac"
        elif ext3 == ".mp4" or ext3 == ".m4a":
            return "mp4"
        elif ext3 == ".mpc":
            return "musepack"
        elif ext3 == ".spx":
            return "oggspeex"
        else:
            return None            

 

    def _save_db_to_id3v2(self, pathSong, dbrating, dbcount):
        """ Save rating and playcount from Rhythmbox db to standard ID3v2 tags
        
        POPM stand for Popularimeter, we use Banshee ratings standard (which is also an ID3v2 standard,
        meaning a value between 0 and 255). (should eventually be deprecated)
        (see http://www.id3.org/id3v2.4.0-frames section 4.16 )
        
        TXXX:FMPS_Rating and TXXX:FMPS_Playcount are from the FMPS freedesktop specs
        (see  http://www.freedesktop.org/wiki/Specifications/free-media-player-specs)
        
        """
        audio = ID3(pathSong)
        # Instead of having two I/O operations each time, 
        # we can get only one I/O operation when rating AND playcount haven't changed
        # We use needsave boolean to do that
        needsave = False
        
        if self.ratingsenabled:
            if dbrating > 0:
                # First we store it in POPM format
                
                ########### POPM (will be deprecated eventually) #######
                popmrating = audio.get('POPM:Banshee')
                if popmrating == None:
                    # No existing tag POPM has been found, so create one...
                    audio.add(POPM(email=u'Banshee', rating=int(51 * dbrating)))
                    needsave = True
                else:
                    # An existing tag POPM has been found, let's check if the rating has changed
                    if self._convert_ID3v2_rating_to_rhythmbdb_rating(popmrating.rating) != dbrating:
                        # If it has, erase the value of the file an replace it with the db value (converted)
                        audio.delall('POPM:Banshee')
                        audio.add(POPM(email=u'Banshee', rating=int(51 * dbrating)))
                        needsave = True
                ####################################################
                
                
                ############# TXXX #################################
                fmpsrating = audio.get(u'TXXX:FMPS_Rating')
                if fmpsrating == None:
                    # No existing tag TXXX for FMPS has been found, so create one...
                    audio.add(TXXX(encoding=3, desc=u"FMPS_Rating", text=[unicode(0.2 * dbrating)]))
                    needsave = True
                else:
                    # An existing tag TXXX for FMPS has been found, let's check if the rating has changed
                    if self._convert_fmps_rating_to_rhythmbdb_rating(fmpsrating.text[0]) != dbrating:
                        # If it has, erase the value of the file and replace it with the db value (converted)
                        audio.delall(u'TXXX:FMPS_Rating')
                        audio.add(TXXX(encoding=3, desc=u"FMPS_Rating", text=[unicode(0.2 * dbrating)]))
                        needsave = True            
                #######################################################
                
                
        if self.playcountsenabled: 
            if dbcount > 0:
                
                ######### TXXX ############
                fmpsplaycount = audio.get(u'TXXX:FMPS_Playcount')
                if fmpsplaycount == None:
                    # No existing tag TXXX for FMPS has been found, so create one...
                    audio.add(TXXX(encoding=3, desc=u"FMPS_Playcount", text=[unicode(1.0 * dbcount)]))
                    needsave = True
                else:
                    # An existing tag TXXX for FMPS has been found, let's check if the playcount has changed
                    if float(fmpsplaycount.text[0]) != dbcount:
                        # If it has, erase the value of the file and replace it with the db value (converted)
                        audio.delall(u'TXXX:FMPS_Playcount')
                        audio.add(TXXX(encoding=3, desc=u"FMPS_Playcount", text=[unicode(1.0 * dbcount)]))
                        needsave = True 
                ############################

        if needsave:
            # save to file only if needed
            audio.save()
            self.num_saved += 1
        else:
            self.num_already_done += 1




    def _save_db_to_oggvorbis(self, pathSong, dbrating, dbcount):
        audio = OggVorbis(pathSong)
        self._save_db_to_vcomment(audio, dbrating, dbcount)
    
    def _save_db_to_flac(self, pathSong, dbrating, dbcount):
        audio = FLAC(pathSong)
        self._save_db_to_vcomment(audio, dbrating, dbcount)
        
    def _save_db_to_oggspeex(self, pathSong, dbrating, dbcount):
        audio = OggSpeex(pathSong)
        self._save_db_to_vcomment(audio, dbrating, dbcount)
    
    def _save_db_to_vcomment(self, audio, rating, count):
       self._save_db_to_dict_tags(audio, 'FMPS_RATING', 'FMPS_PLAYCOUNT',
                                  unicode,
                                  rating, count)

    def _save_db_to_mp4(self, pathSong, dbrating, dbcount):
        audio = MP4(pathSong)
        
        self._save_db_to_dict_tags(audio,
                                   '----:com.apple.iTunes:FMPS_Rating',
                                    '----:com.apple.iTunes:FMPS_Playcount',
                                    str,
                                    dbrating, dbcount)
        
    def _save_db_to_musepack(self, pathSong, dbrating, dbcount):
        audio = Musepack(pathSong)
        self._save_db_to_dict_tags(audio, 'FMPS_RATING', 'FMPS_PLAYCOUNT',
                                  unicode,
                                  dbrating, dbcount)
    

        
     
    def _save_db_to_dict_tags(self, audio, rating_identifier, playcount_identifier, encoding, rating, count):
        """" Common code for _save_db_to_vcomment  and _save_db_to_mp4 and _save_db_to_"whatever use dictionnary tags"
        that use dictionnary tags to save rating and playcount. 
        Only the identifier (dictionnary key) changes, so you need to provide them.
        
        for vorbis comment, identifiers are 'FMPS_RATING' and 'FMPS_PLAYCOUNT'
        for mp4, identifiers are '----:com.apple.iTunes:FMPS_Rating' and  
        '----:com.apple.iTunes:FMPS_Playcount'
        etc...
         See http://www.freedesktop.org/wiki/Specifications/free-media-player-specs
        
        audio : the object representing the audio file 
        rating_identifier : the key to access the rating value in the dictionnary
        playcount_identifier : the key to access the playcount value in the dictionnary
        encoding : builtin methods, unicode or str
        rating : the rating to store (from the db)
        count : the playcount to store (from the db)
        
        """
        # First convert the rhytmbox db value to standard defined in the specs (float between 0 and 1)
        converted_dbrating = 0.2 * rating
        # Convert the count from the db (integer) to a float 
        converted_dbcount = 1.0 * count
        
        # Get the existing rating value (if any)
        existingrating = audio.get(rating_identifier)
        # Get the existing count value (if any)
        existingcount = audio.get(playcount_identifier)
        
        
        needsave = False
        
        if self.ratingsenabled:
            if existingrating is None:
                # There is no existing rating tag
                if converted_dbrating > 0:
                    # Create one, only if the value we want to save is greater than 0
                    audio[rating_identifier] = [encoding(converted_dbrating)]
                    needsave = True
            else:
                # There is an existing rating tag, if the value has changed...
                if float(existingrating[0]) != converted_dbrating:
                    # And if the value we want to save is greater than 0..
                    if converted_dbrating > 0:
                        # Update the tag
                        audio[rating_identifier] = [encoding(converted_dbrating)]
                    else:
                        # If the value we want to save is 0, remove the tag from the comment
                        del audio[rating_identifier]
                    needsave = True
        
        if self.playcountsenabled:
            if existingcount is None:
                # There is no existing count tag
                if converted_dbcount > 0:
                    # Create one, only if the value we want to save is greater than 0
                    audio[playcount_identifier] = [encoding(converted_dbcount)]
                    needsave = True
            else:
                # There is an existing count tag, if the value has changed...
                if float(existingcount[0]) != converted_dbcount:
                    # And if the value we want to save is greater than 0..
                    if converted_dbcount > 0:
                        # Update the tag
                        audio[playcount_identifier] = [encoding(converted_dbcount)]
                    else:
                        # If the value we want to save is 0, remove the tag from the comment
                        del audio[playcount_identifier]
                    needsave = True

        if needsave:
            # save to file only if needed            
            audio.save()
            self.num_saved += 1
        else:
            self.num_already_done += 1
    

    def _save_db_to(self, pathSong, dbrating, dbcount, format):
        """ This Selector use getattr to select the right function to call
        Available format are :
        id3v2
        oggvorbis
        flac
        mp4
        apev2
        etc...
        
        For example, if the format is id3v2, then _save_db_to_id3v2 will be called
        
        """
        save_db_to_function = getattr(self, "_save_db_to_%s" % format)
        save_db_to_function(pathSong, dbrating, dbcount)
        

    def saveRhythmDBToFile(self, db, element, path_normalizado):
        """
        - A doaction function 
        - Save ratings and playcount from Rhytmbox Database to file
        - Should be audio format agnostic 
        
        """
        
    
        try:
            # Get the dbrating value (float) of the RhythmboxDB element 
            dbrating = db.entry_get(element, rhythmdb.PROP_RATING)
            # Get the dbcount value (integer) of the RhythmboxDB element
            dbcount = db.entry_get(element, rhythmdb.PROP_PLAY_COUNT)
         
            
            # Get the audio tagging format of the current element
            format = self._check_recognized_format(path_normalizado)
            
            if format is None:
                raise Exception("Unrecognized format")
            else:
                # Audio format is known, call the selector...
                self._save_db_to(path_normalizado, dbrating, dbcount, format)
            
            
        except Exception, e:
                self.num_failed += 1
                #self.mysource.add_entry(element, -1)
                print(e, path_normalizado)
        



    def _restore_db_from_id3v2(self, pathSong):
        """ This function return the rating and playcount from 
        a mp3 file (with ID3v2 tag) in order to update rhythmbox db 
        Return value is a tuple
        """
        audio = ID3(pathSong)
        
        filerating = 0
        if self.ratingsenabled:
            
            popmrating = audio.get('POPM:Banshee')
            if popmrating is not None:
                rating = popmrating.rating
                filerating = self._convert_ID3v2_rating_to_rhythmbdb_rating(rating)
                
                
            fmpsplaycount = audio.get(u'TXXX:FMPS_Rating')
            if fmpsplaycount is not None:
                rating = fmpsplaycount.text[0] 
                filerating = self._convert_fmps_rating_to_rhythmbdb_rating(rating)
            
        # /!\ TXXX:FMPS_Rating takes precedence over POPM value /!\
        
         
        filecount = 0
        if self.playcountsenabled:
            
            fmpsplaycount = audio.get(u'TXXX:FMPS_Playcount')
            if fmpsplaycount is not None:
                filecount = int(float(fmpsplaycount.text[0])) # is an unicode string 
        
        return (filerating, filecount)
        
        
    
    def _restore_db_from_oggvorbis(self, pathSong):
        audio = OggVorbis(pathSong)
        return self._restore_db_from_vcomment(audio)
    
    def _restore_db_from_flac(self, pathSong):
        audio = FLAC(pathSong)
        return self._restore_db_from_vcomment(audio)
    
    def _restore_db_from_oggspeex(self, pathSong):
        audio = OggSpeex(pathSong)
        return self._restore_db_from_vcomment(audio)
    
    def _restore_db_from_vcomment(self, audio):
        return self._restore_db_from_dict_tags('FMPS_RATING',
                                               'FMPS_PLAYCOUNT',
                                               audio)
        
    def _restore_db_from_mp4(self, pathSong):
        audio = MP4(pathSong)
        return self._restore_db_from_dict_tags('----:com.apple.iTunes:FMPS_Rating',
                                               '----:com.apple.iTunes:FMPS_Playcount',
                                               audio)

    def _restore_db_from_musepack(self, pathSong):
        audio = Musepack(pathSong)
        return self._restore_db_from_dict_tags('FMPS_RATING',
                                               'FMPS_PLAYCOUNT',
                                               audio)
    
    def _restore_db_from_dict_tags(self, rating_identifier, playcount_identifier, audio):
        """" Common code for _restore_db_from_vcomment  and _restore_db_from_mp4 
        that use dictionnary tags to save rating and playcount. 
        Only the identifier (dictionnary key) changes, so you need to provide them.
        
        for vorbis comment, identifiers are 'FMPS_RATING' and 'FMPS_PLAYCOUNT'
        for mp4, identifiers are '----:com.apple.iTunes:FMPS_Rating' and  
        '----:com.apple.iTunes:FMPS_Playcount' 
        
        """
        
        # Get the existing rating value (if any)
        filerating = audio.get(rating_identifier)
        
        if filerating is None:
            convertedfilerating = 0
        else:
            convertedfilerating = self._convert_fmps_rating_to_rhythmbdb_rating(filerating[0])
        
        # Get the existing count value (if any)
        filecount = audio.get(playcount_identifier)

        if filecount is None:
            convertedfilecount = 0
        else:
            convertedfilecount = int(float(filecount[0]))
        
        
        # Returned converted filerating and filecount
        return convertedfilerating, convertedfilecount
    
    
    def _restore_db_from(self, pathSong, format):
        """ this Selector use getattr to select the right function to call
        Available format are :
        id3v2
        oggvorbis
        flac
        etc...
        """
        
        restore_db_from_function = getattr(self, "_restore_db_from_%s" % format)
        return restore_db_from_function(pathSong)


    def restoreRhythmDBFromFile(self, db, element, path_normalizado):
        """ 
        - A doaction function
        - Restore ratings and playcounts from file to Rhythmbox db
        - Should be audio format agnostic
        """
       
        try: 
            # Get the audio tagging format of the current element
            format = self._check_recognized_format(path_normalizado)
       

            if format is None:
               raise Exception("Unrecognized format")
            
            else:
                # Format is known, call the selector...
                filerating, filecount = self._restore_db_from(path_normalizado, format)
                # Use need commit to commit only if necessary (if the tags read from the file are different)            
                needcommit = False
                
                if self.ratingsenabled:
                    if filerating > 0 and db.entry_get(element, rhythmdb.PROP_RATING) != filerating:
                        db.set(element, rhythmdb.PROP_RATING, filerating)
                        needcommit = True
                
                if self.playcountsenabled:     
                    if filecount > 0 and db.entry_get(element, rhythmdb.PROP_PLAY_COUNT) != filecount:
                        db.set(element, rhythmdb.PROP_PLAY_COUNT, filecount)
                        needcommit = True
                
                if needcommit:
                    db.commit()
                    self.num_restored += 1
                else:
                    self.num_already_done += 1
        
        except Exception, e:
                self.num_failed += 1
                print(e, path_normalizado)


    def cleanAllTags(self, db, element, path_normalizado):
        """ Method to clean all rating and playcount tags from the file"""
        try: 
            # Get the audio tagging format of the current element
            format = self._check_recognized_format(path_normalizado)
            if format is None:
               raise Exception("Unrecognized format")
            else:
                needsave = False
                if format == "id3v2":
                    audio = ID3(path_normalizado)
                    if audio.has_key('POPM'):
                        audio.delall('POPM')
                        needsave = True
                    if audio.has_key('PCNT'):
                        audio.delall('PCNT')
                        needsave = True
                    if audio.has_key(u'TXXX:FMPS_Rating'):
                        audio.delall(u'TXXX:FMPS_Rating')
                        needsave = True
                    if audio.has_key(u'TXXX:FMPS_Playcount'):
                        audio.delall(u'TXXX:FMPS_Playcount')
                        needsave = True
                    
                    
                elif format == "oggvorbis":
                    audio = OggVorbis(path_normalizado)
                    if audio.has_key('FMPS_RATING'):
                        del audio['FMPS_RATING']
                        needsave = True
                    if audio.has_key('FMPS_PLAYCOUNT'):
                        del audio['FMPS_PLAYCOUNT']
                        needsave = True
                elif format == "flac":
                    audio = FLAC(path_normalizado)
                    if audio.has_key('FMPS_RATING'):
                        del audio['FMPS_RATING']
                        needsave = True
                    if audio.has_key('FMPS_PLAYCOUNT'):
                        del audio['FMPS_PLAYCOUNT']
                        needsave = True
                elif format == "mp4":
                    audio = MP4(path_normalizado)
                    if audio.has_key('----:com.apple.iTunes:FMPS_Rating'):
                        del audio['----:com.apple.iTunes:FMPS_Rating']
                        needsave = True
                    if audio.has_key('----:com.apple.iTunes:FMPS_Playcount'):
                        del audio['----:com.apple.iTunes:FMPS_Playcount']
                        needsave = True
                elif format == "musepack":
                    audio = Musepack(path_normalizado)
                    if audio.has_key('FMPS_RATING'):
                        del audio['FMPS_RATING']
                        needsave = True
                    if audio.has_key('FMPS_PLAYCOUNT'):
                        del audio['FMPS_PLAYCOUNT']
                        needsave = True
                        
                elif format == "oggspeex":
                    audio = OggSpeex(path_normalizado)
                    if audio.has_key('FMPS_RATING'):
                        del audio['FMPS_RATING']
                        needsave = True
                    if audio.has_key('FMPS_PLAYCOUNT'):
                        del audio['FMPS_PLAYCOUNT']
                        needsave = True
                    
                if needsave:
                    audio.save()
                    self.num_cleaned += 1
                else:
                    self.num_already_done += 1
    
        except Exception, e:
                self.num_failed += 1
                print(e, path_normalizado)

    
    def _on_entry_change(self, db, entry, changes):
        """ Callback method that is called each time an database entry is changed (autosave feature)
        We only need to catch specific entry changes (PROP_RATING, PROP_PLAY_COUNT) 
        """
        if changes[0].prop == rhythmdb.PROP_RATING or changes[0].prop == rhythmdb.PROP_PLAY_COUNT:
             self.saveRhythmDBToFile(db, entry, url2pathname(entry.get_playback_uri()[7:]))
             print("Autosave done")




#class MyEntryType(rhythmdb.EntryType):
#    def __init__(self):
#        rhythmdb.EntryType.__init__(self, name='my-entry-type')
#
#class MySource(rb.StaticPlaylistSource):
#    def __init__(self):
#        rb.StaticPlaylistSource.__init__(self)
#        
#gobject.type_register(MySource)
