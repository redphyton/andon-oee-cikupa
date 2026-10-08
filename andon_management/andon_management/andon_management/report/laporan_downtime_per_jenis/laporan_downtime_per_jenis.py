import frappe
from frappe.utils import today, add_days

def execute(filters=None):
    if not filters:
        filters = {}

    filters.setdefault("from_date", add_days(today(), -7))
    filters.setdefault("to_date", today())

    data = frappe.db.sql("""
        SELECT
            d.jenis_downtime,
            COUNT(d.name) AS jumlah_kejadian,
            SUM(d.durasi_downtime_menit) AS total_durasi_menit,
            CONCAT(
                LPAD(FLOOR(SUM(d.durasi_downtime_menit) / 60), 2, '0'),
                ':',
                LPAD(MOD(SUM(d.durasi_downtime_menit), 60), 2, '0')
            ) AS durasi_jam_menit
        FROM
            `tabDowntime Produksi` d
        JOIN
            `tabProduksi` p ON d.parent = p.name
        WHERE
            DATE(p.start) BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY
            d.jenis_downtime
        ORDER BY
            total_durasi_menit DESC
    """, filters, as_dict=1)

    columns = [
        {"label": "Jenis Downtime", "fieldname": "jenis_downtime", "fieldtype": "Data", "width": 180},
        {"label": "Jumlah Kejadian", "fieldname": "jumlah_kejadian", "fieldtype": "Int", "width": 130},
        {"label": "Total Durasi (mnt)", "fieldname": "total_durasi_menit", "fieldtype": "int", "width": 140},
        {"label": "Jam:Menit", "fieldname": "durasi_jam_menit", "fieldtype": "Data", "width": 100},
    ]

    chart = {
        "data": {
            "labels": [row["jenis_downtime"] for row in data],
            "datasets": [
                {
                    "name": "Total Durasi (mnt)",
                    "values": [row["total_durasi_menit"] for row in data]
                }
            ]
        },
        "type": "bar"
    }

    return columns, data, None, chart
