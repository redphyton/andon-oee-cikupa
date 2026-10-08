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
        "charts_by_shift": context.charts_by_shift, # Mengembalikan multi chart
        "chart_labels": context.chart_labels
    }

# --- Tambahkan Helper Function ini di dalam prepare_data atau di tataran module ---

def get_sort_weight(shift_str, urutan_id, deskripsi_text):
    """
    Mengubah deskripsi waktu menjadi angka agar bisa diurutkan secara logika produksi.
    Logika: Production Day mulai jam 07:00. 
    Jam 00:00 - 06:59 dianggap jam 24:00 - 30:59.
    """
    # 1. Tentukan Prioritas Shift (Agar Shift 1 tampil duluan, lalu 2, lalu 3)
    shift_priority = {'1': 10, '2': 20, '3': 30}.get(str(shift_str), 99)
    
    # 2. Parsing Jam Awal dari Deskripsi (Contoh: "23.00 - 00.00")
    try:
        # Ambil bagian depan sebelum tanda "-"
        start_time_str = deskripsi_text.split('-')[0].strip() # "23.00"
        
        # Pisahkan Jam dan Menit
        if '.' in start_time_str:
            h, m = map(int, start_time_str.split('.'))
        elif ':' in start_time_str:
            h, m = map(int, start_time_str.split(':'))
        else:
            h, m = 0, 0
            
        # --- LOGIKA KUNCI: HANDLING MIDNIGHT ---
        # Jika jam < 7 pagi, tambahkan 24 jam.
        # Contoh: Jam 00.35 menjadi 24.35 (Nilainya lebih besar dari 23.00)
        if str(shift_str) == '1':
            if h < 6:
                h += 24
        else:
            if h < 7:
                h += 24
            
        time_value = (h * 60) + m
    except:
        # Jika deskripsi tidak punya format jam (misal "Lunch"), gunakan urutan ID
        time_value = urutan_id

    # Kembalikan tuple: (Kelompok Shift, Nilai Waktu)
    return (shift_priority, time_value)

def prepare_data(context, assy, bulan, tahun):
    # --- 1. SETUP TANGGAL (SAMA SEPERTI SEBELUMNYA) ---
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

    # --- 2. MASTER URUTAN (Definisi Slot Waktu & Deskripsi) ---
    # Kita ambil ini untuk referensi deskripsi & urutan standar
    master_list = frappe.db.get_all(
        "Data Andon OEE",
        fields=["urutan", "deskripsi", "shift"], 
        filters={"nama_assy": assy},
        order_by="urutan asc",
        distinct=1 # Gunakan parameter ini untuk distinct
    )
    
    # Dictionary untuk lookup deskripsi berdasarkan urutan
    # Format: { 28: "06.00 - 07.00", ... }
    deskripsi_map = {m.urutan: m.deskripsi for m in master_list}
    
    # --- 3. DATA TRANSAKSI ---
    all_data = frappe.db.get_all(
        "Data Andon OEE",
        fields=["tanggal", "urutan", "plan", "actual", "shift"], 
        filters={
            "nama_assy": assy,
            "tanggal": ["between", [start_date, end_date]] 
        }
    )

    # Mapping Data Transaksi
    # Kunci utamanya sekarang menyertakan SHIFT agar unik
    # Format Key: "SHIFT_URUTAN_TANGGAL" -> "1_28_2026_01_22"
    data_map = {}
    
    # Kita perlu mencatat semua kombinasi (Shift, Urutan) yang unik yang muncul
    # Gunakan Set agar tidak ada duplikat
    active_row_keys = set()

    for x in all_data:
        # Skip jika data korup (tidak ada shift/urutan)
        if not x.shift or not x.urutan: continue

        d_key = getdate(x["tanggal"]).strftime("%Y_%m_%d")
        
        # Simpan data transaksi
        map_key = f"{x['shift']}_{x['urutan']}_{d_key}"
        data_map[map_key] = x

        # Catat bahwa kombinasi Shift & Urutan ini ADA di database
        active_row_keys.add((str(x.shift), int(x.urutan)))

    # (Opsional) Tambahkan Master Data ke active_row_keys 
    # agar baris tetap muncul meskipun BELUM ada data transaksi bulan ini
    for m in master_list:
        if m.shift and m.urutan:
            active_row_keys.add((str(m.shift), int(m.urutan)))

    # --- 4. SUSUN BARIS TABEL ---


    # PENTING: Ubah logic sorting di sini
    sorted_keys = sorted(
        list(active_row_keys), 
        key=lambda k: get_sort_weight(k[0], k[1], deskripsi_map.get(k[1], ""))
    )

    shift_totals = {} 
    rows = []

    for (s_shift, s_urutan) in sorted_keys:
        # Inisialisasi total jika shift baru
        if s_shift not in shift_totals:
            shift_totals[s_shift] = {d['key']: {'plan': 0, 'actual': 0} for d in dates}

        # Ambil deskripsi dari map (atau default string jika hilang)
        desc = deskripsi_map.get(s_urutan, f"Slot {s_urutan}")

        row = {
            "urutan": s_urutan,
            "deskripsi": desc,
            "shift": s_shift
        }

        # Loop per Tanggal
        for d in dates:
            key = d["key"]
            # Kunci pencarian spesifik: Shift + Urutan + Tanggal
            map_key = f"{s_shift}_{s_urutan}_{key}"
            
            item = data_map.get(map_key)

            plan_val = item.plan if item else 0
            actual_val = item.actual if item else 0

            # Masukkan ke row
            row[f"plan_{key}"] = plan_val
            row[f"actual_{key}"] = actual_val

            # Tambahkan ke total Shift yang sesuai
            shift_totals[s_shift][key]['plan'] += plan_val
            shift_totals[s_shift][key]['actual'] += actual_val

        rows.append(row)

    # --- 5. DATA CHART PER SHIFT (SAMA SEPERTI SEBELUMNYA) ---
    charts_by_shift = {}
    
    # Sort shift keys agar urut 1, 2, 3 di grafik
    for shift_name in sorted(shift_totals.keys()):
        daily_actual = []
        cum_plan = []
        cum_actual = []
        
        running_p = 0
        running_a = 0
        
        shift_data_dates = shift_totals[shift_name]

        for d in dates:
            val = shift_data_dates[d['key']]
            p_day = val['plan']
            a_day = val['actual']

            running_p += p_day
            running_a += a_day

            daily_actual.append(a_day)
            cum_plan.append(running_p)
            cum_actual.append(running_a)
        
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