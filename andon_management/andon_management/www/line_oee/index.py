import frappe

def get_context(context):

    # 1. Ambil parameter 'assy' dari URL
    # Contoh URL: yoursite.com/andon?assy=STA-02
    target_assy = frappe.form_dict.get('assy', '10-D').upper()    
    filters = {}
    
    # 2. Jika ada parameter, tambahkan ke filter
    if target_assy:
        filters['nama_assy'] = target_assy

    data = frappe.get_list("Status Andon OEE",
        filters=filters,  # <--- Filter diterapkan di sini        
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
            "alarm_id",
            "status_line",
            "info_planning"
        ],
        order_by="modified desc",
        limit=1,
        ignore_permissions=True # PENTING: Agar Guest bisa melihat data
    )

    if data:
        context.doc = data[0]
        # Pastikan angka desimal diformat string agar rapi (mirip StringFormat='0.0' di XAML)
        context.doc.jtt_fmt = "{:.1f}".format(context.doc.jtt or 0)
        context.doc.mtt_fmt = "{:.1f}".format(context.doc.mtt or 0)
        context.doc.eff_fmt = "{:.1f}".format(context.doc.eff * 100 or 0)
    else:
        context.doc = {
            "nama_assy": "NO DATA", "model": "-", "tujuan": "-","alarm_id":0,
            "d_plan": 0, "h_plan": 0, "actual": 0, "balance": 0,
            "jtt": 0, "mtt": 0, "eff": 0, "status_line": "Offline",
            "info_planning": "-",
            "jtt_fmt": "0.0", "mtt_fmt": "0.0", "eff_fmt": "0.0"
        }