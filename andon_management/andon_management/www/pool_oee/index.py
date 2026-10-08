import frappe

# 1. FUNGSI UNTUK HTTP POLLING (DIPANGGIL OLEH FRAPPE.CALL DI JAVASCRIPT)
@frappe.whitelist(allow_guest=True)
def get_andon_data(assy=None):
    # Ambil parameter dari argumen fungsi ATAU dari URL
    target_assy = assy or frappe.form_dict.get('assy')
    
    filters = {}
    if target_assy:
        filters['nama_assy'] = target_assy

    data = frappe.get_list("Status Andon OEE",
        filters=filters,
        fields=[
            "nama_assy", "model", "tujuan", "d_plan", "h_plan", 
            "actual", "balance", "jtt", "mtt", "eff", "alarm_id",
            "status_line", "info_planning"
        ],
        order_by="modified desc",
        limit=1,
        ignore_permissions=True # PENTING: Agar Guest bisa melihat data
    )

    if data:
        doc = data[0]
        # Pastikan angka desimal diformat string agar rapi
        doc.jtt_fmt = "{:.1f}".format(doc.jtt or 0)
        doc.mtt_fmt = "{:.1f}".format(doc.mtt or 0)
        doc.eff_fmt = "{:.1f}".format((doc.eff * 100) or 0)
        return doc
    else:
        return {
            "nama_assy": "NO DATA", "model": "-", "tujuan": "-", "alarm_id": 0,
            "d_plan": 0, "h_plan": 0, "actual": 0, "balance": 0,
            "jtt": 0, "mtt": 0, "eff": 0, "status_line": "Offline",
            "info_planning": "-",
            "jtt_fmt": "0.0", "mtt_fmt": "0.0", "eff_fmt": "0.0"
        }

# 2. FUNGSI UNTUK LOAD PERTAMA KALI (DIPANGGIL OLEH JINJA/HTML)
def get_context(context):
    # Kita cukup memanggil fungsi get_andon_data() agar kodenya tidak perlu ditulis dua kali
    context.doc = get_andon_data()