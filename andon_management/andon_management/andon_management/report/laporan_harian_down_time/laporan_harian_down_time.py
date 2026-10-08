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
            DATE(p.start), d.jenis_downtime
        ORDER BY
            tanggal DESC, d.jenis_downtime ASC
    """, filters, as_dict=1)

    columns = [
        {"label": "Tanggal", "fieldname": "tanggal", "fieldtype": "Date", "width": 100},
        {"label": "Jenis Downtime", "fieldname": "jenis_downtime", "fieldtype": "Data", "width": 180},
        {"label": "Jumlah Kejadian", "fieldname": "jumlah_kejadian", "fieldtype": "Int", "width": 120},
        {"label": "Total Durasi (mnt)", "fieldname": "total_durasi_menit", "fieldtype": "Int", "width": 140},
        {"label": "Jam:Menit", "fieldname": "durasi_jam_menit", "fieldtype": "Data", "width": 100},
    ]

    # Chart per tanggal (total durasi semua downtime jenis digabung)
    chart_data = {}
    for row in data:
        key = row["tanggal"].strftime('%Y-%m-%d')
        chart_data.setdefault(key, 0)
        chart_data[key] += row["total_durasi_menit"]

    chart = {
        "data": {
            "labels": list(chart_data.keys()),
            "datasets": [
                {
                    "name": "Total Durasi Downtime (mnt)",
                    "values": list(chart_data.values())
                }
            ]
        },
        "type": "bar"
    }

    return columns, data, None, chart
