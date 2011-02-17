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
#       This is based on saveTAGCover plugin written by (Copyright (C) 2010 Jeronimo Buencuerpo Fariña jerolata@gmail.com)
#       Matthieu Bosc (mbosc77@gmail.com)
#       Vysserk3  (vysserk3@gmail.com)
#
# Specs for tagging file : 
# http://www.freedesktop.org/wiki/Specifications/free-media-player-specs

from mutagen.id3 import ID3, POPM, PCNT, TXXX
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.mp4 import MP4
from os import path
import sys
from urllib import url2pathname
import gtk
import pynotify
import rb
import rhythmdb
import gobject
from time import time



class saveTAGRating(rb.Plugin):

    def __init__(self):
        rb.Plugin.__init__(self)
            
    def activate(self, shell):
        # Create two gtkAction
        # One to save to file 
        self.action = gtk.Action('savetofile', #name 
                                 _('Save ratings and playcounts to files'), #label
                                 _('Save ratings and playcounts to files'), #tooltip
                                 'saveTAGRating' # icon
                                 )
        # One to restore from file
        self.action2 = gtk.Action('restorefromfile', #name 
                                 _('Restore ratings and playcounts from files'), #label
                                 _('Restore ratings and playcounts from files'), #tooltip
                                 'saveTAGRating' # icon
                                 )
        
        # One to clean all tag (POPM,PCNT, TXXX, FMPS, etc...)
        self.action3 = gtk.Action('cleanalltags', #name 
                                 _('Remove rating/playcount tags of the selected files'), #label
                                 _('Remove rating/playcount tags of the selected files'), #tooltip
                                 'saveTAGRating' # icon
                                 )
        
        # TODO: rajouter une action plus évoluée pour la synchro bidirectionnelle ?
        # TODO: faire une sauvegarde la BD de rhythmbox avant de modifier (dans /tmp ?)
        
        # Store the full path to the plugin directory (to access external resources as XML ui definition, icons, etc...)
        #self.pluginrootpath = path.expanduser("~/.local/share/rhythmbox/plugins/saveTAGRating/")
        self.pluginrootpath = sys.path[0]+"/"
        
        # Define callback methods on these actions
        self.action.connect('activate', self.executedoActionOnSelected, self.saveRhythmDBToFile, shell)       
        self.action2.connect('activate', self.executedoActionOnSelected, self.restoreRhythmDBFromFile, shell)
        self.action3.connect('activate', self.executedoActionOnSelected, self.cleanAllTags, shell)
        
        # Un autre menu pour une autre action (qui s'appliquerait sur les éléments sélectionnés aurait la forme suivante :
        #self.actionX.connect('activate', self.executedoActionOnSelected,self.une_methode_a_definir_dans_la_classe, shell)
        
        
        # Create a group of actions, add the previously defined actions to it, and insert it to the ui manager
        self.action_group = gtk.ActionGroup('saveTAGRatingPluginActions')
        self.action_group.add_action(self.action)
        self.action_group.add_action(self.action2)
        self.action_group.add_action(self.action3)
        self.uim = shell.get_ui_manager ()
        self.uim.insert_action_group(self.action_group, 0)
        
        # Load the ui structure from the xml file
        self.ui_id = self.uim.add_ui_from_file(self.pluginrootpath + "saveratings_ui.xml")
        # Refresh user interface
        self.uim.ensure_update()
        
        print("Plugin activated")
        



      
    def executedoActionOnSelected(self, action, doaction, shell):
        """ Function to apply doaction method on each element that has been selected """        
        # Get a rb.Source instance of the selected page
        try:
            source = shell.get_property("selected_source")
        except TypeError:
            source = shell.get_property("selected_page")
     
        # Get an EntryView for the selected source (the track list)
        entryview = source.get_entry_view()
        # Get the list of selected entries from the track list
        selected = entryview.get_selected_entries()
        
        # Global variables to store statistics
        global num_saved, num_failed, num_restored, num_already_done, num_cleaned
        num_saved, num_failed, num_restored, num_already_done, num_cleaned = 0, 0, 0, 0, 0
        
                
        # Get the  RhythmDBTree from the shell to do some 
        # high level queries and updates
        db = shell.props.db
        
        
        
        ########### TO REMOVE ############################
        # Code before using gtk threads
        # For each element of the selection...
        #        for element in selected:
        #            uri = element.get_playback_uri()
        #            dirpath = uri.rpartition('/')[0]
        #            uri_normalizado = url2pathname(dirpath.replace("file://", ""))
        #            path_normalizado = url2pathname(uri.replace("file://", ""))
        #            # ...Execute the doaction function
        #            doaction(db, element, path_normalizado)
        #####################################################
        
        # Global variable to store the index of the current selected element
        # iel is set to 0 and will be increased during the loop of the idle callback 
        global iel
        iel = 0
        
        # Store the start time before we start a long computation
        global t0
        t0 = time()

        gobject.idle_add(self.idle_cb_loop_on_selected, # name of the callback  
                        selected, # additionnal parameters
                        db, #  --
                        doaction, # --
                        # named parameter to set an idle priority (background)
                        priority=gobject.PRIORITY_LOW) 
        
        
        
 
    
    def idle_cb_loop_on_selected(self, selected, db, doaction):
        """ Use chunked idle callbacks to perform IO operation in an asynchronous way
        See http://live.gnome.org/RhythmboxPlugins/WritingGuide#Using_idle_callbacks_for_repeated_tasks
        """
        global num_cleaned, num_saved, num_failed, num_restored, num_already_done
        global iel
        global t0
        
        gtk.gdk.threads_enter()
        finished = False
        
        # Count is used for chunked idle callbacks (to limit overhead of calling threads_enter())
        # maximum value to be properly defined (if N=size of the collection > N/2, N/3, N/4, N ????)
        count = 0
        
        
        
        while iel < len(selected) and count < 10:
            element = selected[iel]
            uri = element.get_playback_uri()
            dirpath = uri.rpartition('/')[0]
            uri_normalizado = url2pathname(dirpath.replace("file://", ""))
            path_normalizado = url2pathname(uri.replace("file://", ""))
            # ...Execute the doaction function
            doaction(db, element, path_normalizado)
            count += 1
            iel += 1
            
        if iel < len(selected):
            gtk.gdk.threads_leave()
            return True


        gtk.gdk.threads_leave()

        # Compute the total processing time (in seconds)
        t1 = time()
        totaltime = round(t1 - t0, 2)
        # Notification at the end of process
        pynotify.init('notify_user')
        pynotify.Notification(_("Status"), _("%s saved \n" + 
											  "%s restored \n" + 
											  "%s failed \n" + 
											  "%s already done \n" + 
                                              "%s cleaned \n" + 
											  "Took %s sec") % 
											  (num_saved,
											  num_restored,
                                                num_failed,
                                                num_already_done,
                                                num_cleaned,
                                                str(totaltime))).show()
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
        elif ext3 ==".mp4" or ext3==".m4a":
            return "mp4"
        else:
            return None            

 

    def _save_db_to_id3v2(self, pathSong, dbrating, dbcount):
        """ Save rating and playcount from Rhythmbox db to standard ID3v2 tags
        See http://www.id3.org/id3v2.4.0-frames section 4.16 and 4.17
        !!! Only for MP3 !!!
        POPM stand for Popularimeter
        PCNT stand for Play Counter 
        """
        global num_saved, num_already_done

        audio = ID3(pathSong)
        # Instead of having two I/O operations each time, 
        # we can get only one I/O operation when rating AND playcount haven't changed
        # We use needsave boolean to do that
        needsave = False
        
        
        if dbrating > 0:
            # First we store it in POPM format
            popmlist = audio.getall('POPM')
            if popmlist == []:
                # No existing tag POPM has been found, so create one...
                audio.add(POPM(email=u'banshee', rating=int(51 * dbrating)))
                needsave = True
            else:
                # An existing tag POPM has been found, let's check if the rating has changed
                if self._convert_ID3v2_rating_to_rhythmbdb_rating(popmlist[0].rating) != dbrating:
                    # If it has, erase the value of the file an replace it with the db value (converted)
                    audio.delall('POPM')
                    audio.add(POPM(email=u'banshee', rating=int(51 * dbrating)))
                    needsave = True
            fmpslist = audio.getall(u'TXXX:FMPS_Rating')
            if fmpslist == []:
                # No existing tag TXXX for FMPS has been found, so create one...
                audio.add(TXXX(encoding=3, desc=u"FMPS_Rating", text=[unicode(0.2 * dbrating)]))
                needsave = True
            else:
                # An existing tag TXXX for FMPS has been found, let's check if the rating has changed
                if self._convert_fmps_rating_to_rhythmbdb_rating(fmpslist[0].text[0]) != dbrating:
                    # If it has, erase the value of the file an replace it with the db value (converted)
                    audio.delall(u'TXXX:FMPS_Rating')
                    print dbrating
                    audio.add(TXXX(encoding=3, desc=u"FMPS_Rating", text=[unicode(0.2 * dbrating)]))
                    needsave = True            
            
        if dbcount > 0:
            pcntlist = audio.getall('PCNT')
            if pcntlist == []:
                # No existing tag PCNT has been found, create one...
                audio.add(PCNT(count=int(dbcount)))
                needsave = True
            else:
                # An existing tag PCNT has been found, let's check if the count has changed
                if pcntlist[0].count != dbcount:
                    audio.delall('PCNT')
                    audio.add(PCNT(count=int(dbcount)))
                    needsave = True

        if needsave:
            # save to file only if needed
            audio.save()
            num_saved += 1
        else:
            num_already_done += 1




    def _save_db_to_oggvorbis(self, pathSong, dbrating, dbcount):
        audio = OggVorbis(pathSong)
        self._save_db_to_vcomment(audio, dbrating, dbcount)
        pass
    
    def _save_db_to_flac(self, pathSong, dbrating, dbcount):
        audio = FLAC(pathSong)
        self._save_db_to_vcomment(audio, dbrating, dbcount)
        pass
   
    
    def _save_db_to_vcomment(self, audio, rating, count):
       self._save_db_to_dict_tags(audio,'FMPS_RATING','FMPS_PLAYCOUNT',rating,count)

    
    def _save_db_to_mp4(self, pathSong, dbrating, dbcount):
        audio=MP4(pathSong)
        
        self._save_db_to_dict_tags(audio, 
                                   '----:com.apple.iTunes:FMPS_Rating',
                                    '----:com.apple.iTunes:FMPS_Playcount',dbrating,dbcount)
    
    
     
    def _save_db_to_dict_tags(self,audio,rating_identifier,playcount_identifier,rating,count):
        """" Common code for _save_db_to_vcomment  and _save_db_to_mp4 
        that use dictionnary tags to save rating and playcount. 
        Only the identifier (dictionnary key) changes, so you need to provide them.
        
        for vorbis comment, identifiers are 'FMPS_RATING' and 'FMPS_PLAYCOUNT'
        for mp4, identifiers are '----:com.apple.iTunes:FMPS_Rating' and  
        '----:com.apple.iTunes:FMPS_Playcount'
        
        etc...
         See http://www.freedesktop.org/wiki/Specifications/free-media-player-specs
        """
        global num_saved, num_already_done
        # First convert the rhytmbox db value to standard defined in the specs (float between 0 and 1)
        converted_dbrating = 0.2 * rating
        # Convert the count from the db (integer) to a float 
        converted_dbcount = 1.0 * count
        
        # Get the existing rating value (if any)
        existingrating = audio.get(rating_identifier)
        # Get the existing count value (if any)
        existingcount = audio.get(playcount_identifier)
        
        
        needsave = False
        if existingrating is None:
            # There is no existing rating tag
            if converted_dbrating > 0:
                # Create one, only if the value we want to save is greater than 0
                audio[rating_identifier] = [unicode(converted_dbrating)]
                needsave = True
        else:
            # There is an existing rating tag, if the value has changed...
            if float(existingrating[0]) != converted_dbrating:
                # And if the value we want to save is greater than 0..
                if converted_dbrating > 0:
                    # Update the tag
                    audio[rating_identifier] = [unicode(converted_dbrating)]
                else:
                    # If the value we want to save is 0, remove the tag from the comment
                    del audio[rating_identifier]
                needsave = True
        
        
        if existingcount is None:
            # There is no existing count tag
            if converted_dbcount > 0:
                # Create one, only if the value we want to save is greater than 0
                audio[playcount_identifier] = [unicode(converted_dbcount)]
                needsave = True
        else:
            # There is an existing count tag, if the value has changed...
            if float(existingcount[0]) != converted_dbcount:
                # And if the value we want to save is greater than 0..
                if converted_dbcount > 0:
                    # Update the tag
                    audio[playcount_identifier] = [unicode(converted_dbcount)]
                else:
                    # If the value we want to save is 0, remove the tag from the comment
                    del audio[playcount_identifier]
                needsave = True

        if needsave:
            # save to file only if needed
            audio.save()
            
            num_saved += 1
        else:
            num_already_done += 1
    

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
        global num_saved, num_failed
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
                print("save db to file done")        
        
        except Exception, e:
                num_failed += 1
                print(e)
        



    def _restore_db_from_id3v2(self, pathSong):
        """ This function return the rating and playcount from 
        a mp3 file (with ID3v2 tag) in order to update rhythmbox db 
        Return value is a tuple
        """
        audio = ID3(pathSong)
        
        filerating = 0
        popmlist = audio.getall('POPM')
        if popmlist != []:
            rating = popmlist[0].rating
            filerating = self._convert_ID3v2_rating_to_rhythmbdb_rating(rating)
        fmpslist = audio.getall(u'TXXX:FMPS_Rating')
        if fmpslist != []:
            rating = fmpslist[0].text[0] # is an unicode string
            filerating = self._convert_fmps_rating_to_rhythmbdb_rating(rating)
            
        #Attention, filerating prendra ici la valeur de TXXX par défaut
        # mais si il n'pas de TXXX, alors la valeur POPM sera choisie
        
        filecount = 0
        pcntlist = audio.getall('PCNT')
        if pcntlist != []:
            filecount = pcntlist[0].count    
        
        return (filerating, filecount)
        
        
    
    def _restore_db_from_oggvorbis(self, pathSong):
        audio = OggVorbis(pathSong)
        return self._restore_db_from_vcomment(audio)
    
    def _restore_db_from_flac(self, pathSong):
        audio = FLAC(pathSong)
        return self._restore_db_from_vcomment(audio)
    
    
    def _restore_db_from_vcomment(self, audio):
        return self._restore_db_from_dict_tags('FMPS_RATING', 
                                               'FMPS_PLAYCOUNT', 
                                               audio)
        
    def _restore_db_from_mp4(self,pathSong):
        audio=MP4(pathSong)
        return self._restore_db_from_dict_tags('----:com.apple.iTunes:FMPS_Rating', 
                                               '----:com.apple.iTunes:FMPS_Playcount', 
                                               audio)
    
    
    def _restore_db_from_dict_tags(self, rating_identifier,playcount_identifier,audio):
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
        global num_restored, num_failed, num_already_done
       
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
                
                
                if filerating > 0 and db.entry_get(element, rhythmdb.PROP_RATING) != filerating:
                    db.set(element, rhythmdb.PROP_RATING, filerating)
                    needcommit = True
                            
                if filecount > 0 and db.entry_get(element, rhythmdb.PROP_PLAY_COUNT) != filecount:
                    db.set(element, rhythmdb.PROP_PLAY_COUNT, filecount)
                    needcommit = True
                
                if needcommit:
                    db.commit()
                    num_restored += 1
                else:
                    num_already_done += 1
        
        except Exception, e:
                num_failed += 1
                print(e)


    def cleanAllTags(self, db, element, path_normalizado):
        global num_cleaned, num_failed,num_already_done
        try: 
            # Get the audio tagging format of the current element
            format = self._check_recognized_format(path_normalizado)
            if format is None:
               raise Exception("Unrecognized format")
            
            else:
                
                needsave=False
                if format == "id3v2":
                    audio = ID3(path_normalizado)
                    if audio.has_key('POPM'):
                        audio.delall('POPM')
                        needsave=True
                    if audio.has_key('PCNT'):
                        audio.delall('PCNT')
                        needsave=True
                    if audio.has_key(u'TXXX:FMPS_Rating'):
                        audio.delall(u'TXXX:FMPS_Rating')
                        needsave=True
                    
                    
                elif format == "oggvorbis":
                    audio = OggVorbis(path_normalizado)
                    if audio.has_key('FMPS_RATING'):
                        del audio['FMPS_RATING']
                        needsave=True
                    if audio.has_key('FMPS_PLAYCOUNT'):
                        del audio['FMPS_PLAYCOUNT']
                        needsave=True
                elif format == "flac":
                    audio = FLAC(path_normalizado)
                    if audio.has_key('FMPS_RATING'):
                        del audio['FMPS_RATING']
                        needsave=True
                    if audio.has_key('FMPS_PLAYCOUNT'):
                        del audio['FMPS_PLAYCOUNT']
                        needsave=True
                elif format =="mp4":
                    audio = MP4(path_normalizado)
                    if audio.has_key('----:com.apple.iTunes:FMPS_Rating'):
                        del audio['----:com.apple.iTunes:FMPS_Rating']
                        needsave=True
                    if audio.has_key('----:com.apple.iTunes:FMPS_Playcount'):
                        del audio['----:com.apple.iTunes:FMPS_Playcount']
                        needsave=True

                if needsave:
                    audio.save()
                    num_cleaned+=1
                else:
                    num_already_done+=1
    
        except Exception, e:
                num_failed += 1
                print(e)
                
        finally:
            if audio: del audio
            
            
            
    def deactivate(self, shell):
        """ Dereference any fields that has been initialized in activate"""
        self.uim.remove_ui (self.ui_id)
        del self.ui_id
        self.uim.remove_action_group (self.action_group)
        del self.uim
        del self.action_group
        del self.action
        del self.action2
        del self.action3
        del self.pluginrootpath
        print("Plugin deactivated")
