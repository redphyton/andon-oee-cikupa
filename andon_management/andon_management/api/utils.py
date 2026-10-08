# File: andon_management/andon_management/api/utils.py

import frappe

@frappe.whitelist()
def get_machine_list():
    """Mengembalikan daftar semua nama mesin."""
    
    machines = frappe.get_all(
        "Mesin",
        fields=["mesin"],
        order_by="mesin asc"
    )
    
    # Mengubah dari list of dictionary menjadi list of string
    # Contoh: dari [{'name': 'A'}, {'name': 'B'}] menjadi ['A', 'B']
    return [m.get("mesin") for m in machines]