"""API untuk PWA Booking Ops (/booking_ops).

Akses per menu diatur di Booking Ops Settings → Akses Menu per Role, dan ditegakkan di
setiap endpoint lewat `_require(menu)`. Setelah lolos, baca/tulis memakai ignore_permissions.
"""

import hmac
import json
from calendar import monthrange

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, get_url, getdate, now_datetime, nowdate

from booking_ops import beds24, sync

MENUS = (
	"dashboard",
	"calendar",
	"bookings",
	"messages",
	"reply_message",
	"new_booking",
	"edit_booking",
	"front_desk",
	"availability",
	"sales_order",
	"sync",
	"reports",
)
MANAGER_ROLES = {"System Manager", "Booking Ops Manager"}
ACTIVE = ("confirmed", "new", "request")
CARD_FIELDS = [
	"name",
	"booking_id",
	"guest_name",
	"status",
	"stay_status",
	"property",
	"room",
	"unit_name",
	"room_qty",
	"arrival",
	"departure",
	"nights",
	"num_adult",
	"num_child",
	"price",
	"paid",
	"currency",
	"channel",
	"arrival_time",
	"sales_order",
	"sync_state",
	"mobile",
	"phone",
]


# ───────────────────────── Akses ─────────────────────────


def _settings():
	return frappe.get_cached_doc("Booking Ops Settings")


def _is_manager(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(set(frappe.get_roles(user)) & MANAGER_ROLES)


def menu_access(user=None):
	"""{menu: bool}. Menu tanpa baris role → semua Booking Ops User; ada baris → hanya role itu."""
	user = user or frappe.session.user
	if user == "Guest":
		return {m: False for m in MENUS}
	roles = set(frappe.get_roles(user))
	if _is_manager(user):
		return {m: True for m in MENUS}
	rows = {}
	for row in _settings().menu_roles or []:
		rows.setdefault(row.menu, set()).add(row.role)
	base = "Booking Ops User" in roles
	return {m: bool(roles & rows[m]) if m in rows else base for m in MENUS}


def _require(menu):
	if frappe.session.user == "Guest" or not menu_access().get(menu):
		frappe.throw(_("Anda tidak punya akses ke menu ini ({0}).").format(menu), frappe.PermissionError)


def has_app_permission():
	return frappe.session.user != "Guest" and any(menu_access().values())


# ───────────────────────── Bootstrap ─────────────────────────


def _rooms(property=None):
	filters = {"enabled": 1}
	if property:
		filters["property"] = property
	enabled_props = frappe.get_all("Beds24 Property", {"enabled": 1}, pluck="name")
	filters["property"] = ("in", [property] if property else enabled_props or [""])
	rooms = frappe.get_all(
		"Beds24 Room",
		filters,
		["room_id", "property", "room_name", "qty", "max_people", "rack_rate", "units_json", "sort_order"],
		order_by="property asc, sort_order asc, room_name asc",
	)
	for r in rooms:
		try:
			r["units"] = json.loads(r.pop("units_json") or "[]")
		except ValueError:
			r["units"] = []
	return rooms


@frappe.whitelist()
def get_bootstrap():
	if frappe.session.user == "Guest":
		frappe.throw(_("Silakan login."), frappe.PermissionError)
	menus = menu_access()
	if not any(menus.values()):
		frappe.throw(_("Akun Anda belum diberi akses Booking Ops."), frappe.PermissionError)
	s = _settings()
	props = frappe.get_all(
		"Beds24 Property",
		{"enabled": 1},
		["property_id", "property_name", "currency", "check_in_start", "check_out_end"],
		order_by="property_name asc",
	)
	company = s.company or frappe.defaults.get_global_default("company")
	return {
		"user": {
			"email": frappe.session.user,
			"full_name": frappe.utils.get_fullname(frappe.session.user),
			"is_manager": _is_manager(),
		},
		"menus": menus,
		"properties": props,
		"rooms": _rooms(),
		"settings": {
			"company": company,
			"currency": (company and frappe.get_cached_value("Company", company, "default_currency")) or "IDR",
			"connected": bool(
				s.get_password("refresh_token", raise_exception=False)
				or s.get_password("long_life_token", raise_exception=False)
			),
			"enable_sync": cint(s.enable_sync),
			"sandbox": cint(s.sandbox_mode),
			"last_pull": s.last_pull,
			"last_pull_result": s.last_pull_result,
		},
		"unread_messages": _unread_count() if menus.get("messages") else 0,
		"today": nowdate(),
	}


# ───────────────────────── Beranda ─────────────────────────


def _prop_filter(filters, property):
	if property:
		filters["property"] = property
	return filters


def _total_units(property=None):
	return sum(max(cint(r["qty"]), len(r["units"]), 0) for r in _rooms(property))


@frappe.whitelist()
def dashboard(date=None, property=None):
	_require("dashboard")
	d = str(getdate(date or nowdate()))
	act = ("in", ACTIVE)
	arrivals = frappe.get_all(
		"Beds24 Booking", _prop_filter({"arrival": d, "status": act}, property), CARD_FIELDS, order_by="arrival_time asc, guest_name asc"
	)
	departures = frappe.get_all(
		"Beds24 Booking", _prop_filter({"departure": d, "status": act}, property), CARD_FIELDS, order_by="guest_name asc"
	)
	in_house = frappe.get_all(
		"Beds24 Booking",
		_prop_filter({"arrival": ("<=", d), "departure": (">", d), "status": act}, property),
		CARD_FIELDS,
		order_by="departure asc",
	)
	units = _total_units(property)
	occupied = sum(max(cint(b.room_qty), 1) for b in in_house)
	month_start = d[:8] + "01"
	month_end = d[:8] + str(monthrange(getdate(d).year, getdate(d).month)[1])
	revenue = frappe.db.sql(
		"""select coalesce(sum(price),0) from `tabBeds24 Booking`
		where arrival between %s and %s and status in %s {0}""".format("and property=%s" if property else ""),
		(month_start, month_end, ACTIVE, property) if property else (month_start, month_end, ACTIVE),
	)[0][0]
	new_24h = frappe.db.count(
		"Beds24 Booking", _prop_filter({"booking_time": (">=", add_days(now_datetime(), -1))}, property)
	)
	attention = frappe.db.count(
		"Beds24 Booking", _prop_filter({"sync_state": ("in", ("Error", "Needs Review"))}, property)
	)
	return {
		"date": d,
		"arrivals": arrivals,
		"departures": departures,
		"in_house": in_house,
		"stats": {
			"arrivals": len(arrivals),
			"arrivals_done": sum(1 for b in arrivals if b.stay_status != "Expected"),
			"departures": len(departures),
			"departures_done": sum(1 for b in departures if b.stay_status == "Checked Out"),
			"in_house": len(in_house),
			"checked_in": sum(1 for b in in_house if b.stay_status == "Checked In"),
			"occupancy": round(occupied * 100.0 / units, 1) if units else 0,
			"units": units,
			"occupied": occupied,
			"revenue_month": flt(revenue),
			"new_24h": new_24h,
			"attention": attention,
		},
	}


# ───────────────────────── Daftar & detail ─────────────────────────


@frappe.whitelist()
def list_bookings(txt=None, scope="upcoming", property=None, channel=None, date_from=None, date_to=None, start=0, limit=30):
	_require("bookings")
	today = nowdate()
	f = _prop_filter({}, property)
	order = "arrival desc, name desc"
	if txt and txt.strip():
		scope = "all"  # cari nama/nomor di semua booking, bukan hanya tab yang sedang aktif
	if scope == "upcoming":
		f.update({"arrival": (">=", today), "status": ("in", ACTIVE)})
		order = "arrival asc, name asc"
	elif scope == "inhouse":
		f.update({"arrival": ("<=", today), "departure": (">", today), "status": ("in", ACTIVE)})
		order = "departure asc"
	elif scope == "past":
		f.update({"departure": ("<=", today), "status": ("in", ACTIVE)})
	elif scope == "cancelled":
		f["status"] = "cancelled"
	elif scope == "attention":
		f["sync_state"] = ("in", ("Error", "Needs Review"))
	if channel:
		f["channel"] = channel
	if date_from and date_to:
		f["arrival"] = ("between", (date_from, date_to))
	elif date_from:
		f["arrival"] = (">=", date_from)
	elif date_to:
		f["arrival"] = ("<=", date_to)
	or_filters = None
	if txt:
		like = f"%{txt.strip()}%"
		or_filters = {k: ("like", like) for k in ("guest_name", "booking_id", "email", "mobile", "api_reference")}
	return frappe.get_all(
		"Beds24 Booking",
		filters=f,
		or_filters=or_filters,
		fields=CARD_FIELDS,
		order_by=order,
		start=cint(start),
		page_length=min(cint(limit) or 30, 100),
	)


def _so_summary(name):
	if not name or not frappe.db.exists("Sales Order", name):
		return None
	so = frappe.get_doc("Sales Order", name)
	return {
		"name": so.name,
		"status": so.status,
		"docstatus": so.docstatus,
		"customer": so.customer,
		"customer_name": so.customer_name,
		"transaction_date": so.transaction_date,
		"delivery_date": so.delivery_date,
		"currency": so.currency,
		"net_total": so.net_total,
		"total_taxes": so.total_taxes_and_charges,
		"grand_total": so.grand_total,
		"per_billed": so.per_billed,
		"advance_paid": so.advance_paid,
		"items": [{"item_code": i.item_code, "description": i.description, "qty": i.qty, "rate": i.rate, "amount": i.amount} for i in so.items],
		"desk_url": f"/app/sales-order/{so.name}",
	}


def _booking_out(doc):
	out = doc.as_dict(no_default_fields=True)
	for k in ("raw_json", "invoice_json", "info_json", "so_hash"):
		out.pop(k, None)
	out["name"] = doc.name
	out["invoice_items"] = json.loads(doc.invoice_json or "[]")
	out["info_items"] = json.loads(doc.info_json or "[]")
	out["room_name"] = doc.room and frappe.db.get_value("Beds24 Room", doc.room, "room_name")
	out["property_name"] = doc.property and frappe.db.get_value("Beds24 Property", doc.property, "property_name")
	menus = menu_access()
	out["sales_order_info"] = _so_summary(doc.sales_order) if menus.get("sales_order") else None
	if menus.get("messages"):
		out["message_count"] = frappe.db.count("Beds24 Message", {"booking": doc.name})
		out["unread_messages"] = frappe.db.count("Beds24 Message", {"booking": doc.name, "source": "guest", "read": 0})
	out["log"] = frappe.get_all(
		"Beds24 Sync Log",
		{"booking_id": doc.name},
		["creation", "direction", "event", "status", "message", "user"],
		order_by="creation desc",
		limit_page_length=20,
	)
	return out


@frappe.whitelist()
def get_booking(booking_id):
	_require("bookings")
	return _booking_out(frappe.get_doc("Beds24 Booking", str(booking_id)))


# ───────────────────────── Kalender & ketersediaan ─────────────────────────


@frappe.whitelist()
def calendar(start=None, days=14, property=None):
	_require("calendar")
	start = str(getdate(start or nowdate()))
	days = min(max(cint(days) or 14, 1), 62)
	end = add_days(start, days)
	bookings = frappe.get_all(
		"Beds24 Booking",
		_prop_filter({"arrival": ("<", end), "departure": (">", start), "status": ("!=", "cancelled")}, property),
		["booking_id", "guest_name", "status", "stay_status", "room", "unit_id", "unit_name", "arrival", "departure", "channel", "num_adult", "num_child"],
		order_by="arrival asc",
		limit_page_length=2000,
	)
	return {"start": start, "days": days, "rooms": _rooms(property), "bookings": bookings}


def _local_busy_units(room, arrival, departure, exclude=None):
	rows = frappe.get_all(
		"Beds24 Booking",
		{"room": room, "arrival": ("<", departure), "departure": (">", arrival), "status": ("in", (*ACTIVE, "black")), "unit_id": ("is", "set")},
		["unit_id", "name"],
	)
	return {r.unit_id for r in rows if r.name != exclude}


@frappe.whitelist()
def availability(arrival, departure, property=None, num_adult=1, num_child=0, exclude=None):
	"""Kamar tersedia + harga (Beds24 offers). Unit bebas dihitung dari booking lokal."""
	m = menu_access()
	if not (m.get("availability") or m.get("new_booking") or m.get("edit_booking")):
		_require("availability")
	if date_diff(departure, arrival) < 1:
		frappe.throw(_("Tanggal keberangkatan harus setelah kedatangan."))
	rooms = _rooms(property)
	props = sorted({r["property"] for r in rooms})
	offers, avail, warn = {}, {}, ""
	try:
		for pid in props:
			for row in beds24.get_offers(arrival, departure, num_adult, num_child, property_ids=[int(pid)]):
				offers[str(row.get("roomId"))] = row.get("offers") or []
	except Exception as e:
		warn = str(e)
		try:
			last_night = add_days(departure, -1)
			for row in beds24.get_availability(arrival, last_night, property_ids=[int(p) for p in props]):
				avail[str(row.get("roomId"))] = all((row.get("availability") or {}).values())
		except Exception as e2:
			warn = str(e2)
	out = []
	for r in rooms:
		rid = r["room_id"]
		room_offers = offers.get(rid, [])
		units_avail = max((cint(o.get("unitsAvailable")) for o in room_offers), default=None)
		if units_avail is None and rid in avail:
			units_avail = r["qty"] if avail[rid] else 0
		busy = _local_busy_units(rid, arrival, departure, exclude)
		free_units = [u for u in r["units"] if str(u.get("id")) not in busy]
		price = min((flt(o.get("price")) for o in room_offers if o.get("price") is not None), default=None)
		out.append(
			{
				**{k: r[k] for k in ("room_id", "property", "room_name", "qty", "max_people", "rack_rate")},
				"units_available": units_avail,
				"price": price,
				"offers": room_offers,
				"free_units": free_units,
			}
		)
	return {"rooms": out, "nights": date_diff(departure, arrival), "warning": warn}


@frappe.whitelist()
def rates(start=None, days=14, property=None):
	"""Kalender harga & sisa kamar per hari (Beds24 /inventory/rooms/calendar)."""
	_require("availability")
	start = str(getdate(start or nowdate()))
	days = min(max(cint(days) or 14, 1), 62)
	end = add_days(start, days - 1)
	rooms = _rooms(property)
	props = sorted({int(r["property"]) for r in rooms})
	grid = {}
	for row in beds24.get_calendar(start, end, property_ids=props) if props else []:
		cells = grid.setdefault(str(row.get("roomId")), {})
		for c in row.get("calendar") or []:
			d, to = str(getdate(c.get("from"))), str(getdate(c.get("to") or c.get("from")))
			while d <= to:
				if start <= d <= end:
					cells[d] = {"avail": c.get("numAvail"), "price": c.get("price1"), "min_stay": c.get("minStay")}
				d = str(add_days(d, 1))
	return {"start": start, "days": days, "rooms": rooms, "grid": grid}


# ───────────────────────── Tulis ke Beds24 ─────────────────────────

EDITABLE = {
	"arrival": "arrival",
	"departure": "departure",
	"room": "roomId",
	"unit_id": "unitId",
	"num_adult": "numAdult",
	"num_child": "numChild",
	"title": "title",
	"first_name": "firstName",
	"last_name": "lastName",
	"email": "email",
	"mobile": "mobile",
	"phone": "phone",
	"country": "country2",
	"company_name": "company",
	"arrival_time": "arrivalTime",
	"price": "price",
	"deposit": "deposit",
	"comments": "comments",
	"notes": "notes",
	"status": "status",
}
INT_FIELDS = {"roomId", "unitId", "numAdult", "numChild"}


def _payload(data):
	data = frappe.parse_json(data) if isinstance(data, str) else (data or {})
	out = {}
	for k, b24 in EDITABLE.items():
		if k not in data:
			continue
		v = data[k]
		if b24 in INT_FIELDS:
			v = cint(v) or None
		elif b24 in ("price", "deposit"):
			v = flt(v)
		elif b24 == "status" and v not in ("confirmed", "request", "new"):
			frappe.throw(_("Status tidak valid: {0}").format(v))
		out[b24] = v
	return out, data


def _validate_dates(arrival, departure):
	if not arrival or not departure or date_diff(departure, arrival) < 1:
		frappe.throw(_("Tanggal keberangkatan harus setelah kedatangan."))


def _after_push(booking_id, fallback, event):
	try:
		doc = sync.pull_one(booking_id, source="app")
	except Exception as e:
		sync.upsert_booking(dict(fallback, id=booking_id), source="app")
		doc = frappe.get_doc("Beds24 Booking", str(booking_id))
		sync.log("Keluar", event, booking_id, "Error", _("Tersimpan di Beds24, tapi gagal ditarik ulang: {0}").format(e))
	sync.log("Keluar", event, booking_id, message=frappe.session.user)
	frappe.db.commit()
	return _booking_out(doc)


@frappe.whitelist(methods=["POST"])
def create_booking(data):
	_require("new_booking")
	payload, raw = _payload(data)
	_validate_dates(payload.get("arrival"), payload.get("departure"))
	if not payload.get("roomId"):
		frappe.throw(_("Pilih tipe kamar."))
	if not (payload.get("firstName") or payload.get("lastName")):
		frappe.throw(_("Isi nama tamu."))
	payload.setdefault("status", "confirmed")
	payload.setdefault("numAdult", 1)
	payload["referer"] = "ERPNext Booking Ops"
	payload["actions"] = {
		"checkAvailability": True,
		"notifyGuest": bool(cint(raw.get("notify_guest"))),
		"autoInvoiceItemCharge": True,
	}
	res = beds24.post_bookings([payload])
	new_id = ((res[0].get("new") or {}).get("id")) or res[0].get("id")
	if not new_id:
		frappe.throw(_("Beds24 tidak mengembalikan nomor booking: {0}").format(res))
	payload.pop("actions", None)
	return _after_push(new_id, payload, "Booking dibuat")


@frappe.whitelist(methods=["POST"])
def update_booking(booking_id, data):
	_require("edit_booking")
	doc = frappe.get_doc("Beds24 Booking", str(booking_id))
	if doc.status == "cancelled":
		frappe.throw(_("Booking sudah dibatalkan."))
	payload, _raw = _payload(data)
	_validate_dates(payload.get("arrival", str(doc.arrival)), payload.get("departure", str(doc.departure)))
	payload["id"] = cint(booking_id)
	beds24.post_bookings([payload])
	return _after_push(booking_id, payload, "Booking diubah")


@frappe.whitelist(methods=["POST"])
def cancel_booking(booking_id, reason=None):
	_require("edit_booking")
	doc = frappe.get_doc("Beds24 Booking", str(booking_id))
	if doc.status == "cancelled":
		return _booking_out(doc)
	payload = {"id": cint(booking_id), "status": "cancelled", "subStatus": "cancelledByHost"}
	if reason:
		stamp = f"[{nowdate()} {frappe.session.user}] Batal: {reason}"
		payload["notes"] = f"{doc.notes}\n{stamp}".strip() if doc.notes else stamp
	beds24.post_bookings([payload])
	return _after_push(booking_id, payload, "Booking dibatalkan")


STAY_ACTIONS = {
	# aksi: (status asal yang boleh, status baru, kolom waktu, flag Beds24, warna)
	"check_in": (("Expected",), "Checked In", "checked_in_at", "CHECKED IN", "2e7d32"),
	"check_out": (("Checked In",), "Checked Out", "checked_out_at", "CHECKED OUT", "607d8b"),
	"no_show": (("Expected",), "No Show", None, "NO SHOW", "c62828"),
	"undo": (("Checked In", "Checked Out", "No Show"), "Expected", None, "", ""),
}


@frappe.whitelist(methods=["POST"])
def set_stay_status(booking_id, action):
	_require("front_desk")
	if action not in STAY_ACTIONS:
		frappe.throw(_("Aksi tidak dikenal."))
	allowed, new, ts_field, flag, color = STAY_ACTIONS[action]
	doc = frappe.get_doc("Beds24 Booking", str(booking_id))
	if doc.status not in ACTIVE:
		frappe.throw(_("Booking berstatus {0} tidak bisa diproses.").format(doc.status))
	if doc.stay_status not in allowed:
		frappe.throw(_("Tidak bisa {0}: status inap sekarang {1}.").format(action, doc.stay_status))
	if action == "check_in" and getdate(doc.arrival) > getdate(nowdate()):
		frappe.throw(_("Belum tanggal kedatangan ({0}).").format(doc.arrival))
	if action == "undo" and not _is_manager():
		frappe.throw(_("Hanya manajer yang bisa membatalkan status inap."), frappe.PermissionError)
	vals = {"stay_status": new}
	if ts_field:
		vals[ts_field] = now_datetime()
	if action == "undo":
		vals.update({"checked_in_at": None, "checked_out_at": None})
	doc.db_set(vals)
	sync.log("Sistem", {"check_in": "Check-in", "check_out": "Check-out", "no_show": "No-show", "undo": "Status inap dibatalkan"}[action], doc.name, message=frappe.session.user)
	# Tanda di kalender Beds24 (best effort — gagal tidak membatalkan check-in).
	try:
		beds24.post_bookings([{"id": cint(doc.name), "flagText": flag, "flagColor": color}])
	except Exception as e:
		sync.log("Keluar", "Flag status inap", doc.name, "Error", str(e))
	frappe.db.commit()
	return _booking_out(frappe.get_doc("Beds24 Booking", doc.name))


# ───────────────────────── Sinkron ─────────────────────────


@frappe.whitelist(methods=["POST"])
def resync_booking(booking_id):
	_require("bookings")
	doc = sync.pull_one(booking_id)
	sync.sync_sales_order(doc)  # paksa coba ulang SO walau data Beds24 tak berubah
	frappe.db.commit()
	return _booking_out(frappe.get_doc("Beds24 Booking", doc.name))


@frappe.whitelist(methods=["POST"])
def sync_now(full=0):
	_require("sync")
	if cint(full):
		frappe.enqueue("booking_ops.sync.pull_changes", queue="long", full=True, timeout=1800)
		return {"queued": True}
	return sync.pull_changes()


@frappe.whitelist(methods=["POST"])
def sandbox_simulate(kind="new"):
	"""Mode Sandbox: tiru booking baru / pembatalan dari OTA (diproses seperti webhook)."""
	_require("sync")
	from booking_ops import sandbox

	return sandbox.simulate(kind)


@frappe.whitelist()
def sync_status(limit=50, only_errors=0):
	_require("sync")
	s = frappe.get_doc("Booking Ops Settings")
	f = {"status": "Error"} if cint(only_errors) else {}
	return {
		"connected": bool(s.get_password("refresh_token", raise_exception=False) or s.get_password("long_life_token", raise_exception=False)),
		"connection_status": s.connection_status,
		"sandbox": cint(s.sandbox_mode),
		"enable_sync": cint(s.enable_sync),
		"last_pull": s.last_pull,
		"last_pull_result": s.last_pull_result,
		"attention": frappe.get_all(
			"Beds24 Booking",
			{"sync_state": ("in", ("Error", "Needs Review"))},
			["booking_id", "guest_name", "arrival", "sync_state", "sync_error"],
			order_by="modified desc",
			limit_page_length=50,
		),
		"log": frappe.get_all(
			"Beds24 Sync Log",
			f,
			["creation", "direction", "event", "booking_id", "status", "message", "user"],
			order_by="creation desc",
			limit_page_length=min(cint(limit) or 50, 200),
		),
	}


# ───────────────────────── Laporan ─────────────────────────


@frappe.whitelist()
def report(month=None, property=None):
	_require("reports")
	d = getdate(month or nowdate())
	first = d.replace(day=1)
	days_in = monthrange(d.year, d.month)[1]
	last = d.replace(day=days_in)
	next_first = add_days(last, 1)
	rows = frappe.get_all(
		"Beds24 Booking",
		_prop_filter({"arrival": ("<", next_first), "departure": (">", first), "status": ("in", (*ACTIVE, "cancelled"))}, property),
		["name", "status", "room", "channel", "arrival", "departure", "nights", "room_qty", "price", "sales_order"],
		limit_page_length=10000,
	)
	by_channel, by_room = {}, {}
	tot = {"bookings": 0, "nights": 0, "revenue": 0.0, "cancelled": 0}
	for b in rows:
		if b.status == "cancelled":
			if first <= getdate(b.arrival) <= last:
				tot["cancelled"] += 1
			continue
		# malam yang jatuh di bulan ini; pendapatan dibagi proporsional per malam
		a, dep = max(getdate(b.arrival), first), min(getdate(b.departure), getdate(next_first))
		n_in = max(date_diff(dep, a), 0) * max(cint(b.room_qty), 1)
		total_n = max(cint(b.nights), 1) * max(cint(b.room_qty), 1)
		rev = flt(b.price) * n_in / total_n
		tot["nights"] += n_in
		tot["revenue"] += rev
		if first <= getdate(b.arrival) <= last:
			tot["bookings"] += 1
		ch = by_channel.setdefault(b.channel or "direct", {"channel": b.channel or "direct", "bookings": 0, "nights": 0, "revenue": 0.0})
		ch["nights"] += n_in
		ch["revenue"] += rev
		if first <= getdate(b.arrival) <= last:
			ch["bookings"] += 1
		rm = by_room.setdefault(b.room or "-", {"room": b.room, "nights": 0, "revenue": 0.0})
		rm["nights"] += n_in
		rm["revenue"] += rev
	rooms = {r["room_id"]: r for r in _rooms(property)}
	for rid, rm in by_room.items():
		r = rooms.get(rid) or {}
		units = max(cint(r.get("qty")), len(r.get("units") or []), 1)
		rm["room_name"] = r.get("room_name") or rid
		rm["occupancy"] = round(rm["nights"] * 100.0 / (units * days_in), 1)
	units_total = _total_units(property)
	so_names = [b.sales_order for b in rows if b.sales_order]
	so_rows = frappe.get_all("Sales Order", {"name": ("in", so_names or [""])}, ["docstatus", "status", "grand_total", "per_billed"])
	return {
		"month": str(first)[:7],
		"days": days_in,
		"totals": dict(
			tot,
			revenue=round(tot["revenue"], 2),
			adr=round(tot["revenue"] / tot["nights"], 2) if tot["nights"] else 0,
			occupancy=round(tot["nights"] * 100.0 / (units_total * days_in), 1) if units_total else 0,
			units=units_total,
		),
		"by_channel": sorted(by_channel.values(), key=lambda x: -x["revenue"]),
		"by_room": sorted(by_room.values(), key=lambda x: -x["nights"]),
		"sales_orders": {
			"draft": sum(1 for r in so_rows if r.docstatus == 0),
			"submitted": sum(1 for r in so_rows if r.docstatus == 1),
			"billed": sum(1 for r in so_rows if r.docstatus == 1 and flt(r.per_billed) >= 100),
			"total": round(sum(flt(r.grand_total) for r in so_rows if r.docstatus != 2), 2),
		},
	}


# ───────────────────────── Pesan tamu ─────────────────────────

MSG_FIELDS = ["name", "message_id", "booking", "source", "message", "time", "read", "attachment", "attachment_name", "sent_by"]
ATTACH_TYPES = {"image/jpeg", "image/png", "image/gif", "application/pdf"}
MAX_ATTACH = 5 * 1024 * 1024


def _unread_count(property=None):
	cond, args = "", {}
	if property:
		cond, args = " and b.property = %(property)s", {"property": property}
	return cint(
		frappe.db.sql(
			f"""select count(*) from `tabBeds24 Message` m join `tabBeds24 Booking` b on b.name = m.booking
			where m.source = 'guest' and m.read = 0{cond}""",
			args,
		)[0][0]
	)


@frappe.whitelist()
def unread_count(property=None):
	"""Ringan, dipanggil berkala oleh PWA untuk badge menu Pesan."""
	if frappe.session.user == "Guest" or not menu_access().get("messages"):
		return 0
	return _unread_count(property)


@frappe.whitelist()
def inbox(txt=None, only_unread=0, property=None, start=0, limit=30):
	"""Satu baris per booking: pesan terakhir + jumlah belum dibaca, terbaru di atas."""
	_require("messages")
	cond, args = [], {"start": cint(start), "limit": min(cint(limit) or 30, 100)}
	if property:
		cond.append("b.property = %(property)s")
		args["property"] = property
	if txt and txt.strip():
		args["like"] = f"%{txt.strip()}%"
		cond.append(
			"(b.guest_name like %(like)s or b.booking_id like %(like)s or exists (select 1 from `tabBeds24 Message` x"
			" where x.booking = b.name and x.message like %(like)s))"
		)
	where = ("where " + " and ".join(cond)) if cond else ""
	having = "having unread > 0" if cint(only_unread) else ""
	rows = frappe.db.sql(
		f"""select m.booking, max(m.time) as last_time, count(*) as total,
			sum(m.source = 'guest' and m.read = 0) as unread
		from `tabBeds24 Message` m join `tabBeds24 Booking` b on b.name = m.booking
		{where} group by m.booking {having}
		order by last_time desc limit %(start)s, %(limit)s""",
		args,
		as_dict=True,
	)
	if not rows:
		return []
	names = [r.booking for r in rows]
	books = {b.name: b for b in frappe.get_all("Beds24 Booking", {"name": ("in", names)}, CARD_FIELDS)}
	last = {}
	for m in frappe.get_all(
		"Beds24 Message", {"booking": ("in", names)}, ["booking", "source", "message", "attachment_name", "time"], order_by="time desc"
	):
		last.setdefault(m.booking, m)
	return [
		dict(books.get(r.booking) or {}, booking_id=r.booking, last_time=r.last_time, total=cint(r.total),
			 unread=cint(r.unread), last=last.get(r.booking))
		for r in rows
	]


@frappe.whitelist()
def thread(booking_id, refresh=0):
	"""Percakapan satu booking (lama → baru). refresh=1 → tarik dulu dari Beds24."""
	_require("messages")
	name = str(booking_id)
	doc = frappe.get_doc("Beds24 Booking", name)
	warning = None
	if cint(refresh):
		try:
			sync.pull_messages(booking_id=name)
		except Exception as e:
			frappe.db.rollback()
			warning = _("Gagal mengambil pesan terbaru dari Beds24: {0}").format(e)
	out = {k: doc.get(k) for k in CARD_FIELDS}
	out["room_name"] = doc.room and frappe.db.get_value("Beds24 Room", doc.room, "room_name")
	return {
		"booking": out,
		"messages": frappe.get_all("Beds24 Message", {"booking": name}, MSG_FIELDS, order_by="time asc, creation asc"),
		"can_reply": bool(menu_access().get("reply_message")),
		"warning": warning,
	}


@frappe.whitelist(methods=["POST"])
def mark_read(booking_id):
	"""Tandai pesan tamu dibaca: lokal langsung, lalu diteruskan ke Beds24 (gagal → dicatat saja)."""
	_require("messages")
	ids = frappe.get_all("Beds24 Message", {"booking": str(booking_id), "source": "guest", "read": 0}, pluck="name")
	if not ids:
		return {"marked": 0}
	frappe.db.set_value("Beds24 Message", {"name": ("in", ids)}, "read", 1, update_modified=False)
	frappe.db.commit()
	try:
		beds24.post_messages([{"id": cint(i), "read": True} for i in ids if str(i).isdigit()])
	except Exception as e:
		sync.log("Keluar", "Tandai pesan dibaca", booking_id, "Error", str(e))
	return {"marked": len(ids)}


@frappe.whitelist(methods=["POST"])
def send_message(booking_id, message=None, internal=0, attachment=None, attachment_name=None, attachment_type=None):
	"""Balas tamu lewat Beds24 (diteruskan ke channel: Airbnb, Booking.com, …) atau catatan internal."""
	_require("reply_message")
	name = str(booking_id)
	if not frappe.db.exists("Beds24 Booking", name):
		frappe.throw(_("Booking {0} tidak ditemukan.").format(name))
	text = (message or "").strip()
	if not text and not attachment:
		frappe.throw(_("Tulis pesan dulu."))
	if len(text) > 5000:
		frappe.throw(_("Pesan terlalu panjang (maks 5000 karakter)."))
	row = {"bookingId": cint(name), "message": text}
	source = "internalNote" if cint(internal) else "host"
	if source == "internalNote":
		row["source"] = source
	if attachment:
		if attachment_type not in ATTACH_TYPES:
			frappe.throw(_("Lampiran harus JPG, PNG, GIF atau PDF."))
		if len(attachment) * 3 / 4 > MAX_ATTACH:
			frappe.throw(_("Lampiran maksimal 5 MB."))
		row.update({"attachment": attachment, "attachmentName": attachment_name or "lampiran", "attachmentMimeType": attachment_type})
	beds24.post_messages([row])
	try:
		sync.pull_messages(booking_id=name)
	except Exception as e:
		sync.log("Masuk", "Pesan", name, "Error", _("Terkirim, tapi gagal ditarik ulang: {0}").format(e))
	mine = frappe.db.get_value(
		"Beds24 Message",
		{"booking": name, "source": source, "message": text, "sent_by": ("is", "not set")},
		"name",
		order_by="time desc",
	)
	if mine:
		frappe.db.set_value("Beds24 Message", mine, "sent_by", frappe.session.user, update_modified=False)
	sync.log("Keluar", "Catatan internal" if source == "internalNote" else "Pesan dikirim", name, message=text[:140])
	frappe.db.commit()
	return thread(name)


@frappe.whitelist(methods=["POST"])
def fetch_messages():
	"""Tombol "Muat pesan": tarik pesan 30 hari terakhir dari Beds24."""
	_require("messages")
	return sync.pull_messages(max_age=30)


# ───────────────────────── Webhook Beds24 ─────────────────────────


@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook(key=None):
	# Body JSON (Beds24) → Frappe tidak memasukkan query string ke form_dict; baca langsung.
	key = key or frappe.request.args.get("key") or frappe.get_request_header("X-Booking-Ops-Key")
	expected = frappe.db.get_single_value("Booking Ops Settings", "webhook_key") or ""
	if not expected or not hmac.compare_digest(str(key or ""), expected):
		frappe.throw(_("Kunci webhook salah."), frappe.PermissionError)
	try:
		payload = json.loads(frappe.request.get_data(as_text=True) or "{}")
	except ValueError:
		payload = {}
	frappe.enqueue("booking_ops.sync.handle_webhook", queue="short", payload=payload, enqueue_after_commit=True)
	return {"ok": True}


def webhook_url(key):
	return get_url(f"/api/method/booking_ops.api.webhook?key={key}")
