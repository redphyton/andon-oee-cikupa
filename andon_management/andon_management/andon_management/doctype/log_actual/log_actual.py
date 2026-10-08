# Copyright (c) 2025, ivan co and contributors
# For license information, please see license.txt


import frappe
from frappe.utils import (
    get_time,
    getdate,
    time_diff_in_seconds,
    now_datetime,
    add_days,
    cint
)
from frappe.model.document import Document
from datetime import datetime, time
import paho.mqtt.client as mqtt
import json

MQTT_BROKER = "localhost"
MQTT_PORT = 1883

class LogActual(Document):
    def validate(self):
        self.notes = "BEFORE SAVE"

        # ambil waktu log, default ke sekarang kalau kosong
        log_time = self.waktu or now_datetime()
        time_only = get_time(log_time)
        log_date = getdate(log_time)

        # ambil patokan start_time dari slot pertama (misalnya name = "1")
        first_slot = frappe.db.get_value("Production Time Slot", "1", "start_time")
        if first_slot:
            first_slot_time = get_time(first_slot)
            if time_only < first_slot_time:
                log_date = add_days(log_date, -1)

        # cari slot yang sesuai
        slot = frappe.db.sql("""
            SELECT name, description, shift, start_time, end_time
            FROM `tabProduction Time Slot`
            WHERE start_time <= %s AND end_time >= %s
            LIMIT 1
        """, (time_only, time_only), as_dict=True)

        if slot:
            self.notes = f"{log_date.strftime('%d-%m-%Y')} {slot[0].description}"

    def before_insert(self):
        pass
        # Hapus log yang lebih lama dari 45 hari
        # threshold_date = add_days(now_datetime(), -7)
        # old_logs = frappe.get_all(
        #     "Log Actual",
        #     filters={"waktu": ["<", threshold_date]},
        #     pluck="name"
        # )
        # for log_name in old_logs:
        #     try:
        #         frappe.delete_doc("Log Actual", log_name, force=1, ignore_permissions=True)
        #     except Exception as e:
        #         frappe.log_error(f"Error deleting old Log Actual {log_name}: {e}")

    def to_time(self, value):
        """Konversi berbagai tipe (str, timedelta, dll) ke datetime.time"""
        if isinstance(value, time):
            return value
        if isinstance(value, str):
            return get_time(value)
        try:
            seconds = int(value.total_seconds())
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return time(hours % 24, minutes, seconds)
        except Exception:
            return None
        

    def after_insert(self):
        # ambil waktu log
        log_time = self.waktu
        time_only = get_time(log_time)
        log_date = getdate(log_time)
        schedule_name = ""
        if len (self.part_no) < 1:
            part = frappe.get_all(
                "Production Schedule",
                    filters={
                "nama_line": self.mesin,
                "tanggal": log_date,
                "completed": 0
            },
            fields=["part_no","aktual","name"],
            order_by="urutan asc",
            limit=1
            )
            if part:
                self.part_no = part[0].part_no
                schedule_name = part[0].name
            else:
                self.part_no = "UNDEF"

            
            
            # if frappe.db.exists("Production Schedule", schedule_name):
            #     schedule_doc = frappe.get_doc("Production Schedule", schedule_name)
            #     schedule_doc.aktual = cint(schedule_doc.aktual) + 1
            #     if (schedule_doc.aktual >= schedule_doc.plan):
            #         schedule_doc.completed = 1
            #     schedule_doc.save(ignore_permissions=True)
################
            # msg = f"Hello world {schedule_name}"
            # frappe.publish_realtime(
            #     event='msgprint',
            #     message=msg,
            #     user = "Administrator"
            # )


            # mqtt_topic ="frappe/todo"
            # try:
            #     client = mqtt.Client()
            #     client.connect(MQTT_BROKER, MQTT_PORT, 60)

            #     payload = {

            #         "name": msg
            
            #     }
            #     client.publish(mqtt_topic, json.dumps(payload))
            #     client.disconnect()

            # except Exception as e:
            #     frappe.log_error(f"Gagal mempublikasikan ke MQTT: {e}")
########################


#            return



        # cek patokan slot pertama (misal slot name=1)
        first_slot = frappe.db.get_value("Production Time Slot", "1", "start_time")
        if first_slot:
            first_slot_time = get_time(first_slot)
            if time_only < first_slot_time:
                log_date = add_days(log_date, -1)

        # cari slot yang sesuai
        slot = frappe.db.sql("""
            SELECT name, description, shift, plan_start_time, start_time, end_time, durasi
            FROM `tabProduction Time Slot`
            WHERE start_time <= %s AND end_time >= %s
            LIMIT 1
        """, (time_only, time_only), as_dict=True)

        if not slot:
            return

        slot = slot[0]

        # tentukan slot_start & slot_end (datetime)
        log_date_ori = getdate(log_time)

        slot_start = datetime.combine(log_date_ori, self.to_time(slot.plan_start_time))
        slot_end = datetime.combine(log_date_ori, self.to_time(slot.end_time))

        # cari record terakhir di slot ini
        last_summary = frappe.get_all(
            "Production Slot Summary",
            filters={
                "tanggal": log_date,
                "mesin": self.mesin,
                "slot": slot.name
            },
            order_by="creation desc",
            limit=1
        )


        # cycle_time = frappe.db.get_value("Master Part", self.part_no, "takt_time")
        if frappe.db.exists("Master Part", self.part_no):
            cycle_time = frappe.db.get_value("Master Part", self.part_no, "takt_time") or 1
        else:
            new_part = frappe.get_doc({
                "doctype": "Master Part",
                "name": self.part_no,
                "part_no": self.part_no,
                "takt_time": 1
            })
            new_part.insert(ignore_permissions=True)
            cycle_time = 1

        plan_qty = 0

        if last_summary:
            last_doc = frappe.get_doc("Production Slot Summary", last_summary[0].name)

            if last_doc.part_no == self.part_no:
                # 🚀 part sama → update qty saja
                last_doc.actual_qty = cint(last_doc.actual_qty) + 1
                # last_doc.production_end = log_time

                if cycle_time and last_doc.production_start:
                    duration = time_diff_in_seconds(last_doc.production_end, last_doc.production_start)
                    last_doc.plan_qty = int(duration // cycle_time)

                last_doc.save(ignore_permissions=True)

                # if frappe.db.exists("Production Schedule", schedule_name):
                #     schedule_doc = frappe.get_doc("Production Schedule", schedule_name)
                #     schedule_doc.aktual = cint(schedule_doc.aktual) + 1
                #     if (schedule_doc.aktual >= schedule_doc.plan):
                #         schedule_doc.completed = 1
                #     schedule_doc.save(ignore_permissions=True)

                
                if schedule_name:
                    try:
                        frappe.call("andon_management.andon_management.doctype.production_schedule.production_schedule.UpdateActual",
                            { "doc_name" : schedule_name,
                            "nama_line": self.mesin,
                            "tanggal": log_date.strftime("%Y-%m-%d")
                            }
                        )
                    except Exception as e:
                        frappe.log_error(f"Gagal memanggil UpdateActual untuk {schedule_name}: {e}")        
                

                return
            else:
                # 🚀 part berbeda → tutup record lama, lalu buat baru
                # last_doc.production_end = log_time
                # if last_doc.part_no:
                #     prev_cycle = frappe.db.get_value("Master Part", last_doc.part_no, "takt_time")
                #     if prev_cycle:
                #         duration = time_diff_in_seconds(last_doc.production_end, last_doc.production_start)
                #         last_doc.plan_qty = int(duration // prev_cycle)
                # last_doc.save(ignore_permissions=True)
                # 🚀 part berbeda → tutup record lama, lalu buat baru
                last_doc.production_end = log_time

                if last_doc.part_no:
                    if frappe.db.exists("Master Part", last_doc.part_no):
                        prev_cycle = frappe.db.get_value("Master Part", last_doc.part_no, "takt_time") or 1
                    else:
                        new_part = frappe.get_doc({
                            "doctype": "Master Part",
                            "name": last_doc.part_no,
                            "part_no": last_doc.part_no,
                            "takt_time": 1
                        })
                        new_part.insert(ignore_permissions=True)
                        prev_cycle = 1

                    duration = time_diff_in_seconds(last_doc.production_end, last_doc.production_start)
                    last_doc.plan_qty = int(duration // prev_cycle)

                last_doc.save(ignore_permissions=True)

                production_start = log_time
                production_end = slot_end
        else:
            # slot kosong → buat record pertama
            production_start = slot_start
            production_end = slot_end

        if cycle_time:
            duration = time_diff_in_seconds(production_end, production_start)
            plan_qty = int(duration // cycle_time)
        else:
            cycle_time = 1;
            

        # 🚀 buat record baru untuk part yang berbeda
        summary = frappe.get_doc({
            "doctype": "Production Slot Summary",
            "tanggal": log_date,
            "mesin": self.mesin,
            "slot": slot.name,
            "deskripsi_slot": slot.description,
            "shift": slot.shift,
            "part_no": self.part_no,
            "slot_start": slot_start,
            "slot_end": slot_end,
            "takt_time": cycle_time,
            "production_start": production_start,
            "production_end": production_end,
            "plan_qty": plan_qty,
            "actual_qty": 1
        })
        summary.insert(ignore_permissions=True)
        # if frappe.db.exists("Production Schedule", schedule_name):
        #     schedule_doc = frappe.get_doc("Production Schedule", schedule_name)
        #     schedule_doc.aktual = cint(schedule_doc.aktual) + 1
        #     if (schedule_doc.aktual >= schedule_doc.plan):
        #         schedule_doc.completed = 1
        #     schedule_doc.save(ignore_permissions=True)
        

# 🔁 Update nilai aktual lewat API resmi


        if schedule_name:
            try:
                frappe.call("andon_management.andon_management.doctype.production_schedule.production_schedule.UpdateActual",
                            { "doc_name" : schedule_name,
                    "nama_line": self.mesin,
                    "tanggal": log_date.strftime("%Y-%m-%d")
                }
            )
            except Exception as e:
                frappe.log_error(f"Gagal memanggil UpdateActual untuk {schedule_name}: {e}")        
