frappe.query_reports["Laporan Produksi per Part"] = {
    filters: [
        {
            fieldname: "from_date",
            label: "Dari",
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -7),
            reqd: 1
        },
        {
            fieldname: "to_date",
            label: "Sampai",
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1
        }
    ]
};
