# Copyright (c) 2025, ivan co and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DataAndonOEE(Document):
	def on_update(self):
		frappe.publish_realtime(
        event='refresh_andon_monitor', 
        message={'action': 'reload'}, 
        room='website')

	def on_trash(self):
		frappe.publish_realtime(
        event='refresh_andon_monitor', 
        message={'action': 'reload'}, 
        room='website')
