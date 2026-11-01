import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ROLES = ("Booking Ops User", "Booking Ops Manager")

SO_FIELDS = {
	"Sales Order": [
		{
			"fieldname": "beds24_section",
			"fieldtype": "Section Break",
			"label": "Beds24",
			"insert_after": "po_date",
			"collapsible": 1,
			"depends_on": "eval:doc.beds24_booking",
		},
		{
			"fieldname": "beds24_booking",
			"fieldtype": "Link",
			"label": "Beds24 Booking",
			"options": "Beds24 Booking",
			"insert_after": "beds24_section",
			"read_only": 1,
			"no_copy": 1,
			"search_index": 1,
		},
		{"fieldname": "beds24_guest", "fieldtype": "Data", "label": "Tamu", "insert_after": "beds24_booking", "read_only": 1, "no_copy": 1},
		{"fieldname": "beds24_channel", "fieldtype": "Data", "label": "Channel", "insert_after": "beds24_guest", "read_only": 1, "no_copy": 1},
		{"fieldname": "beds24_col", "fieldtype": "Column Break", "insert_after": "beds24_channel"},
		{"fieldname": "beds24_arrival", "fieldtype": "Date", "label": "Kedatangan", "insert_after": "beds24_col", "read_only": 1, "no_copy": 1},
		{"fieldname": "beds24_departure", "fieldtype": "Date", "label": "Keberangkatan", "insert_after": "beds24_arrival", "read_only": 1, "no_copy": 1},
	]
}


def after_install():
	after_migrate()


def after_migrate():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 0}).insert(ignore_permissions=True)
	create_custom_fields(SO_FIELDS, ignore_validate=True, update=True)
	# Saat install-app doctype bisa belum tersinkron → kunci webhook dibuat pada migrate berikutnya.
	if not frappe.db.exists("DocType", "Booking Ops Settings"):
		frappe.db.commit()
		return
	s = frappe.get_doc("Booking Ops Settings")
	if not s.webhook_key or not s.webhook_url:
		s.flags.ignore_mandatory = True
		s.save(ignore_permissions=True)
	frappe.db.commit()
