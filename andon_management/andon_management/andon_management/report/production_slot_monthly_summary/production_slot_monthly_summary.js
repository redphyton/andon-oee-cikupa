// Copyright (c) 2025, Ivan Co and contributors
// For license information, please see license.txt


frappe.query_reports["Production Slot Monthly Summary"] = {
    filters: [
        {
            fieldname: "year",
            label: __("Year"),
            fieldtype: "Int",
            default: new Date().getFullYear(),
            reqd: 1
        },
        {
            fieldname: "month",
            label: __("Month"),
            fieldtype: "Int",
            default: new Date().getMonth() + 1,
            reqd: 1
        },
        {
            fieldname: "mesin",
            label: __("Mesin"),
            fieldtype: "Link",
			options: "Shop Floor",
            reqd: 0
        }
    ],
};
