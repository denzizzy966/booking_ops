import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class BookingOpsSettings(Document):
	def validate(self):
		if not self.webhook_key:
			self.webhook_key = frappe.generate_hash(length=32)
		from booking_ops.api import webhook_url

		self.webhook_url = webhook_url(self.webhook_key)
		self._sandbox_token()
		seen = set()
		for row in self.menu_roles or []:
			if (row.menu, row.role) in seen:
				frappe.throw(_("Baris menu {0} untuk role {1} dobel.").format(row.menu, row.role))
			seen.add((row.menu, row.role))

	def _sandbox_token(self):
		"""Sandbox tidak butuh invite code: tandai 'terhubung' supaya sinkron berkala ikut jalan."""
		current = self.get_password("refresh_token", raise_exception=False) if not self.is_new() else None
		if self.sandbox_mode and not current:
			self.refresh_token = "SANDBOX"
			self.connection_status = _("Sandbox (Beds24 tiruan)")
			self.connected_at = now_datetime()
		elif not self.sandbox_mode and current == "SANDBOX":
			self.refresh_token = None
			self.connection_status = _("Belum terhubung")
			self.connected_at = None


def _manager():
	frappe.only_for(("System Manager", "Booking Ops Manager"))


@frappe.whitelist()
def connect(invite_code=None):
	"""Invite code (dari field atau argumen) → refresh token."""
	_manager()
	from booking_ops import beds24

	s = frappe.get_doc("Booking Ops Settings")
	code = invite_code or s.get_password("invite_code", raise_exception=False)
	if not code:
		frappe.throw(_("Isi Invite Code dulu."))
	s.refresh_token = beds24.connect(code)
	s.invite_code = None  # sekali pakai
	s.connection_status = _("Terhubung")
	s.connected_at = now_datetime()
	s.save()
	return test_connection()


@frappe.whitelist()
def test_connection():
	_manager()
	from booking_ops import beds24

	try:
		props = beds24.get_properties()
		status = _("Terhubung · {0} properti").format(len(props))
		ok = True
	except Exception as e:
		status = _("Gagal: {0}").format(str(e)[:120])
		ok = False
	frappe.db.set_single_value("Booking Ops Settings", "connection_status", status)
	return {"ok": ok, "status": status}


@frappe.whitelist()
def import_properties():
	_manager()
	from booking_ops import sync

	return sync.import_properties()


@frappe.whitelist()
def pull_now(full=0):
	_manager()
	from booking_ops import sync

	if frappe.utils.cint(full):
		frappe.enqueue("booking_ops.sync.pull_changes", queue="long", full=True, timeout=1800)
		return {"queued": True}
	return sync.pull_changes()


@frappe.whitelist()
def sandbox_reset():
	_manager()
	from booking_ops import sandbox

	return sandbox.reset()


@frappe.whitelist()
def sandbox_simulate(kind="new"):
	_manager()
	from booking_ops import sandbox

	return sandbox.simulate(kind)
