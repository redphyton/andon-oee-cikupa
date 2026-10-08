import frappe
from frappe.utils import flt, today, add_days

def execute(filters=None):
    if not filters:
        filters = {}

    filters.setdefault('from_date', add_days(today(), -7))
    filters.setdefault('to_date', today())

    data = frappe.db.sql("""
        SELECT
            p.part_no,
			p.part_item,
            COUNT(p.name) AS total_lot,
            SUM(p.plan) AS total_plan,
            SUM(p.actual) AS total_aktual,
            SUM(p.ng) AS total_ng,
            SUM(p.up_time_menit) AS total_up_time,
            SUM(p.downtime_menit) AS total_down_time,
            SUM(p.durasi_menit) AS total_durasi,
            CONCAT(
                LPAD(FLOOR(SUM(p.durasi_menit) / 60), 2, '0'),
                ':',
                LPAD(MOD(SUM(p.durasi_menit), 60), 2, '0')
            ) AS durasi_jam_menit,
            ROUND((SUM(p.actual) / NULLIF(SUM(p.plan), 0)) * 100, 2) AS efisiensi_persen
        FROM `tabProduksi` p
        WHERE DATE(p.start) BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY p.part_no
        ORDER BY p.part_no
    """, filters, as_dict=1)

    columns = [
        {"label": "Part No", "fieldname": "part_no", "fieldtype": "Data", "width": 200},
        {"label": "Part Name", "fieldname": "part_item", "fieldtype": "Data", "width": 300},
        {"label": "Lot", "fieldname": "total_lot", "fieldtype": "Int", "width": 60},
        {"label": "Plan", "fieldname": "total_plan", "fieldtype": "Int", "width": 80},
        {"label": "Aktual", "fieldname": "total_aktual", "fieldtype": "Int", "width": 80},
        {"label": "NG", "fieldname": "total_ng", "fieldtype": "Int", "width": 60},
        {"label": "Up Time", "fieldname": "total_up_time", "fieldtype": "Int", "width": 100},
        {"label": "Down Time", "fieldname": "total_down_time", "fieldtype": "Int", "width": 100},
        {"label": "Durasi", "fieldname": "total_durasi", "fieldtype": "Int", "width": 100},
        {"label": "Jam:Menit", "fieldname": "durasi_jam_menit", "fieldtype": "Data", "width": 100},
        {"label": "Efisiensi (%)", "fieldname": "efisiensi_persen", "fieldtype": "Percent", "width": 120},
    ]

    chart = {
        "data": {
            "labels": [d["part_no"] for d in data],
            "datasets": [
                {
                    "name": "Efisiensi",
                    "values": [flt(d["efisiensi_persen"]) for d in data]
                }
            ]
        },
        "type": "bar"
    }

    return columns, data, None, chart
