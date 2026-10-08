import frappe
from frappe.utils import now_datetime, add_days

def cleanup_old_logs():
    """Delete Log Actual entries older than 7 days"""
    threshold_date = add_days(now_datetime(), -3)
    frappe.logger().info(f"Starting cleanup for Log Actual before {threshold_date}")

    # Jalankan query delete langsung (lebih cepat dari delete_doc)
    deleted_count = frappe.db.sql("""
        DELETE FROM `tabLog Actual`
        WHERE waktu < %s
    """, threshold_date)

    frappe.db.commit()
    frappe.logger().info(f"Deleted {deleted_count[0] if deleted_count else 0} old Log Actual records.")
