import frappe
from frappe.utils import get_first_day, get_last_day, add_days, getdate, nowdate

def get_context(context):
    args = frappe.form_dict
    assy = args.get('assy', 'STA-01')
    
    today_dt = getdate(nowdate())
    # Gunakan parameter URL atau default ke bulan berjalan
    bulan = args.get('bulan', today_dt.month)
    tahun = args.get('tahun', today_dt.year)

    prepare_data(context, assy, int(bulan), int(tahun))

@frappe.whitelist(allow_guest=True)
def get_updates(assy=None, bulan=None, tahun=None):
    context = frappe._dict()
    
    today_dt = getdate(nowdate())
    if not assy: assy = 'STA-01'
    if not bulan: bulan = today_dt.month
    if not tahun: tahun = today_dt.year
    
    prepare_data(context, assy, int(bulan), int(tahun))
    
    return {
        "rows": context.rows,
        "shift_totals": context.shift_totals,
        "charts_by_shift": context.charts_by_shift,
        "chart_labels": context.chart_labels
    }

def prepare_data(context, assy, bulan, tahun):
    # --- 1. SETUP TANGGAL ---
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
        # Logika: Masa depan (Future) adalah tanggal > hari ini
        is_future = cur > today
        dates.append({
            "day_num": cur.day,
            "key": cur.strftime("%Y_%m_%d"),
            "is_future": is_future
        })
        cur = add_days(cur, 1)

    # --- 2. MASTER URUTAN ---
    urutan_list = frappe.db.get_all(
        "Data Andon OEE",
        fields=["distinct urutan", "deskripsi"], 
        filters={"nama_assy": assy},
        order_by="urutan asc"
    )

    # --- 3. DATA TRANSAKSI ---
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

    # --- 4. SUSUN BARIS TABEL (DENGAN FIX SHIFT HILANG) ---
    shift_totals = {} 
    rows = []
    
    # Cache untuk menyimpan info shift dari DB agar tidak query berulang
    master_shift_cache = {}
    last_known_shift = "UNKNOWN" 

    for u in urutan_list:
        # Coba ambil shift dari transaksi bulan ini
        current_shift = urutan_shift_map.get(u.urutan)
        
        # --- FIX UTAMA: JIKA SHIFT TIDAK DITEMUKAN DI BULAN INI ---
        if not current_shift:
            if u.urutan in master_shift_cache:
                current_shift = master_shift_cache[u.urutan]
            else:
                # Cari data terakhir di DB (Mundur ke bulan lalu dst)
                last_entry = frappe.db.get_value("Data Andon OEE", 
                    {"nama_assy": assy, "urutan": u.urutan}, 
                    "shift", 
                    order_by="tanggal desc"
                )
                if last_entry:
                    current_shift = last_entry
                    master_shift_cache[u.urutan] = last_entry
        
        # Jika DB juga kosong (urutan baru), pakai last_known
        current_shift = current_shift or last_known_shift
        last_known_shift = current_shift

        # Init Total Shift
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
                # Masa depan: String Kosong
                row[f"plan_{key}"] = ""
                row[f"actual_{key}"] = ""
            else:
                # Hari ini/Lalu: Angka 0 jika tidak ada data
                map_key = f"{u.urutan}_{key}"
                item = data_map.get(map_key)
                
                plan_val = item.plan if item else 0
                actual_val = item.actual if item else 0
                
                row[f"plan_{key}"] = plan_val
                row[f"actual_{key}"] = actual_val
                
                shift_totals[current_shift][key]['plan'] += plan_val
                shift_totals[current_shift][key]['actual'] += actual_val
        
        rows.append(row)

    # --- 5. DATA CHART PER SHIFT ---
    charts_by_shift = {}
    
    for shift_name in sorted(shift_totals.keys()):
        daily_actual = []
        cum_plan = []
        cum_actual = []
        
        running_p = 0
        running_a = 0
        
        shift_data_dates = shift_totals[shift_name]

        for d in dates:
            if not d["is_future"]:
                val = shift_data_dates[d['key']]
                p_day = val['plan']
                a_day = val['actual']

                running_p += p_day
                running_a += a_day

                daily_actual.append(a_day)
                cum_plan.append(running_p)
                cum_actual.append(running_a)
            else:
                # Chart tidak digambar untuk masa depan
                daily_actual.append(None)
                cum_plan.append(None)
                cum_actual.append(None)
        
        charts_by_shift[shift_name] = {
            "daily_actual": daily_actual,
            "cum_plan": cum_plan,
            "cum_actual": cum_actual
        }

    context.dates = dates
    context.rows = rows
    context.shift_totals = shift_totals
    context.charts_by_shift = charts_by_shift
    context.chart_labels = [d['day_num'] for d in dates]
    
    month_names = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agt", "Sep", "Okt", "Nov", "Des"]
    context.active_assy = assy
    context.period_label = f"{month_names[bulan]} {tahun}"
    context.title = f"Andon {assy}"