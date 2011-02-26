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

class saveTAGRatingConfigureDialog (object):
	def __init__(self, builder_file, gconf_keys):
		self.gconf = gconf.client_get_default()
		self.gconf_keys = gconf_keys

		builder = gtk.Builder()
		builder.add_from_file(builder_file)
		
		self.dialog=builder.get_object("preferences_dialog")
		
		# Get the boolean values from gconf (store them for later restoration (if needed))
		self.autosaveenabled=self.gconf.get_bool(self.gconf_keys['autosaveenabled'])
		self.ratingsenabled=self.gconf.get_bool(self.gconf_keys['ratingsenabled'])
		self.playcountsenabled=self.gconf.get_bool(self.gconf_keys['playcountsenabled'])
		
		# Setup buttons
		self.autosavecheckbutton=builder.get_object("autosaveenablecheckbutton")
		self.autosavecheckbutton.set_active(self.autosaveenabled)
		self.ratingscheckbutton=builder.get_object("ratingscheckbutton")
		self.ratingscheckbutton.set_active(self.ratingsenabled)
		self.playcountscheckbutton=builder.get_object("playcountscheckbutton")
		self.playcountscheckbutton.set_active(self.playcountsenabled)
		
		# Setup callbacks
		self.dialog.connect("response", self.dialog_response)
		self.autosavecheckbutton.connect("toggled",self.autosavetoggle_callback)
		self.ratingscheckbutton.connect("toggled",self.ratingstoggle_callback)
		self.playcountscheckbutton.connect("toggled",self.playcountstoggle_callback)


	def dialog_response(self, dialog, response):
		if response == gtk.RESPONSE_OK:
			self.dialog.hide()
		elif response == gtk.RESPONSE_CANCEL or response == gtk.RESPONSE_DELETE_EVENT:
			# Restore previous booleans
			self.gconf.set_bool(self.gconf_keys['autosaveenabled'],self.autosaveenabled)
			self.gconf.set_bool(self.gconf_keys['ratingsenabled'],self.ratingsenabled)
			self.gconf.set_bool(self.gconf_keys['playcountsenabled'],self.playcountsenabled)

			# etc...
			self.dialog.hide()
		else:
			print "unexpected response type"
	
	def get_dialog (self):
		return self.dialog


	def autosavetoggle_callback(self,widget):
		# Change the gconf value whenever the checkbox is changed
		self.gconf.set_bool(self.gconf_keys['autosaveenabled'],widget.get_active())
		
	def ratingstoggle_callback(self,widget):
		# Change the gconf value whenever the checkbox is changed
		self.gconf.set_bool(self.gconf_keys['ratingsenabled'],widget.get_active())
	
	def playcountstoggle_callback(self,widget):
		# Change the gconf value whenever the checkbox is changed
		self.gconf.set_bool(self.gconf_keys['playcountsenabled'],widget.get_active())
		