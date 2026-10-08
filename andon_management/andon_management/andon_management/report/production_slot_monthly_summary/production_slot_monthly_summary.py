import frappe
from frappe.utils import get_first_day, get_last_day, getdate, formatdate
from datetime import timedelta
import json # BARU: Impor library JSON

@frappe.whitelist(allow_guest=True)
def execute(filters=None):
    # BARU: Blok kode untuk memeriksa dan mengonversi 'filters'
    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except json.JSONDecodeError:
            # Handle kasus jika string tidak valid, meskipun jarang terjadi
            return [], []
            
    if not filters:
        filters = {}


    year = filters.get("year")
    month = filters.get("month")
    mesin = filters.get("mesin")

    # --- Langkah 1 & 2 ---
    start_date = get_first_day(f"{year}-{month}-01")
    end_date = get_last_day(f"{year}-{month}-01")
    date_list = []
    current_date = getdate(start_date)
    while current_date <= getdate(end_date):
        date_list.append(current_date)
        current_date += timedelta(days=1)

    master_slots = frappe.db.sql("""
        SELECT 
            name, slot_no, description AS deskripsi
        FROM `tabProduction Time Slot`
        ORDER BY slot_no ASC
    """, as_dict=True)

    # --- Langkah 3 ---
    conditions = "tanggal BETWEEN %(start_date)s AND %(end_date)s"
    values = {"start_date": start_date, "end_date": end_date}
    if mesin:
        # Menggunakan pencocokan eksak, bisa diubah ke LIKE jika dibutuhkan
        conditions += " AND mesin = %(mesin)s"
        values["mesin"] = mesin
        
    production_data = frappe.db.sql(f"""
        SELECT 
            mesin, slot, part_no, deskripsi, tanggal, plan_qty, actual_qty
        FROM `tabProduction Slot Summary`
        WHERE {conditions}
    """, values, as_dict=True)

    # Pemetaan Data dengan Logika Umum (Multi-Part per Slot)
    plan_actual_map = {}
    details_map = {}
    for row in production_data:
        # Kunci unik sekarang selalu (slot, part_no)
        unique_key = (row.slot, row.part_no)
        plan_actual_key = (row.slot, row.part_no, row.tanggal)
        
        plan_actual_map[plan_actual_key] = {"plan": row.plan_qty, "actual": row.actual_qty}
        
        if unique_key not in details_map:
             details_map[unique_key] = {"mesin": row.mesin, "part_no": row.part_no, "deskripsi": row.deskripsi}

    # --- Langkah 4: Definisi Kolom ---
    columns = [
        {"label": "Mesin", "fieldname": "mesin", "fieldtype": "Data", "width": 100},
        # {"label": "Slot No", "fieldname": "slot_no", "fieldtype": "Data", "width": 80},
        {"label": "Deskripsi Slot", "fieldname": "deskripsi", "fieldtype": "Data", "width": 150},
        {"label": "Part No", "fieldname": "part_no", "fieldtype": "Data", "width": 120},
    ]
    for d in date_list:
        day = formatdate(d, "dd")
        columns.append({"label": f"{day} Plan", "fieldname": f"plan_{day}", "fieldtype": "Int", "width": 80})
        columns.append({"label": f"{day} Actual", "fieldname": f"actual_{day}", "fieldtype": "Int", "width": 80})
    columns.append({"label": "Total Plan", "fieldname": "total_plan", "fieldtype": "Int", "width": 100})
    columns.append({"label": "Total Actual", "fieldname": "total_actual", "fieldtype": "Int", "width": 100})

    # Inisialisasi dictionary untuk menampung Grand Total
    grand_totals = { "total_plan": 0, "total_actual": 0 }
    for d in date_list:
        day = formatdate(d, "dd")
        grand_totals[f"plan_{day}"] = 0
        grand_totals[f"actual_{day}"] = 0

    # --- Langkah 5: Membangun Hasil Laporan ---
    results = []
    
    for slot in master_slots:
        slot_name = slot.name
        
        # Cari semua entri (part_no) yang cocok untuk slot ini
        matching_entries = []
        for key, value in details_map.items():
            if key[0] == slot_name: # key adalah (slot_name, part_no)
                matching_entries.append((key, value))

        # Jika tidak ada data produksi, tampilkan baris kosong
        if not matching_entries:
            row_data = {
                "slot_no": slot.slot_no, "mesin": mesin or "", "deskripsi": slot.deskripsi, "part_no": "",
                "total_plan": 0, "total_actual": 0
            }
            for d in date_list:
                day = formatdate(d, "dd")
                row_data[f"plan_{day}"] = 0
                row_data[f"actual_{day}"] = 0
            results.append(row_data)
            continue
            
        # Proses setiap entri (part_no) yang ditemukan
        for key, details in matching_entries:
            row_data = {
                "slot_no": slot.slot_no,
                "mesin": details.get("mesin"),
                "deskripsi": details.get("deskripsi"),
                "part_no": details.get("part_no"),
            }

            total_plan, total_actual = 0, 0
            for d in date_list:
                day = formatdate(d, "dd")
                
                plan_actual_key = (slot_name, details.get("part_no"), d)
                data = plan_actual_map.get(plan_actual_key, {"plan": 0, "actual": 0})
                plan, actual = data["plan"], data["actual"]
                
                row_data[f"plan_{day}"] = plan
                row_data[f"actual_{day}"] = actual
                
                grand_totals[f"plan_{day}"] += plan
                grand_totals[f"actual_{day}"] += actual

                total_plan += plan
                total_actual += actual

            row_data["total_plan"] = total_plan
            row_data["total_actual"] = total_actual
            results.append(row_data)
            
            grand_totals["total_plan"] += total_plan
            grand_totals["total_actual"] += total_actual

    # Tambahkan baris Grand Total ke akhir hasil jika ada data
    if results:
        total_row = grand_totals.copy()
        total_row["part_no"] = "<strong>TOTAL</strong>"
        results.append(total_row)

    return columns, results