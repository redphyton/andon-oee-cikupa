import frappe
from frappe.utils import get_first_day, get_last_day, add_days, getdate


def execute(filters=None):
    # ======================================================
    # 1. RANGE TANGGAL BULAN INI (DATE OBJECT)
    # ======================================================
    today = getdate(frappe.utils.nowdate())
    start_date = getdate(get_first_day(today))
    end_date = getdate(get_last_day(today))

    # List semua tanggal dalam bulan ini
    dates = []
    cur = start_date
    while cur <= end_date:
        dates.append(cur)
        cur = add_days(cur, 1)

    # ======================================================
    # 2. GET LIST URUTAN UNTUK STA-01
    # ======================================================
    urutan_list = frappe.db.get_all(
        "Data Andon OEE",
        fields=["distinct urutan"],
        filters={"nama_assy": "STA-01"},
        order_by="urutan asc"
    )

    # ======================================================
    # 3. DEFINISI KOLOM LAPORAN
    # ======================================================
    columns = [
        {"label": "Urutan",    "fieldname": "urutan",    "fieldtype": "Int",  "width": 60},
        {"label": "Deskripsi", "fieldname": "deskripsi", "fieldtype": "Data", "width": 200},
    ]

    # Kolom per tanggal → 2 kolom: Plan & Actual
    for d in dates:
        d_str = d.strftime("%Y_%m_%d")
        d_label = d.strftime("%d-%m")

        columns.extend([
            {"label": f"{d_label} Plan",   "fieldname": f"plan_{d_str}",   "fieldtype": "Int", "width": 70},
            {"label": f"{d_label} Actual", "fieldname": f"actual_{d_str}", "fieldtype": "Int", "width": 70},
        ])

    # ======================================================
    # 4. AMBIL DATA OEE UNTUK STA-01
    # ======================================================
    all_data = frappe.db.get_all(
        "Data Andon OEE",
        fields=["tanggal", "urutan", "deskripsi", "plan", "actual"],
        filters={
            "nama_assy": "STA-01",
            "tanggal": ["between", [start_date, end_date]]
        }
    )

    # Convert tanggal ke date object
    for x in all_data:
        x["tanggal"] = getdate(x["tanggal"])

    # ======================================================
    # 5. SUSUN DATA PIVOT
    # ======================================================
    rows = []

    for u in urutan_list:
        urut = u.urutan

        base = next((x for x in all_data if x.urutan == urut), None)

        row = {
            "urutan": urut,
            "deskripsi": base.deskripsi if base else "",
        }

        # Isi kolom tanggal
        for d in dates:
            d_str = d.strftime("%Y_%m_%d")

            item = next((x for x in all_data if x.urutan == urut and x.tanggal == d), None)

            if item:
                row[f"plan_{d_str}"]   = item.plan
                row[f"actual_{d_str}"] = item.actual
            else:
                row[f"plan_{d_str}"]   = 0
                row[f"actual_{d_str}"] = 0

        rows.append(row)

    return columns, rows
