import frappe

def get_context(context):
    data = frappe.get_list("Status Andon OEE",
        fields=[
            "nama_assy", 
            "model", 
            "tujuan", 
            "d_plan", 
            "h_plan", 
            "actual", 
            "balance",
            "jtt",
            "mtt",
            "eff",
            "status_line",
            "info_planning"
        ],
        order_by="modified desc",
        limit=1
    )

    if data:
        context.doc = data[0]
        # Pastikan angka desimal diformat string agar rapi (mirip StringFormat='0.0' di XAML)
        context.doc.jtt_fmt = "{:.1f}".format(context.doc.jtt or 0)
        context.doc.mtt_fmt = "{:.1f}".format(context.doc.mtt or 0)
        context.doc.eff_fmt = "{:.1f}".format(context.doc.eff * 100 or 0)
    else:
        context.doc = {
            "nama_assy": "NO DATA", "model": "-", "tujuan": "-",
            "d_plan": 0, "h_plan": 0, "actual": 0, "balance": 0,
            "jtt": 0, "mtt": 0, "eff": 0, "status_line": "Offline",
            "info_planning": "-",
            "jtt_fmt": "0.0", "mtt_fmt": "0.0", "eff_fmt": "0.0"
        }