import frappe
from frappe.utils import today, add_days

def execute(filters=None):
    if not filters:
        filters = {}

    filters.setdefault("from_date", add_days(today(), -7))
    filters.setdefault("to_date", today())

    data = frappe.db.sql("""
        SELECT
            DATE(p.start) AS tanggal,
            COUNT(p.name) AS total_lot,
            SUM(p.plan) AS total_plan,
            SUM(p.actual) AS total_aktual,
            SUM(p.ng) AS total_ng,
            SUM(p.up_time_menit) AS total_up_time,
            CONCAT(
                LPAD(FLOOR(SUM(p.up_time_menit) / 60), 2, '0'),
                ':',
                LPAD(MOD(SUM(p.up_time_menit), 60), 2, '0')
            ) AS total_up_time_jam_menit,
            SUM(p.downtime_menit) AS total_down_time,
            CONCAT(
                LPAD(FLOOR(SUM(p.downtime_menit) / 60), 2, '0'),
                ':',
                LPAD(MOD(SUM(p.downtime_menit), 60), 2, '0')
            ) AS total_down_time_jam_menit,
            SUM(p.durasi_menit) AS total_durasi,
            CONCAT(
                LPAD(FLOOR(SUM(p.durasi_menit) / 60), 2, '0'),
                ':',
                LPAD(MOD(SUM(p.durasi_menit), 60), 2, '0')
            ) AS durasi_jam_menit,
            ROUND((SUM(p.actual) / NULLIF(SUM(p.plan), 0)) * 100, 2) AS efisiensi_persen
        FROM `tabProduksi` p
        WHERE DATE(p.start) BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY DATE(p.start)
        ORDER BY tanggal DESC
    """, filters, as_dict=1)

    columns = [
        {"label": "Tanggal", "fieldname": "tanggal", "fieldtype": "Date", "width": 120},
        {"label": "Total Lot", "fieldname": "total_lot", "fieldtype": "Int", "width": 90},
        {"label": "Total Plan", "fieldname": "total_plan", "fieldtype": "Int", "width": 100},
        {"label": "Total Aktual", "fieldname": "total_aktual", "fieldtype": "Int", "width": 100},
        {"label": "Total NG", "fieldname": "total_ng", "fieldtype": "Int", "width": 90},
        {"label": "Up Time", "fieldname": "total_up_time", "fieldtype": "Int", "width": 90},
        {"label": "Up Time (J:M)", "fieldname": "total_up_time_jam_menit", "fieldtype": "Data", "width": 100},
        {"label": "Down Time", "fieldname": "total_down_time", "fieldtype": "Int", "width": 90},
        {"label": "Down Time (J:M)", "fieldname": "total_down_time_jam_menit", "fieldtype": "Data", "width": 100},
        {"label": "Durasi", "fieldname": "total_durasi", "fieldtype": "Int", "width": 90},
        {"label": "Durasi (J:M)", "fieldname": "durasi_jam_menit", "fieldtype": "Data", "width": 100},
        {"label": "Efisiensi (%)", "fieldname": "efisiensi_persen", "fieldtype": "Percent", "width": 120}
    ]

    chart = {
        "data": {
            "labels": [row["tanggal"].strftime('%Y-%m-%d') for row in data],
            "datasets": [
                {
                    "name": "Efisiensi (%)",
                    "values": [row["efisiensi_persen"] for row in data]
                }
            ]
        },
        "type": "bar"
    }

    return columns, data, None, chart
