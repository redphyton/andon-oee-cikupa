import frappe
from datetime import datetime, timedelta

def get_context(context):
    doc_name = frappe.form_dict.get("name", "MULTY PACER")
    
    if frappe.db.exists("Shop Floor", doc_name):
        data = frappe.get_doc("Shop Floor", doc_name)
        context.doc = data
        
        # Hitung apakah data sudah stale (> 1 jam)
        now = datetime.now()
        modified = data.modified  # field bawaan Frappe, selalu ada
        diff_minutes = (now - modified).total_seconds() / 60
        context.last_updated_iso = modified.strftime("%Y-%m-%dT%H:%M:%S")
        context.is_stale = diff_minutes > 60
    else:
        context.doc = frappe._dict({
            "name": doc_name,
            "status": "OFFLINE",
            "plan": 0,
            "target": 0,
            "actual": 0,
            "part_no": "-",
            "part_item": "-",
            "notes": "No Data",
            "modified": datetime.now()
        })
        context.last_updated_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        context.is_stale = True  # Kalau tidak ada data, langsung anggap stale
        
    context.doc_name = doc_name