import frappe
from frappe.utils import get_first_day, get_last_day, add_days, getdate, nowdate

def get_context(context):
    # 1. Ambil Parameter URL (Hanya Assy)
    args = frappe.form_dict
    assy = args.get('assy', 'STA-01')
    
    # 2. Logika Waktu (Selalu Bulan Berjalan)
    today = getdate(nowdate())
    bulan = today.month
    tahun = today.year

    # 3. Jalankan logic utama
    prepare_data(context, assy, int(bulan), int(tahun))

@frappe.whitelist(allow_guest=True)
def get_updates(assy=None):
    # Fungsi API untuk Realtime Update
    context = frappe._dict()
    
    # Default Assy jika tidak dikirim
    if not assy: 
        assy = 'STA-01'
    
    # Selalu gunakan bulan berjalan untuk data update
    today = getdate(nowdate())
    bulan = today.month
    tahun = today.year
    
    prepare_data(context, assy, int(bulan), int(tahun))
    
    return {
        "rows": context.rows,
        "shift_totals": context.shift_totals
    }

def prepare_data(context, assy, bulan, tahun):
    # 1. SETUP TANGGAL
    try:
        start_date_str = f"{tahun}-{bulan:02d}-01"
        start_date = getdate(start_date_str)
        end_date = getdate(get_last_day(start_date))
        today = getdate(nowdate())
    except Exception:
        today = getdate(nowdate())
        start_date = getdate(get_first_day(today))
        end_date = getdate(get_last_day(today))

    dates = []
    cur = start_date
    while cur <= end_date:
        dates.append({
            "day_num": cur.day,
            "key": cur.strftime("%Y_%m_%d"),
            "is_future": cur > today
        })
        cur = add_days(cur, 1)

    # 2. MASTER URUTAN
    urutan_list = frappe.db.get_all(
        "Data Andon OEE",
        fields=["distinct urutan", "deskripsi"], 
        filters={"nama_assy": assy},
        order_by="urutan asc"
    )

    # 3. DATA TRANSAKSI
    all_data = frappe.db.get_all(
        "Data Andon OEE",
        fields=["tanggal", "urutan", "plan", "actual", "shift"], 
        filters={
            "nama_assy": assy,
            "tanggal": ["between", [start_date, end_date]]
        }
    )

    data_map = {}
    urutan_shift_map = {} 

    for x in all_data:
        d_key = getdate(x["tanggal"]).strftime("%Y_%m_%d")
        map_key = f"{x['urutan']}_{d_key}"
        data_map[map_key] = x
        if x.shift:
            urutan_shift_map[x.urutan] = x.shift

    shift_totals = {} 

    # 4. SUSUN BARIS
    rows = []
    last_known_shift = "UNKNOWN" 

    for u in urutan_list:
        current_shift = urutan_shift_map.get(u.urutan)
        if not current_shift:
            current_shift = last_known_shift
        else:
            last_known_shift = current_shift

        if current_shift not in shift_totals:
            shift_totals[current_shift] = {d['key']: {'plan': 0, 'actual': 0} for d in dates}

        row = {
            "urutan": u.urutan,
            "deskripsi": u.deskripsi or f"Slot {u.urutan}",
            "shift": current_shift
        }
        
        for d in dates:
            key = d["key"]
            if d["is_future"]:
                row[f"plan_{key}"] = ""
                row[f"actual_{key}"] = ""
            else:
                map_key = f"{u.urutan}_{key}"
                item = data_map.get(map_key)
                plan_val = item.plan if item else 0
                actual_val = item.actual if item else 0
                row[f"plan_{key}"] = plan_val
                row[f"actual_{key}"] = actual_val
                shift_totals[current_shift][key]['plan'] += plan_val
                shift_totals[current_shift][key]['actual'] += actual_val
        
        rows.append(row)

    context.dates = dates
    context.rows = rows
    context.shift_totals = shift_totals
    
    month_names = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agt", "Sep", "Okt", "Nov", "Des"]
    context.active_assy = assy
    context.period_label = f"{month_names[bulan]} {tahun}"
    context.title = f"Andon {assy}"