import frappe
from frappe.utils import get_first_day, get_last_day, add_days, getdate, nowdate

def get_context(context):
    args = frappe.form_dict
    assy = args.get('assy', 'STA-01')
    
    today_dt = getdate(nowdate())
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
    while cur <= end_date and cur <= today:
        dates.append({
            "day_num": cur.day,
            "key": cur.strftime("%Y_%m_%d")
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
    
    # Mapping: Urutan X muncul di shift mana saja bulan ini?
    # Contoh Hasil: {'27': {'1', '3'}, '26': {'1'}}
    # Artinya Urutan 27 muncul di Shift 1 DAN Shift 3.
    urutan_active_shifts = {} 
    
    for x in all_data:
        d_key = getdate(x["tanggal"]).strftime("%Y_%m_%d")
        map_key = f"{x['urutan']}_{d_key}"
        data_map[map_key] = x
        
        if x.shift:
            u_str = str(x.urutan)
            s_str = str(x.shift)
            if u_str not in urutan_active_shifts:
                urutan_active_shifts[u_str] = set()
            urutan_active_shifts[u_str].add(s_str)

    # --- 4. SUSUN BARIS TABEL (LOGIKA PECAL SLOT PER SHIFT) ---
    shift_totals = {}
    rows = []
    master_shift_cache = {}
    last_known_shift = "UNKNOWN" 

    for u in urutan_list:
        u_str = str(u.urutan)
        
        # Ambil daftar shift yang aktif untuk urutan ini bulan ini
        shifts_to_render = urutan_active_shifts.get(u_str, set())
        
        # KASUS: Jika bulan ini BELUM ada data sama sekali untuk urutan ini (misal awal bulan)
        # Kita harus tetap menampilkannya, cari data histori shift terakhirnya
        if not shifts_to_render:
            fallback_shift = None
            if u_str in master_shift_cache:
                fallback_shift = master_shift_cache[u_str]
            else:
                last_entry = frappe.db.get_value("Data Andon OEE", 
                    {"nama_assy": assy, "urutan": u.urutan}, 
                    "shift", 
                    order_by="tanggal desc"
                )
                if last_entry:
                    fallback_shift = str(last_entry)
                    master_shift_cache[u_str] = fallback_shift
            
            # Jika masih tidak ketemu, pakai shift terakhir yg diketahui dr loop sebelumnya
            fallback_shift = fallback_shift or last_known_shift
            shifts_to_render.add(fallback_shift)

        # Update last_known_shift agar urutan berikutnya yang kosong bisa ngikut
        if shifts_to_render:
             last_known_shift = list(shifts_to_render)[0]

        # --- CORE LOGIC: MEMBUAT BARIS SESUAI JUMLAH SHIFT ---
        # Jika Urutan 27 ada di Shift 1 dan 3, loop ini jalan 2x.
        for s_render in shifts_to_render:
            
            # Pastikan wadah total shift tersedia
            if s_render not in shift_totals:
                shift_totals[s_render] = {d['key']: {'plan': 0, 'actual': 0} for d in dates}

            row = {
                "urutan": u.urutan,
                "deskripsi": u.deskripsi or f"Slot {u.urutan}",
                "shift": s_render # Kunci: Baris ini didefinisikan milik Shift ini
            }
            
            for d in dates:
                key = d["key"]
                map_key = f"{u.urutan}_{key}"
                item = data_map.get(map_key)
                
                plan_val = 0
                actual_val = 0
                
                # --- FILTER DATA ---
                # Hanya masukkan data ke sel jika shift transaksi SAMA dengan shift baris ini
                if item:
                    # Jika data tidak punya shift (jarang terjadi), anggap sama dengan baris
                    item_shift = str(item.shift) if item.shift else s_render
                    
                    if item_shift == s_render:
                        # MATCH! Data tanggal 17 (Shift 3) masuk ke baris Shift 3
                        # Data tanggal 22 (Shift 1) masuk ke baris Shift 1
                        plan_val = item.plan
                        actual_val = item.actual
                
                row[f"plan_{key}"] = plan_val
                row[f"actual_{key}"] = actual_val
                
                shift_totals[s_render][key]['plan'] += plan_val
                shift_totals[s_render][key]['actual'] += actual_val
            
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
            val = shift_data_dates[d['key']]
            running_p += val['plan']
            running_a += val['actual']
            daily_actual.append(val['actual'])
            cum_plan.append(running_p)
            cum_actual.append(running_a)
        
        charts_by_shift[shift_name] = {
            "daily_actual": daily_actual,
            "cum_plan": cum_plan,
            "cum_actual": cum_actual
        }

    # --- 6. FINAL SORTING ---
    # 1. Urutkan berdasarkan SHIFT (Agar Shift 1 di atas, Shift 3 di bawah)
    # 2. Urutkan berdasarkan DESKRIPSI (Agar 05.15 di atas 07.00)
    
    def sort_rows_logic(r):
        s = str(r['shift'])
        d = r['deskripsi'] or ""
        return (s, d)

    rows.sort(key=sort_rows_logic)

    context.dates = dates
    context.rows = rows
    context.shift_totals = shift_totals
    context.charts_by_shift = charts_by_shift
    context.chart_labels = [d['day_num'] for d in dates]
    
    month_names = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agt", "Sep", "Okt", "Nov", "Des"]
    context.active_assy = assy
    context.period_label = f"{month_names[bulan]} {tahun}"
    context.title = f"Andon {assy}"