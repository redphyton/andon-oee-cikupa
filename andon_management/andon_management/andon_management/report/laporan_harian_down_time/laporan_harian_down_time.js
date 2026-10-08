frappe.query_reports["Laporan Harian Downtime"] = {
    filters: [
        {
            fieldname: "from_date",
            label: "Dari Tanggal",
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -7),
            reqd: 1
        },
        {
            fieldname: "to_date",
            label: "Sampai Tanggal",
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1
        }
    ]
};
