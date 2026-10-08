# Copyright (c) 2025, ivan co and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ShopFloor(Document):
    def on_update(self):
        # Siapkan data yang akan dikirim ke layar (sama dengan parameter di HTML)
        payload = {
            "name": self.name,
            "status": self.status,
            "plan": self.plan,
            "target": self.target,
            "actual": self.actual,
            "part_item": self.part_item,
            "part_no": self.part_no,
            "notes": self.notes
        }
        
        # Kirim sinyal Real-Time
        # Menggunakan room 'website' agar sinyal dapat ditangkap di halaman publik (tanpa login)
        frappe.publish_realtime(
            event='shop_floor_update', 
            message=payload, 
            room='website' 
        )