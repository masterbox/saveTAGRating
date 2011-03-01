# -*- Mode: python; coding: utf-8; tab-width: 8; indent-tabs-mode: t; -*-
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# The Rhythmbox authors hereby grant permission for non-GPL compatible
# GStreamer plugins to be used and distributed together with GStreamer
# and Rhythmbox. This permission is above and beyond the permissions granted
# by the GPL license by which Rhythmbox is covered. If you modify this code
# you may extend this exception to your version of the code, but you are not
# obligated to do so. If you do not wish to do so, delete this exception
# statement from your version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.
import gtk
import gconf

class saveTAGRatingConfigureDialog:
	""" Class representing the configuration dialog of the plugin"""
	
	def __init__(self, builder_file, gconf_keys, rbplugin):
		# Retrieve the gconf client
		self.gconf = gconf.client_get_default()
		# Store the gconf keys
		self.gconf_keys = gconf_keys
		# Store the calling plugin (rbplugin)
		self.rbplugin = rbplugin
		
		# Create a builder and load the ui file (glade interface)
		builder = gtk.Builder()
		builder.add_from_file(builder_file)
		
		# Get the gtk dialog object 
		self.dialog = builder.get_object("preferences_dialog")
		
		
		# Get the boolean values from gconf (and store them for later restoration (if needed))
		self.autosaveenabled = self.gconf.get_bool(self.gconf_keys['autosaveenabled'])
		self.ratingsenabled = self.gconf.get_bool(self.gconf_keys['ratingsenabled'])
		self.playcountsenabled = self.gconf.get_bool(self.gconf_keys['playcountsenabled'])
		
		# Get the gtk checkbuttons objects, and set their state according to the retrieved gconf values
		self.autosavecheckbutton = builder.get_object("autosaveenablecheckbutton")
		self.autosavecheckbutton.set_active(self.autosaveenabled)
		self.ratingscheckbutton = builder.get_object("ratingscheckbutton")
		self.ratingscheckbutton.set_active(self.ratingsenabled)
		self.playcountscheckbutton = builder.get_object("playcountscheckbutton")
		self.playcountscheckbutton.set_active(self.playcountsenabled)
		
		
		# Setup callbacks for the checkbuttons and for the dialog
		self.dialog.connect("response", self.dialog_response)
		self.autosavecheckbutton.connect("toggled", self.autosavetoggle_callback)
		self.ratingscheckbutton.connect("toggled", self.ratingstoggle_callback)
		self.playcountscheckbutton.connect("toggled", self.playcountstoggle_callback)


	def dialog_response(self, dialog, response):
		""" Callback method for the dialog 
		Two possible response : OK and CANCEL
		"""
		if response == gtk.RESPONSE_OK:
			
			if self.autosavecheckbutton.get_active():
				# If autosave is enable, connect (in the rbplugin instance) the "entry-changed" signal.
				self.rbplugin.autosaveenabled=True
				self.rbplugin.entrychanged_sig_id = self.rbplugin.db.connect('entry-changed', self.rbplugin._on_entry_change)
			else:
				# Else, disconnect it (but only if it was already connected)
				if self.rbplugin.autosaveenabled:
					self.rbplugin.db.disconnect(self.rbplugin.entrychanged_sig_id)
			
			
			# If the rating checkbutton is enabled, set the corresponding variable in the rbplugin instance
			self.rbplugin.ratingsenabled = self.ratingscheckbutton.get_active()		
			# Same thing for playcount checkbutton...
			self.rbplugin.playcountsenabled = self.playcountscheckbutton.get_active()
			
			# Some booleans have changed, call again setup_gtkactions to update menu
			self.rbplugin.setup_gtkactions(self.rbplugin.shell)
			
			# Hide the dialog box
			self.dialog.hide()
			
			
		elif response == gtk.RESPONSE_CANCEL or response == gtk.RESPONSE_DELETE_EVENT:
			# Cancellation requested. Restore previous booleans
			self.gconf.set_bool(self.gconf_keys['autosaveenabled'], self.autosaveenabled)
			self.gconf.set_bool(self.gconf_keys['ratingsenabled'], self.ratingsenabled)
			self.gconf.set_bool(self.gconf_keys['playcountsenabled'], self.playcountsenabled)
			
			# Hide the dialog box
			self.dialog.hide()
			
		else:
			print("unexpected response type")
	
	
	
	def get_dialog (self):
		return self.dialog


	def autosavetoggle_callback(self, widget):
		# Change the gconf value whenever the checkbox is changed
		self.gconf.set_bool(self.gconf_keys['autosaveenabled'], widget.get_active())
		
		
	def ratingstoggle_callback(self, widget):
		# Change the gconf value whenever the checkbox is changed
		self.gconf.set_bool(self.gconf_keys['ratingsenabled'], widget.get_active())
		self.disableautosavecheckbutton()
			
	def playcountstoggle_callback(self, widget):
		# Change the gconf value whenever the checkbox is changed
		self.gconf.set_bool(self.gconf_keys['playcountsenabled'], widget.get_active())
		self.disableautosavecheckbutton()
	
	def disableautosavecheckbutton(self):
		if not self.ratingscheckbutton.get_active() and not self.playcountscheckbutton.get_active():
			self.autosavecheckbutton.set_active(False)
			self.autosavecheckbutton.set_sensitive(False)
		else:
			self.autosavecheckbutton.set_sensitive(True)  