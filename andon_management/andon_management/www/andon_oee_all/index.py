import frappe
from frappe.utils import get_first_day, get_last_day, add_days, getdate, nowdate

def get_context(context):
    args = frappe.form_dict
    today_dt = getdate(nowdate())
    bulan = args.get('bulan', today_dt.month)
    tahun = args.get('tahun', today_dt.year)
    prepare_data(context, int(bulan), int(tahun))

@frappe.whitelist(allow_guest=True)
def get_updates(bulan=None, tahun=None):
    context = frappe._dict()
    today_dt = getdate(nowdate())
    if not bulan: bulan = today_dt.month
    if not tahun: tahun = today_dt.year
    prepare_data(context, int(bulan), int(tahun))
    
    return {
        "rows": context.rows,
        "shift_totals": context.shift_totals,
        "charts_by_shift": context.charts_by_shift,
        "chart_labels": context.chart_labels
    }

def get_sort_weight(shift_str, mulai_val):
    """
    Sortir langsung membaca dari field Jam Mulai (misal: "12:45:00")
    bukan lagi dari teks deskripsi. Ini jauh lebih akurat.
    """
    shift_priority = {'1': 10, '2': 20, '3': 30}.get(str(shift_str), 99)
    try:
        time_str = str(mulai_val)
        h, m, s = map(int, time_str.split(':'))
        
        # Logika melewati tengah malam
        if str(shift_str) == '1':
            if h < 6: h += 24
        else:
            if h < 7: h += 24
            
        time_value = (h * 60) + m
    except:
        time_value = 9999
        
    return (shift_priority, time_value)

def prepare_data(context, bulan, tahun):
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

    # 1. AMBIL TRANSAKSI (Filter Assy dihapus, field mulai & selesai ditambahkan)
    all_data = frappe.db.get_all(
        "Data Andon OEE",
        fields=["tanggal", "plan", "actual", "shift", "mulai", "selesai", "deskripsi"], 
        filters={
            "tanggal": ["between", [start_date, end_date]] 
        }
    )

    data_map = {}
    active_row_keys = set()
    deskripsi_map = {}

    for x in all_data:
        # Abaikan jika data korup (tidak ada shift, mulai, atau selesai)
        if not x.shift or x.mulai is None or x.selesai is None: 
            continue
            
        s_shift = str(x.shift)
        s_mulai = str(x.mulai)
        s_selesai = str(x.selesai)
        
        d_key = getdate(x["tanggal"]).strftime("%Y_%m_%d")
        
        # KEY GROUPING BARU: Shift + Jam Mulai + Jam Selesai
        row_key = f"{s_shift}_{s_mulai}_{s_selesai}"
        cell_key = f"{row_key}_{d_key}"
        
        # Jumlahkan (Akumulasi) nilai plan dan actual untuk waktu yang sama
        if cell_key not in data_map:
            data_map[cell_key] = {"plan": 0, "actual": 0}
            
        data_map[cell_key]["plan"] += (x.plan or 0)
        data_map[cell_key]["actual"] += (x.actual or 0)

        # Daftarkan kombinasi waktu ini agar dibuatkan baris
        active_row_keys.add((s_shift, s_mulai, s_selesai))
        
        if row_key not in deskripsi_map:
            deskripsi_map[row_key] = x.deskripsi or f"{s_mulai} - {s_selesai}"

    # 2. SORTING BERDASARKAN JAM MULAI
    sorted_keys = sorted(
        list(active_row_keys), 
        key=lambda k: get_sort_weight(k[0], k[1])
    )

    shift_totals = {} 
    rows = []

    # 3. SUSUN BARIS TABEL
    # enumerate digunakan untuk membuat nomor urut dinamis (idx) pengganti 'urutan'
    for idx, (s_shift, s_mulai, s_selesai) in enumerate(sorted_keys):
        if s_shift not in shift_totals:
            shift_totals[s_shift] = {d['key']: {'plan': 0, 'actual': 0} for d in dates}

        row_key = f"{s_shift}_{s_mulai}_{s_selesai}"
        desc = deskripsi_map.get(row_key, f"{s_mulai} - {s_selesai}")

        row = {
            "urutan": idx + 1,  # ID ini dikirim ke HTML agar target sel JavaScript tidak eror
            "deskripsi": desc,
            "shift": s_shift
        }

        for d in dates:
            key = d["key"]
            cell_key = f"{row_key}_{key}"
            
            item = data_map.get(cell_key)

            plan_val = item["plan"] if item else 0
            actual_val = item["actual"] if item else 0

            row[f"plan_{key}"] = plan_val
            row[f"actual_{key}"] = actual_val

            shift_totals[s_shift][key]['plan'] += plan_val
            shift_totals[s_shift][key]['actual'] += actual_val

        rows.append(row)

    # 4. DATA CHART
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
    
    context.active_assy = "ALL ASSY"
    context.period_label = f"{month_names[bulan]} {tahun}"
    context.title = "Andon ALL ASSY"