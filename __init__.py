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


from mutagen.id3 import ID3, POPM, PCNT
from os import path
from urllib import url2pathname
import gtk
import pynotify
import rb
import rhythmdb

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
        
        # TODO: rajouter une action plus évoluée pour la synchro bidirectionnelle ?
        # TODO: faire une sauvegarde la BD de rhythmbox avant de modifier (dans /tmp ?)
        
        # Store the full path to the plugin directory (to access external resources as XML ui definition, icons, etc...)
        self.pluginrootpath=path.expanduser("~/.local/share/rhythmbox/plugins/saveTAGRating/")
        
        # Define callback methods on these actions
        self.action.connect('activate', self.executedoActionOnSelected,self.saveRhythmDBToFile, shell)       
        self.action2.connect('activate', self.executedoActionOnSelected,self.restoreRhythmDBFromFile, shell)
        
        # Un autre menu pour une autre action (qui s'appliquerait sur les éléments sélectionnés aurait la forme suivante :
        #self.actionX.connect('activate', self.executedoActionOnSelected,self.une_methode_a_definir_dans_la_classe, shell)
        
        
        # Create a group of actions, add the previously defined actions to it, and insert it to the ui manager
        self.action_group = gtk.ActionGroup('saveTAGRatingPluginActions')
        self.action_group.add_action(self.action)
        self.action_group.add_action(self.action2)
        self.uim = shell.get_ui_manager ()
        self.uim.insert_action_group(self.action_group, 0)
        
        # Load the ui structure from the xml file
        self.ui_id = self.uim.add_ui_from_file(self.pluginrootpath+"saveratings_ui.xml")
        # Refresh user interface
        self.uim.ensure_update()
        
        print("Plugin activated")
        
    
    def check_recognized_format(self, pathSong):
        """ Return true if the file (pathSong) is a recognized audio format (mp3,ogg, flac,etc...)"""
        ext4=pathSong[-5:].lower()
        ext3=ext4[1:].lower()
        
        return ext3 == ".mp3" #or ext3 == ".ogg" or ext3==".oga" or ext4==".flac" 
            

    def save_db_to_id3v2(self,pathSong,dbrating,dbcount):
        """ Save rating and playcount from Rhythmbox db to standard ID3v2 tags
        See http://www.id3.org/id3v2.4.0-frames section 4.16 and 4.17
        !!! Only for MP3 !!!
        POPM stand for Popularimeter
        PCNT stand for Play Counter 
        """
        audio = ID3(pathSong)
        if dbrating>0:
            audio.delall('POPM')
            audio.add(POPM(email=u'Banshee',rating=int(51*dbrating)))
            # ajouter une compatibilité avec d'autres lecteurs qui stockerait différemment
            # le rating (c'est à dire autrement que entre 1 et 255 ou que entre 0 et 5)
            #audio.add(POPM(email=u'Other Player',rating=?????????)))
        if dbcount>0:
            audio.delall('PCNT') 
            audio.add(PCNT(count=int(dbcount)))
        audio.save()
            
            
            
    def save_db_to_xiphcomment(self,pathSong,dbrating,dbcount):
        """" Save rating and playcount from Rhythmbox db to xiph comment (vorbis)
        for ogg vorbis and flac """
        #TODO: prendre en charge le Ogg et le FLAC
        # il semblerait qu'il n'y ait pas de standard pour le Ogg et le FLAC, comme pour ID3
        # à creuser
        pass
    
    
    
    def get_ID3v2_Rating(self, pathSong):
        """ Function to get the rating from a file (pathSong) and to return 
        a Rhythmbox compatible ratings (value from 0 to 5)"""
        # By default, 0 means an unknown rating 
        rhytm_rating = 0
        audio = ID3(pathSong)
        popmlist = audio.getall('POPM')
        if popmlist != []:
            rating = popmlist[0].rating
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

    
    def get_ID3v2_Count(self, pathSong):
        """ Function to get the playcount from a file (pathSong) """
        # By default, 0 means the file has never been played 
        rhytm_playcount = 0
        audio = ID3(pathSong)
        pcntlist = audio.getall('PCNT')
        if pcntlist != []:
            rhytm_playcount = pcntlist[0].count    
        return rhytm_playcount

      
    def executedoActionOnSelected(self, action, doaction, shell):
        """ Function to apply doaction on each element that has been selected """        
        # Get a rb.Source instance of the selected page
        source = shell.get_property("selected_page")
        # Get an EntryView for the selected source (the track list)
        entryview = source.get_entry_view()
        # Get the list of selected entries from the track list
        selected = entryview.get_selected_entries()
        
        global num_saved,num_failed,num_restored
        num_saved,num_failed,num_restored=0,0,0
        
        
        # Get the  RhythmDBTree from the shell to do some 
        # high level queries and updates
        db = shell.props.db
        # For each element of the selection...
        for element in selected:
            uri = element.get_playback_uri()
            dirpath = uri.rpartition('/')[0]
            uri_normalizado = url2pathname(dirpath.replace("file://", ""))
            path_normalizado = url2pathname(uri.replace("file://", ""))
            # ...Execute the doaction function
            doaction(db,element,path_normalizado)
        
        
        
        print(num_saved,num_restored,num_failed)
        pynotify.init('notify_user')
        pynotify.Notification(_("Status"), _("%s saved \n %s restored \n %s failed "%(num_saved,num_restored,num_failed))).show()
      
      
      
      
    def saveRhythmDBToFile(self, db,element,path_normalizado):
        """ a doaction function """
        """ Save ratings and playcount from Rhytmbox Database to file """
        # Get the dbrating value (float) of the RhythmboxDB element 
        dbrating = db.entry_get(element, rhythmdb.PROP_RATING)
        # Get the dbcount value (integer) of the RhythmboxDB element
        dbcount = db.entry_get(element, rhythmdb.PROP_PLAY_COUNT)
       
        global num_saved
        global num_failed
        print("dbrating",dbrating)
        print("dbcount",dbcount)        
        
        if self.check_recognized_format(path_normalizado):
            
            #TODO: utiliser l'introspection pour faire selon le format (mp3, ogg, flac, etc...) une sauvegarde spécifique
            # c'est à dire appeler save_db_to_xxx(...) avec xxx à remplacer selon le format audio
            
            self.save_db_to_id3v2(path_normalizado, dbrating, dbcount)
            num_saved+=1
            print("save db to file done")        

            ####### Check if tag has been saved (debug) ############
            #filerating = self.get_ID3v2_Rating(path_normalizado)
            #print("filerating",filerating)
            #filecount = self.get_ID3v2_Count(path_normalizado)
            #print("filecount",filecount)
            ############################################
        else:
            #TODO: utiliser les exceptions pour gérer tous les cas d'erreurs (erreur d'entrée sortie, cause inconnue, etc...)
            # pour rendre transactionnel le code précédent, ainsi la levée d'une exception entraînera l'incrémentation de num_failed
            # même si la cause n'est pas juste un format non reconnu
            num_failed+=1
            print("unrecognized format")



    def restoreRhythmDBFromFile(self, db, element,path_normalizado):
        """ a doaction function """
        """ Restore ratings and playcounts from file to Rhythmbox db"""
        global num_restored
        global num_failed
        if self.check_recognized_format(path_normalizado):
            #TODO: utiliser l'introspection pour faire selon le format (mp3, ogg, flac, etc...) une restauration spécifique
            # c'est à dire appeler save_db_to_xxx(...) avec xxx à remplacer selon le format audio
            filerating = self.get_ID3v2_Rating(path_normalizado)
            print("filerating",filerating)
            db.set(element, rhythmdb.PROP_RATING, filerating)
            filecount = self.get_ID3v2_Count(path_normalizado)
            db.set(element, rhythmdb.PROP_PLAY_COUNT, filecount)
            db.commit() 
            num_restored+=1
            print("filecount",filecount)
        else:
            #TODO: utiliser les exceptions pour gérer tous les cas d'erreurs (erreur d'entrée sortie, cause inconnue, etc...)
            # pour rendre transactionnel le code précédent, ainsi la levée d'une exception entraînera l'incrémentation de num_failed
            # même si la cause n'est pas juste un format non reconnu
            num_failed+=1       
            print("unrecognized format")


    def deactivate(self, shell):
        """ Dereference any fields that has been initialized in activate"""
        self.uim.remove_ui (self.ui_id)
        del self.ui_id
        self.uim.remove_action_group (self.action_group)
        del self.uim
        del self.action_group
        del self.action
        del self.action2
        del self.pluginrootpath
