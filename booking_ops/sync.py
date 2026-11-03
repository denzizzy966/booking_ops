"""Sinkron Beds24 ⇄ ERPNext.

Alur masuk:  Beds24 (webhook / tarik berkala) → `Beds24 Booking` → Sales Order.
Alur keluar: PWA → Beds24 POST /bookings → tarik ulang booking itu → alur masuk.

Beds24 tetap sumber kebenaran untuk booking; ERPNext menyimpan salinan + status inap
(check-in/out, tidak ada di Beds24) + Sales Order.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone

import frappe
from frappe import _
from frappe.utils import (
	add_days,
	cint,
	convert_utc_to_system_timezone,
	date_diff,
	flt,
	getdate,
	now_datetime,
	nowdate,
)

from booking_ops import beds24

PULL_LOCK = "booking_ops:pull_lock"
UTC_FMT = "%Y-%m-%dT%H:%M:%S"


def _settings():
	return frappe.get_cached_doc("Booking Ops Settings")


def log(direction, event, booking_id=None, status="OK", message=None, payload=None):
	try:
		frappe.get_doc(
			{
				"doctype": "Beds24 Sync Log",
				"direction": direction,
				"event": event,
				"booking_id": str(booking_id or ""),
				"status": status,
				"user": frappe.session.user,
				"message": (message or "")[:1000],
				"payload": json.dumps(payload, default=str)[:60000] if payload is not None else None,
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="Booking Ops: gagal menulis log")


# ───────────────────────── Tarik dari Beds24 ─────────────────────────


def _connected(s):
	return bool(s.get_password("refresh_token", raise_exception=False) or s.get_password("long_life_token", raise_exception=False))


def scheduled_pull():
	s = _settings()
	if not cint(s.enable_sync) or not _connected(s):
		return
	try:
		pull_changes()
	except Exception as e:
		log("Masuk", "Sinkron berkala", status="Error", message=str(e))


def pull_changes(full=False):
	"""Tarik booking yang berubah sejak kursor (atau semua sejak N hari lalu bila full)."""
	if frappe.cache.get_value(PULL_LOCK):
		return {"skipped": True, "message": _("Sinkron lain sedang berjalan.")}
	frappe.cache.set_value(PULL_LOCK, 1, expires_in_sec=600)
	try:
		s = frappe.get_doc("Booking Ops Settings")
		started = datetime.now(timezone.utc) - timedelta(minutes=2)  # tumpang-tindih kecil, aman dari jam beda
		if full or not s.pull_cursor:
			rows = beds24.get_bookings(arrivalFrom=add_days(nowdate(), -cint(s.initial_days_back or 30)))
		else:
			rows = beds24.get_bookings(modifiedFrom=s.pull_cursor)
		stats = {"fetched": len(rows), "created": 0, "updated": 0, "unchanged": 0, "errors": 0}
		for b in rows:
			try:
				res = upsert_booking(b, source="pull")
				stats[res] = stats.get(res, 0) + 1
			except Exception as e:
				stats["errors"] += 1
				log("Masuk", "Tarik booking", b.get("id"), "Error", str(e), b)
			frappe.db.commit()
		msg = _("{fetched} diambil · {created} baru · {updated} berubah · {errors} gagal").format(**stats)
		frappe.db.set_single_value(
			"Booking Ops Settings",
			{"pull_cursor": started.strftime(UTC_FMT), "last_pull": now_datetime(), "last_pull_result": msg},
		)
		log("Masuk", "Sinkron penuh" if full else "Sinkron", status="Error" if stats["errors"] else "OK", message=msg)
		frappe.db.commit()
		return stats
	finally:
		frappe.cache.delete_value(PULL_LOCK)


def pull_one(booking_id, source="pull"):
	b = beds24.get_booking(booking_id)
	if not b:
		raise beds24.Beds24Error(_("Booking {0} tidak ditemukan di Beds24.").format(booking_id))
	upsert_booking(b, source=source)
	return frappe.get_doc("Beds24 Booking", str(booking_id))


def handle_webhook(payload):
	"""Dipanggil di background job. Data lengkap diambil ulang via API (webhook v2 bisa tanpa data pribadi)."""
	frappe.set_user("Administrator")  # dikirim sebagai Guest
	b = (payload or {}).get("booking") or {}
	bid = b.get("id")
	if not bid:
		log("Masuk", "Webhook", status="Dilewati", message="payload tanpa booking.id", payload=payload)
		return
	try:
		pull_one(bid, source="webhook")
	except Exception as e:
		# API gagal → pakai isi webhook apa adanya supaya perubahan tidak hilang.
		if payload.get("invoiceItems") is not None:
			b = dict(b, invoiceItems=payload.get("invoiceItems"))
		upsert_booking(b, source="webhook")
		log("Masuk", "Webhook (tanpa API)", bid, "Error", str(e))
	log("Masuk", "Webhook", bid, message=b.get("status"))
	# Payload webhook v2 bisa membawa pesan booking itu → simpan sekalian.
	for m in payload.get("messages") or []:
		try:
			upsert_message(dict(m, bookingId=m.get("bookingId") or bid))
		except Exception as e:
			log("Masuk", "Pesan (webhook)", bid, "Error", str(e), m)


# ───────────────────────── Beds24 → Beds24 Booking ─────────────────────────


def _dt(value):
	"""'2026-11-01T10:20:30Z' (UTC) → datetime zona sistem, naif."""
	if not value:
		return None
	try:
		v = str(value).replace("Z", "").split(".")[0]
		return convert_utc_to_system_timezone(datetime.strptime(v[:19], UTC_FMT)).replace(tzinfo=None)
	except ValueError:
		return None


def _ensure_room(property_id, room_id):
	"""Booking bisa datang sebelum properti diimpor → buat entri minimal supaya link valid."""
	prop = str(property_id or "")
	room = str(room_id or "")
	if prop and not frappe.db.exists("Beds24 Property", prop):
		frappe.get_doc({"doctype": "Beds24 Property", "property_id": prop, "property_name": f"Properti {prop}"}).insert(
			ignore_permissions=True
		)
	if room and not frappe.db.exists("Beds24 Room", room):
		if not prop:
			return prop or None, None
		frappe.get_doc(
			{"doctype": "Beds24 Room", "room_id": room, "property": prop, "room_name": f"Kamar {room}", "qty": 1}
		).insert(ignore_permissions=True)
	return prop or None, room or None


def _unit_name(room, unit_id):
	if not room or not unit_id:
		return ""
	try:
		units = json.loads(frappe.db.get_value("Beds24 Room", room, "units_json") or "[]")
	except ValueError:
		units = []
	for u in units:
		if str(u.get("id")) == str(unit_id):
			return u.get("name") or ""
	return ""


def map_booking(b):
	"""Field Beds24 → field Beds24 Booking."""
	prop, room = _ensure_room(b.get("propertyId"), b.get("roomId"))
	first, last = (b.get("firstName") or "").strip(), (b.get("lastName") or "").strip()
	guest = " ".join(x for x in (first, last) if x) or (b.get("company") or "").strip() or _("(tanpa nama)")
	invoice = b.get("invoiceItems") or []
	paid = sum(abs(flt(i.get("lineTotal") if i.get("lineTotal") is not None else flt(i.get("qty") or 1) * flt(i.get("amount")))) for i in invoice if i.get("type") == "payment")
	arrival, departure = b.get("arrival"), b.get("departure")
	unit_id = str(b.get("unitId") or "") if b.get("unitId") else ""
	return {
		"booking_id": str(b.get("id")),
		"master_id": str(b.get("masterId") or "") or None,
		"property": prop,
		"room": room,
		"unit_id": unit_id,
		"unit_name": _unit_name(room, unit_id),
		"room_qty": cint(b.get("roomQty") or 1),
		"status": b.get("status") or "confirmed",
		"sub_status": b.get("subStatus") if b.get("subStatus") not in (None, "none") else "",
		"arrival": arrival,
		"departure": departure,
		"nights": max(date_diff(departure, arrival), 0) if arrival and departure else 0,
		"arrival_time": b.get("arrivalTime") or "",
		"num_adult": cint(b.get("numAdult")),
		"num_child": cint(b.get("numChild")),
		"title": b.get("title") or "",
		"first_name": first,
		"last_name": last,
		"guest_name": guest,
		"company_name": b.get("company") or "",
		"email": (b.get("email") or "").strip() or None,  # disimpan apa adanya; validasi saat dipakai
		"phone": b.get("phone") or "",
		"mobile": b.get("mobile") or "",
		"country": b.get("country2") or b.get("country") or "",
		"lang": b.get("lang") or "",
		"price": flt(b.get("price")),
		"deposit": flt(b.get("deposit")),
		"tax": flt(b.get("tax")),
		"commission": flt(b.get("commission")),
		"paid": paid,
		"rate_description": b.get("rateDescription") or "",
		"channel": b.get("channel") or b.get("apiSource") or "",
		"referer": b.get("referer") or "",
		"api_source": b.get("apiSource") or "",
		"api_reference": b.get("apiReference") or "",
		"reference": b.get("reference") or "",
		"booking_time": _dt(b.get("bookingTime")),
		"modified_time": _dt(b.get("modifiedTime")),
		"cancel_time": _dt(b.get("cancelTime")),
		"comments": b.get("comments") or "",
		"notes": b.get("notes") or "",
		"invoice_json": json.dumps(invoice, default=str),
		"info_json": json.dumps(b.get("infoItems") or [], default=str),
		"raw_json": json.dumps(b, default=str),
	}


def upsert_booking(b, source="pull"):
	"""Simpan booking + selaraskan Sales Order. Kembalikan 'created' | 'updated' | 'unchanged'."""
	data = map_booking(b)
	name = data["booking_id"]
	exists = frappe.db.exists("Beds24 Booking", name)
	doc = frappe.get_doc("Beds24 Booking", name) if exists else frappe.new_doc("Beds24 Booking")
	# Data Beds24 sama → lewati; kecuali Error (dicoba ulang tiap sinkron, mis. setelah setelan diperbaiki).
	if exists and doc.raw_json == data["raw_json"] and doc.sync_state != "Error":
		return "unchanged"
	if doc.get("currency") is None and data["property"]:
		data["currency"] = frappe.db.get_value("Beds24 Property", data["property"], "currency")
	doc.update(data)
	# Tamu sudah check-out/no-show tak berubah karena sinkron; batal → kembali Expected tidak perlu.
	doc.flags.from_beds24 = True
	doc.save(ignore_permissions=True) if exists else doc.insert(ignore_permissions=True)
	sync_sales_order(doc)
	return "updated" if exists else "created"


# ───────────────────────── Beds24 Booking → Sales Order ─────────────────────────


def _wants_so(doc, s):
	return {
		"confirmed": cint(s.so_on_confirmed),
		"new": cint(s.so_on_new),
		"request": cint(s.so_on_request),
	}.get(doc.status, 0)


def _company(doc, s):
	company = (doc.property and frappe.db.get_value("Beds24 Property", doc.property, "company")) or s.company
	if not company:
		company = frappe.defaults.get_global_default("company")
	if not company:
		raise frappe.ValidationError(_("Isi Company di Booking Ops Settings."))
	return company


def _channel_customer(doc, s):
	keys = {(doc.channel or "").lower(), (doc.referer or "").lower(), (doc.api_source or "").lower()} - {""}
	for row in s.channel_customers or []:
		if (row.channel or "").strip().lower() in keys:
			return row.customer
	return None


def _default_customer(s):
	if not s.default_customer:
		raise frappe.ValidationError(_("Isi Customer Default di Booking Ops Settings."))
	return s.default_customer


def resolve_customer(doc, s):
	"""Customer untuk SO: per channel → mode default → tamu (cocok email/HP, kalau tidak dibuat baru)."""
	by_channel = _channel_customer(doc, s)
	if by_channel:
		return by_channel
	if s.customer_mode == "Satu Customer Default":
		return _default_customer(s)
	if doc.customer and frappe.db.exists("Customer", doc.customer):
		return doc.customer
	if not (doc.first_name or doc.last_name or doc.company_name):
		return _default_customer(s)

	phone = doc.mobile or doc.phone
	# Email OTA bisa tidak valid (mis. huruf non-ASCII) → abaikan untuk Customer, jangan gagalkan SO.
	email = frappe.utils.validate_email_address(doc.email or "") or None
	for field, value in (("email_id", email), ("mobile_no", phone)):
		if value:
			found = frappe.db.get_value("Customer", {field: value, "disabled": 0}, "name")
			if found:
				return found
	if email:
		found = frappe.db.sql(
			"""select dl.link_name from `tabContact Email` ce
			join `tabDynamic Link` dl on dl.parent = ce.parent and dl.parenttype = 'Contact' and dl.link_doctype = 'Customer'
			where ce.email_id = %s limit 1""",
			email,
		)
		if found:
			return found[0][0]
	if not email and not phone:
		found = frappe.db.get_value("Customer", {"customer_name": doc.guest_name, "disabled": 0}, "name")
		if found:
			return found

	cust = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": doc.guest_name,
			"customer_type": "Company" if (doc.company_name and not (doc.first_name or doc.last_name)) else "Individual",
			"customer_group": s.customer_group
			or frappe.db.get_single_value("Selling Settings", "customer_group")
			or "All Customer Groups",
			"territory": s.territory or frappe.db.get_single_value("Selling Settings", "territory") or "All Territories",
			"email_id": email,
			"mobile_no": phone or None,
			"first_name": doc.first_name or None,
			"last_name": doc.last_name or None,
		}
	)
	cust.flags.ignore_permissions = True
	cust.insert()
	return cust.name


def _room_item(doc, s):
	item = doc.room and frappe.db.get_value("Beds24 Room", doc.room, "item_code")
	item = item or s.default_item
	if not item:
		raise frappe.ValidationError(_("Isi Item Kamar Default di Booking Ops Settings (atau petakan item di Beds24 Room)."))
	return item


def _so_lines(doc, s, delivery_date):
	room_item = _room_item(doc, s)
	room_label = (doc.room and frappe.db.get_value("Beds24 Room", doc.room, "room_name")) or _("Kamar")
	stay = f"{room_label}{' · ' + doc.unit_name if doc.unit_name else ''} · {doc.arrival} → {doc.departure} · {doc.guest_name}"
	lines = []
	if s.line_mode == "Rincian Invoice Beds24":
		charges = [i for i in json.loads(doc.invoice_json or "[]") if i.get("type") == "charge"]
		for idx, c in enumerate(charges):
			qty = flt(c.get("qty") or 1) or 1
			total = flt(c.get("lineTotal")) if c.get("lineTotal") is not None else qty * flt(c.get("amount"))
			is_room = idx == 0 or room_label.lower() in (c.get("description") or "").lower()
			lines.append(
				{
					"item_code": room_item if is_room else (s.extra_item or room_item),
					"description": (c.get("description") or stay) + ("" if not is_room else f" ({stay})"),
					"qty": qty,
					"rate": total / qty,
				}
			)
	if not lines:
		qty = max(cint(doc.nights), 1) * max(cint(doc.room_qty), 1)
		lines.append({"item_code": room_item, "description": stay, "qty": qty, "rate": flt(doc.price) / qty})
	for ln in lines:
		ln["delivery_date"] = delivery_date
	return lines


def _desired_so(doc, s):
	company = _company(doc, s)
	tx_date = getdate(doc.booking_time) if doc.booking_time else getdate(nowdate())
	tx_date = min(tx_date, getdate(nowdate()))
	delivery = max(getdate(doc.arrival or tx_date), tx_date)
	currency = doc.currency or frappe.get_cached_value("Company", company, "default_currency")
	return {
		"customer": resolve_customer(doc, s),
		"company": company,
		"currency": currency,
		"transaction_date": str(tx_date),
		"delivery_date": str(delivery),
		"po_no": doc.api_reference or doc.booking_id,
		"selling_price_list": s.price_list or None,
		"taxes_and_charges": s.taxes_template or None,
		"items": _so_lines(doc, s, str(delivery)),
		"beds24_booking": doc.name,
		"beds24_arrival": str(doc.arrival or ""),
		"beds24_departure": str(doc.departure or ""),
		"beds24_guest": doc.guest_name,
		"beds24_channel": doc.channel or "",
	}


def _hash(d):
	return hashlib.md5(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()


def _apply(so, d):
	for k, v in d.items():
		# Price List kosong di setelan → biarkan nilai bawaan ERPNext (wajib di SO), jangan ditimpa None.
		if k == "items" or (k == "selling_price_list" and not v):
			continue
		so.set(k, v)
	so.set("items", [])
	# Jadwal bayar dihitung ulang ERPNext dari tanggal SO yang baru. Kalau jadwal lama ikut terbawa
	# (SO draft diperbarui / di-amend) dan tanggal SO bergeser, due date-nya bisa lebih awal dari
	# tanggal SO → "Due Date ... cannot be before Posting Date".
	so.set("payment_schedule", [])
	for ln in d["items"]:
		so.append("items", dict(ln, price_list_rate=ln["rate"]))
	company_currency = frappe.get_cached_value("Company", d["company"], "default_currency")
	if d["currency"] != company_currency:
		from erpnext.setup.utils import get_exchange_rate

		so.conversion_rate = get_exchange_rate(d["currency"], company_currency, d["transaction_date"]) or 1
	else:
		so.conversion_rate = 1
	if d["taxes_and_charges"]:
		from erpnext.controllers.accounts_controller import get_taxes_and_charges

		so.set("taxes", get_taxes_and_charges("Sales Taxes and Charges Template", d["taxes_and_charges"]))
	else:
		so.set("taxes", [])
	so.flags.ignore_permissions = True
	so.flags.from_booking_ops = True


def _billed(so):
	return flt(so.per_billed) > 0 or flt(so.get("per_delivered")) > 0 or flt(so.get("advance_paid")) > 0


def _set_state(doc, state, message="", so_name=None, so_hash=None):
	vals = {"sync_state": state, "sync_error": message}
	if so_name is not None:
		vals["sales_order"] = so_name
	if so_hash is not None:
		vals["so_hash"] = so_hash
	doc.db_set(vals, update_modified=False)


def sync_sales_order(doc):
	"""Buat / perbarui / batalkan Sales Order agar sesuai booking. Gagal → dicatat, tidak dilempar."""
	s = _settings()
	frappe.db.savepoint("booking_so")
	try:
		so = None
		if doc.sales_order and frappe.db.exists("Sales Order", doc.sales_order):
			so = frappe.get_doc("Sales Order", doc.sales_order)
			if so.docstatus == 2:
				so = None  # dibatalkan → buat baru bila booking masih aktif

		if not _wants_so(doc, s):
			if not so:
				_set_state(doc, "Skipped" if doc.status != "cancelled" else "Synced", "", so_name=doc.sales_order or "")
				return
			if so.docstatus == 0:
				so.flags.from_booking_ops = True
				frappe.delete_doc("Sales Order", so.name, ignore_permissions=True, force=True)
				_set_state(doc, "Synced", _("SO draft dihapus (booking {0}).").format(doc.status), so_name="", so_hash="")
				log("Sistem", "SO dihapus", doc.name, message=so.name)
			elif _billed(so):
				_set_state(doc, "Needs Review", _("Booking {0}, tapi {1} sudah ditagih/dibayar — batalkan manual.").format(doc.status, so.name))
			elif cint(s.cancel_so_on_cancel):
				so.flags.ignore_permissions = True
				so.flags.from_booking_ops = True
				so.cancel()
				_set_state(doc, "Synced", _("{0} dibatalkan.").format(so.name))
				log("Sistem", "SO dibatalkan", doc.name, message=so.name)
			else:
				_set_state(doc, "Needs Review", _("Booking {0}; SO {1} masih aktif.").format(doc.status, so.name))
			return

		d = _desired_so(doc, s)
		h = _hash(d)
		if so and doc.so_hash == h:
			if doc.sync_state != "Synced":
				_set_state(doc, "Synced", "")
			return

		if not so:
			so = frappe.new_doc("Sales Order")
			so.order_type = "Sales"
			_apply(so, d)
			so.insert()
			if cint(s.auto_submit_so):
				so.submit()
			event = "SO dibuat"
		elif so.docstatus == 0:
			_apply(so, d)
			so.save()
			event = "SO diperbarui"
		elif _billed(so):
			_set_state(doc, "Needs Review", _("Booking berubah, tapi {0} sudah ditagih/dibayar — sesuaikan manual.").format(so.name))
			return
		else:
			# SO submitted belum ditagih → cancel + amend dengan data baru.
			so.flags.ignore_permissions = True
			so.flags.from_booking_ops = True
			so.cancel()
			new = frappe.copy_doc(so)
			new.amended_from = so.name
			_apply(new, d)
			new.insert()
			new.submit()
			so = new
			event = "SO di-amend"
		_set_state(doc, "Synced", "", so_name=so.name, so_hash=h)
		if doc.customer != d["customer"]:
			doc.db_set("customer", d["customer"], update_modified=False)
		log("Sistem", event, doc.name, message=so.name)
	except Exception as e:
		frappe.db.rollback(save_point="booking_so")
		msg = str(e) or e.__class__.__name__
		frappe.clear_messages()
		_set_state(doc, "Error", msg[:1000])
		log("Sistem", "SO gagal", doc.name, "Error", msg)


def on_sales_order_cancel(so, method=None):
	"""SO dibatalkan manual di Desk → tandai booking supaya terlihat di PWA."""
	if so.flags.get("from_booking_ops") or not so.get("beds24_booking"):
		return
	if frappe.db.exists("Beds24 Booking", so.beds24_booking):
		frappe.db.set_value(
			"Beds24 Booking",
			so.beds24_booking,
			{"sync_state": "Needs Review", "sync_error": _("{0} dibatalkan manual di ERPNext.").format(so.name)},
			update_modified=False,
		)


# ───────────────────────── Properti & kamar ─────────────────────────


def import_properties():
	props = beds24.get_properties()
	n_rooms = 0
	for p in props:
		pid = str(p.get("id"))
		doc = frappe.get_doc("Beds24 Property", pid) if frappe.db.exists("Beds24 Property", pid) else frappe.new_doc("Beds24 Property")
		cur = (p.get("currency") or "").upper()
		doc.update(
			{
				"property_id": pid,
				"property_name": p.get("name") or doc.property_name or pid,
				"currency": cur if cur and frappe.db.exists("Currency", cur) else doc.currency,
				"city": p.get("city") or "",
				"check_in_start": p.get("checkInStart") or "",
				"check_out_end": p.get("checkOutEnd") or "",
				"last_imported": now_datetime(),
			}
		)
		doc.save(ignore_permissions=True)
		for i, r in enumerate(p.get("roomTypes") or []):
			rid = str(r.get("id"))
			room = frappe.get_doc("Beds24 Room", rid) if frappe.db.exists("Beds24 Room", rid) else frappe.new_doc("Beds24 Room")
			units = [{"id": u.get("id"), "name": u.get("name") or str(u.get("id"))} for u in (r.get("units") or [])]
			room.update(
				{
					"room_id": rid,
					"property": pid,
					"room_name": r.get("name") or room.room_name or rid,
					"room_type": r.get("roomType") or "",
					"qty": cint(r.get("qty")) or len(units) or 1,
					"max_people": cint(r.get("maxPeople")),
					"rack_rate": flt(r.get("rackRate") or r.get("minPrice")),
					"units_json": json.dumps(units),
					"sort_order": room.sort_order or i + 1,
				}
			)
			room.save(ignore_permissions=True)
			n_rooms += 1
	frappe.db.commit()
	log("Masuk", "Impor properti", status="OK", message=f"{len(props)} properti · {n_rooms} tipe kamar")
	return {"properties": len(props), "rooms": n_rooms}


def daily():
	frappe.db.delete("Beds24 Sync Log", {"creation": ("<", add_days(now_datetime(), -30))})
	s = _settings()
	if cint(s.enable_sync) and (s.get_password("refresh_token", raise_exception=False) or s.get_password("long_life_token", raise_exception=False)):
		try:
			import_properties()
		except Exception as e:
			log("Masuk", "Impor properti", status="Error", message=str(e))


# ───────────────────────── Pesan tamu ─────────────────────────

MSG_LOCK = "booking_ops:msg_lock"
MSG_SOURCES = ("guest", "host", "system", "internalNote")


def map_message(m):
	return {
		"message_id": str(m.get("id")),
		"booking": str(m.get("bookingId")),
		"property": str(m.get("propertyId") or "") or None,
		"source": m.get("source") if m.get("source") in MSG_SOURCES else "system",
		"message": m.get("message") or "",
		"time": _dt(m.get("time")),
		# Pesan dari host/sistem tidak perlu "dibaca" → anggap sudah.
		"read": 1 if m.get("read") or m.get("source") != "guest" else 0,
		"attachment_name": m.get("attachmentName") or "",
	}


def _save_attachment(doc, m):
	"""Lampiran base64 dari Beds24 → File privat di pesan (sekali saja)."""
	raw = m.get("attachment")
	if not raw or doc.attachment:
		return
	import base64

	try:
		content = base64.b64decode(raw)
	except (ValueError, TypeError):
		return
	f = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": m.get("attachmentName") or f"lampiran-{doc.name}",
			"attached_to_doctype": "Beds24 Message",
			"attached_to_name": doc.name,
			"is_private": 1,
			"content": content,
		}
	).insert(ignore_permissions=True)
	doc.db_set("attachment", f.file_url, update_modified=False)


def upsert_message(m, sent_by=None):
	"""Simpan satu pesan Beds24. Kembalikan 'created' | 'updated' | 'unchanged' | 'skipped'."""
	data = map_message(m)
	if not m.get("id") or not m.get("bookingId"):
		return "skipped"
	if not frappe.db.exists("Beds24 Booking", data["booking"]):
		try:  # pesan untuk booking yang belum ada di ERPNext → ambil booking-nya dulu
			pull_one(data["booking"], source="message")
		except Exception as e:
			log("Masuk", "Pesan", data["booking"], "Dilewati", _("Booking belum ada: {0}").format(e))
			return "skipped"
	name = data["message_id"]
	if frappe.db.exists("Beds24 Message", name):
		doc = frappe.get_doc("Beds24 Message", name)
		# status dibaca lokal tidak ditimpa mundur (sudah dibaca di app, Beds24 belum tahu)
		data["read"] = max(cint(doc.read), data["read"])
		if all(str(doc.get(k) or "") == str(v or "") for k, v in data.items() if k != "time"):
			return "unchanged"
		doc.update(data)
		doc.save(ignore_permissions=True)
		res = "updated"
	else:
		doc = frappe.get_doc(dict(doctype="Beds24 Message", sent_by=sent_by, **data))
		doc.insert(ignore_permissions=True)
		res = "created"
	_save_attachment(doc, m)
	return res


def pull_messages(booking_id=None, max_age=None):
	"""Tarik pesan dari Beds24 (per booking, atau semua N hari terakhir)."""
	if not booking_id and frappe.cache.get_value(MSG_LOCK):
		return {"skipped": True, "message": _("Tarik pesan lain sedang berjalan.")}
	if not booking_id:
		frappe.cache.set_value(MSG_LOCK, 1, expires_in_sec=300)
	try:
		params = {"bookingId": [cint(booking_id)]} if booking_id else {"maxAge": cint(max_age) or 30}
		rows = beds24.get_messages(**params)
		stats = {"fetched": len(rows), "created": 0, "updated": 0, "unchanged": 0, "skipped": 0, "errors": 0}
		for m in sorted(rows, key=lambda x: x.get("time") or ""):
			try:
				stats[upsert_message(m)] += 1
			except Exception as e:
				stats["errors"] += 1
				log("Masuk", "Pesan", m.get("bookingId"), "Error", str(e), m)
		frappe.db.commit()
		if not booking_id and (stats["created"] or stats["errors"]):
			log("Masuk", "Tarik pesan", status="Error" if stats["errors"] else "OK",
				message=_("{created} pesan baru · {errors} gagal").format(**stats))
		return stats
	finally:
		if not booking_id:
			frappe.cache.delete_value(MSG_LOCK)


def scheduled_messages():
	s = _settings()
	if not cint(s.enable_sync) or not cint(s.get("enable_messages")) or not _connected(s):
		return
	try:
		pull_messages(max_age=cint(s.get("message_days")) or 2)
	except Exception as e:
		log("Masuk", "Tarik pesan berkala", status="Error", message=str(e))
