# Copyright (c) 2025, ivan co and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StatusAndonOEE(Document):
	def on_update(self):
		# Siapkan data yang akan dikirim ke layar
		eff = self.eff * 100 
		payload = {
			"nama_assy": self.nama_assy,
			"model": self.model,
			"tujuan": self.tujuan,
			"d_plan": self.d_plan,
			"h_plan": self.h_plan,
			"actual": self.actual,
			"balance": self.balance,
			"status_line": self.status_line,
			"info_planning": self.info_planning,
			"alarm_id": self.alarm_id,
			# Format angka desimal langsung di sini agar konsisten
			"jtt_fmt": "{:.1f}".format(self.jtt or 0),
			"mtt_fmt": "{:.1f}".format(self.mtt or 0),
			"eff_fmt": "{:.1f}".format(eff or 0)
		}
		
		# Kirim sinyal Real-Time ke room 'website' (Semua orang yang buka web)
		frappe.publish_realtime(
			event='andon_update_event',  # Nama event unik
			message=payload, 
			room='website'               # Room public
		)