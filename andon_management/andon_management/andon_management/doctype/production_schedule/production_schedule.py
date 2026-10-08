# Copyright (c) 2025, Ivan Co and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import paho.mqtt.client as mqtt
import json
from frappe.utils import now_datetime
from datetime import timedelta



MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883

class ProductionSchedule(Document):
	pass



def publish_mqtt_message(topic, payload):
    """Fungsi untuk mengirim pesan ke broker MQTT."""
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
        client.publish(topic, json.dumps(payload), qos=1)
        client.disconnect()
        print(f"MQTT Published to '{topic}': {payload}")
    except Exception as e:
        print(f"Failed to publish to MQTT: {e}")
        frappe.log_error(f"MQTT Publish Failed: {e}", "Andon API Error")

# ==============================================================================
#  Fungsi API Utama
# ==============================================================================

@frappe.whitelist()
def GetSchedule():
    """
    Dipanggil oleh aplikasi WPF untuk mendapatkan data jadwal produksi.
    Fungsi ini akan mencari jadwal berdasarkan nama_line dan tanggal yang
    ditentukan secara otomatis berdasarkan jam cut-off (06:55:00).
    - Jika dipanggil sebelum 06:55, jadwal yang diambil adalah tanggal kemarin.
    - Jika dipanggil setelah 06:55, jadwal yang diambil adalah tanggal hari ini.
    Kemudian mempublikasikan hasilnya ke topik MQTT.
    """
    try:
        # 1. Ambil nama_line yang dikirim dari aplikasi WPF
        data = frappe.local.form_dict
        nama_line = data.get("nama_line")

        if not nama_line:
            frappe.throw("Parameter 'nama_line' wajib diisi.")

        # 2. Tentukan tanggal efektif berdasarkan jam cut-off
        now = now_datetime()
        cutoff_time = now.replace(hour=6, minute=55, second=0, microsecond=0)

        if now < cutoff_time:
            # Jika waktu saat ini sebelum jam cut-off, gunakan tanggal kemarin
            effective_date = (now - timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            # Jika setelah jam cut-off, gunakan tanggal hari ini
            effective_date = now.strftime('%Y-%m-%d')

        # 3. Cari dokumen Production Schedule yang sesuai
        schedule = frappe.get_list(
            "Production Schedule",
            filters={
                "nama_line": nama_line,
                "tanggal": effective_date, # Menggunakan tanggal yang sudah dihitung
                "completed": 0
            },
            fields=["name", "part_no", "tujuan", "plan", "aktual", "takt_time", "target", "barcode"],
            order_by="urutan asc",  # <--- TAMBAHKAN BARIS INI
            limit=1
        )


        # 4. Siapkan data payload untuk dikirim
        if schedule:
            schedule_data = schedule[0]
            payload = {
                "part_no": schedule_data.get("part_no"),
                "tujuan": schedule_data.get("tujuan"),
                "plan": schedule_data.get("plan"),
                "target": schedule_data.get("target"),
                "barcode": schedule_data.get("barcode"),
                "aktual": schedule_data.get("aktual"),
                "doc_name": schedule_data.get("name"),
                "takt_time": schedule_data.get("takt_time")
            }
        else:
            # Jika tidak ada jadwal, kirim payload default
            payload = {
                "part_no": "-",
                "tujuan": "-",
                "barcode": "",
                "target": 0,
                "plan": 0,
                "aktual": 0,
                "takt_time": 0
            }

        # 5. Publikasikan payload ke topik MQTT
        mqtt_topic = f"schedule/{nama_line}"
        # Pastikan Anda sudah memiliki fungsi publish_mqtt_message
        publish_mqtt_message(mqtt_topic, payload) 
        # frappe.publish_realtime(event="publish_mqtt", message={"topic": mqtt_topic, "payload": payload}) # Alternatif jika menggunakan Frappe event

        # 6. Kembalikan pesan sukses ke aplikasi WPF
        return {
            "status": "success",
            "message": f"Schedule for line '{nama_line}' on {effective_date} has been processed."
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "GetSchedule API Error")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def UpdateActual(args=None):
    """Menambah nilai aktual dan kirim MQTT update"""
    try:
        if args:
            data = args
        else:
            data = frappe.local.form_dict

        nama_line = data.get("nama_line")
        tanggal = data.get("tanggal")
        doc_name = data.get("doc_name")

        if not nama_line or not tanggal:
            frappe.throw("Parameter 'nama_line' dan 'tanggal' wajib diisi.")
        if not doc_name:
            frappe.throw("Parameter 'doc_name' wajib diisi.")

        # 1. Muat dokumen dan update nilai aktual
        doc = frappe.get_doc("Production Schedule", doc_name)
        doc.aktual = (doc.aktual or 0) + 1
        if doc.aktual >= doc.plan:
            doc.completed = 1
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        # 2. Siapkan payload MQTT (sama formatnya seperti GetSchedule)
        payload = {
            "part_no": doc.part_no,
            "tujuan": doc.tujuan,
            "plan": doc.plan,
            "target": doc.target,
            "barcode": doc.barcode,
            "aktual": doc.aktual,
            "doc_name": doc.name,
            "takt_time": doc.takt_time
        }

        mqtt_topic = f"schedule/{nama_line}"
        publish_mqtt_message(mqtt_topic, payload)

        # msg = f"Hello world {payload}"
        # frappe.publish_realtime(
        #         event='msgprint',
        #         message=msg,
        #         user = "Administrator"
        #     )

        message = {
                "mesin": nama_line
        }

            # 2. Panggil fungsi publish_realtime
        frappe.publish_realtime(
                event='UPDATE ANDON',      # Nama event HARUS SAMA PERSIS dengan di JavaScript
                message=message,           # Data yang dikirim dalam format dictionary
                user = "Guest"

                # after_commit=True          # PENTING: Mengirim event HANYA SETELAH
                                           # transaksi database berhasil disimpan.
            )

        frappe.publish_realtime(
                event='UPDATE ANDON',      # Nama event HARUS SAMA PERSIS dengan di JavaScript
                message=message        # Data yang dikirim dalam format dictionary
            
            )
        
        return {
            "status": "success",
            "message": f"Actual count for '{nama_line}' updated to {doc.aktual}."
        }
    

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "UpdateActual API Error")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def UpdateTarget():
    """Memperbarui nilai 'target' pada Production Schedule dan kirim MQTT update."""
    try:
        data = frappe.local.form_dict
        doc_name = data.get("doc_name")
        target = data.get("target")
        nama_line = data.get("nama_line")
        tanggal = data.get("tanggal")

        if not doc_name:
            frappe.throw("Parameter 'doc_name' wajib diisi.")
        if target is None:
            frappe.throw("Parameter 'target' wajib diisi.")

        # 1. Muat dokumen dan update nilai target
        doc = frappe.get_doc("Production Schedule", doc_name)
        doc.target = target
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        # 2. Siapkan payload MQTT (format sama)
        payload = {
            "part_no": doc.part_no,
            "tujuan": doc.tujuan,
            "plan": doc.plan,
            "target": doc.target,
            "barcode": doc.barcode,
            "aktual": doc.aktual,
            "doc_name": doc.name,
            "takt_time": doc.takt_time
        }

        mqtt_topic = f"schedule/{nama_line}"
        publish_mqtt_message(mqtt_topic, payload)

        return {
            "status": "success",
            "message": f"Target for '{doc_name}' updated to {doc.target}."
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "UpdateTarget API Error")
        return {"status": "error", "message": str(e)}
