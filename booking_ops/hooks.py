app_name = "booking_ops"
app_title = "Booking Ops"
app_publisher = "RMI"
app_description = "Mobile/tablet PWA for Beds24 bookings, synced to ERPNext Sales Order"
app_email = "denzizzy966@gmail.com"
app_license = "mit"
required_apps = ["erpnext"]

# Tile di App Switcher desk → langsung ke PWA.
add_to_apps_screen = [
	{
		"name": "booking_ops",
		"logo": "/assets/booking_ops/booking_ops/icon-192.png",
		"title": "Booking Ops",
		"route": "/booking_ops",
		"has_permission": "booking_ops.api.has_app_permission",
	}
]

# User Booking Ops tanpa akses Desk diarahkan ke PWA.
role_home_page = {
	"Booking Ops User": "booking_ops",
	"Booking Ops Manager": "booking_ops",
}

after_install = "booking_ops.setup.install.after_install"
after_migrate = "booking_ops.setup.install.after_migrate"

scheduler_events = {
	# Tarik booking yang berubah dari Beds24 (cadangan bila webhook terlewat) + pesan tamu.
	"cron": {"*/5 * * * *": ["booking_ops.sync.scheduled_pull", "booking_ops.sync.scheduled_messages"]},
	"daily": ["booking_ops.sync.daily"],
}

doc_events = {
	"Sales Order": {
		"on_cancel": "booking_ops.sync.on_sales_order_cancel",
	}
}
