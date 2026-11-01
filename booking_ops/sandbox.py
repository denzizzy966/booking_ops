"""Mode Sandbox: Beds24 tiruan di dalam app, untuk mencoba Booking Ops tanpa akun Beds24.

Aktif bila Booking Ops Settings → Mode Sandbox dicentang. `beds24.request()` lalu memanggil
`handle()` di sini alih-alih HTTP ke beds24.com, dengan bentuk respons yang sama (apiV2.yaml).
Data contoh (2 properti, 4 tipe kamar, ±16 booking di sekitar hari ini) disimpan di file
private/booking_ops_sandbox.json milik site, jadi bertahan antar worker & restart.

Simulasi OTA (`simulate`) membuat/membatalkan booking "dari channel" lalu memprosesnya lewat
jalur yang sama dengan webhook, sehingga Sales Order ikut terbentuk/berubah.
"""

import json
import os
import random
from datetime import date, datetime, timedelta, timezone

import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.synchronization import filelock

ACTIVE = ("confirmed", "new", "request", "black")
OTA = ("booking", "airbnb", "agoda", "expedia", "traveloka", "tiket")

PROPS = [
	{"id": 1001, "name": "Sandbox Guesthouse Ubud", "currency": "IDR", "city": "Ubud", "checkInStart": "14:00", "checkOutEnd": "12:00",
	 "roomTypes": [
		{"id": 2001, "name": "Deluxe Double", "roomType": "double", "qty": 4, "maxPeople": 2, "rackRate": 650000, "units": [{"id": i, "name": f"{100 + i}"} for i in range(1, 5)]},
		{"id": 2002, "name": "Family Suite", "roomType": "family", "qty": 2, "maxPeople": 4, "rackRate": 1200000, "units": [{"id": i, "name": f"{200 + i}"} for i in range(1, 3)]},
		{"id": 2003, "name": "Standard Twin", "roomType": "twin", "qty": 3, "maxPeople": 2, "rackRate": 450000, "units": [{"id": i, "name": f"{300 + i}"} for i in range(1, 4)]},
	]},
	{"id": 1002, "name": "Sandbox Villa Seminyak", "currency": "IDR", "city": "Seminyak", "checkInStart": "15:00", "checkOutEnd": "11:00",
	 "roomTypes": [
		{"id": 2101, "name": "Private Pool Villa", "roomType": "villa", "qty": 2, "maxPeople": 4, "rackRate": 2500000, "units": [{"id": 1, "name": "Villa A"}, {"id": 2, "name": "Villa B"}]},
	]},
]
ROOMS = {r["id"]: dict(r, propertyId=p["id"]) for p in PROPS for r in p["roomTypes"]}

GUESTS = [
	("Budi", "Santoso", "ID"), ("Sarah", "Miller", "AU"), ("Ketut", "Arsana", "ID"), ("Hiroshi", "Tanaka", "JP"),
	("Maria", "Garcia", "ES"), ("Dewi", "Lestari", "ID"), ("Thomas", "Müller", "DE"), ("Olivia", "Brown", "GB"),
	("Agus", "Wijaya", "ID"), ("Emma", "Wilson", "US"), ("Rina", "Kurnia", "ID"), ("Lucas", "Martin", "FR"),
	("Putu", "Ayu", "ID"), ("Kim", "Jiwoo", "KR"), ("Liam", "Smith", "AU"), ("Wayan", "Sudarma", "ID"),
]

GUEST_MSGS = [
	"Hi, what time can we check in? Our flight lands at 11am.",
	"Halo, apakah bisa minta extra bed untuk anak?",
	"Is airport pickup available? How much does it cost?",
	"Can we leave our luggage after check-out?",
	"Selamat siang, apakah sarapan sudah termasuk?",
	"We will arrive late, around 11pm. Is that ok?",
	"Could you recommend a good restaurant nearby?",
	"Apakah ada parkir untuk mobil?",
]


def active():
	return cint(frappe.get_cached_doc("Booking Ops Settings").get("sandbox_mode"))


# ───────────────────────── Penyimpanan ─────────────────────────


def _path():
	return frappe.get_site_path("private", "booking_ops_sandbox.json")


def _now():
	return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load():
	try:
		with open(_path(), encoding="utf-8") as fh:
			state = json.load(fh)
	except (OSError, ValueError):
		return _seed()
	state.setdefault("messages", {})  # file dari versi sebelum fitur pesan
	state.setdefault("next_msg_id", 900001)
	return state


def _save(state):
	tmp = _path() + ".tmp"
	with open(tmp, "w", encoding="utf-8") as fh:
		json.dump(state, fh, ensure_ascii=False)
	os.replace(tmp, _path())


def _with_state(fn):
	"""Baca-ubah-tulis state di bawah file lock (aman untuk beberapa worker)."""
	with filelock("booking_ops_sandbox", timeout=20):
		state = _load()
		out = fn(state)
		_save(state)
		return out


# ───────────────────────── Data contoh ─────────────────────────


def _mk(state, room, unit, arrival, nights, first, last, country, channel, status="confirmed", price=None, paid=0, **kw):
	i = state["next_id"]
	state["next_id"] += 1
	rate = ROOMS[room]["rackRate"]
	price = rate * nights if price is None else price
	inv = []
	if price:
		inv.append({"id": i * 10 + 1, "type": "charge", "description": ROOMS[room]["name"], "qty": nights, "amount": price / nights, "lineTotal": price, "createTime": _now()})
	if paid:
		inv.append({"id": i * 10 + 2, "type": "payment", "description": "Transfer bank", "qty": 1, "amount": paid, "lineTotal": paid, "createTime": _now()})
	ota = channel in OTA
	b = {
		"id": i, "propertyId": ROOMS[room]["propertyId"], "roomId": room, "unitId": unit, "roomQty": 1,
		"status": status, "subStatus": "none", "arrival": str(arrival), "departure": str(arrival + timedelta(days=nights)),
		"numAdult": 2, "numChild": 0, "title": "", "firstName": first, "lastName": last,
		"email": f"{first.lower()}.{last.lower()}@example.com" if last else "", "phone": "",
		"mobile": f"+62812{i:07d}" if first else "", "country2": country, "channel": channel, "apiSource": channel,
		"referer": channel, "apiReference": f"{channel[:3].upper()}-{i}" if ota else "", "price": price,
		"deposit": 0, "tax": 0, "commission": round(price * 0.15) if channel in ("booking", "agoda", "expedia") else 0,
		"arrivalTime": "14:00", "comments": "", "notes": "", "bookingTime": _now(), "modifiedTime": _now(),
		"cancelTime": None, "invoiceItems": inv, "infoItems": [],
	}
	b.update(kw)
	state["bookings"][str(i)] = b
	return b


def _seed():
	t = date.today()
	d = lambda n: t + timedelta(days=n)  # noqa: E731
	state = {"seeded": str(t), "next_id": 50001, "bookings": {}}
	g = iter(GUESTS)
	for room, unit, a, n, ch, kw in [
		(2001, 1, 0, 2, "booking", {}),
		(2002, 1, 0, 3, "airbnb", {"paid": 3600000, "numChild": 2}),
		(2003, None, 0, 1, "direct", {}),
		(2001, 2, -2, 2, "agoda", {"paid": 1300000}),
		(2003, 2, -3, 3, "expedia", {}),
		(2001, 3, -1, 3, "traveloka", {}),
		(2002, 2, -1, 4, "booking", {}),
		(2101, 1, -2, 5, "airbnb", {"paid": 12500000}),
		(2001, 4, 1, 2, "direct", {}),
		(2002, None, 2, 2, "booking", {}),
		(2003, 1, 3, 4, "tiket", {}),
		(2101, 2, 5, 3, "expedia", {}),
		(2001, 1, 6, 2, "direct", {"status": "request"}),
		(2003, 3, -9, 2, "booking", {}),
		(2001, 2, 4, 2, "agoda", {"status": "cancelled", "cancelTime": _now(), "subStatus": "cancelledByGuest"}),
	]:
		first, last, country = next(g)
		_mk(state, room, unit, d(a), n, first, last, country, ch, **kw)
	_mk(state, 2101, 1, d(8), 3, "", "", "", "", status="black", price=0, notes="Perawatan kolam")
	state["messages"], state["next_msg_id"] = {}, 900001
	for bid, src, text, hours, read in [
		(50001, "system", "Booking.com: reservation confirmed.", 50, True),
		(50001, "guest", "Hi! Is early check-in possible? We arrive at 10am.", 5, False),
		(50002, "guest", "Hello, can you arrange airport pickup for 4 people?", 26, True),
		(50002, "host", "Hi Sarah, yes we can. IDR 350.000 per car. Shall we book it?", 25, True),
		(50002, "guest", "Yes please, flight QZ 512 landing 13:20. Thanks!", 3, False),
		(50010, "guest", "Halo, apakah kamarnya ada bathtub?", 1, False),
		(50012, "internalNote", "Tamu VIP, siapkan welcome drink.", 30, True),
	]:
		_msg(state, bid, src, text, time=_ago(hours), read=read)
	return state


def _ago(hours):
	return (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _msg(state, booking_id, source, text, time=None, read=None, **kw):
	i = state["next_msg_id"]
	state["next_msg_id"] += 1
	b = state["bookings"].get(str(booking_id)) or {}
	m = {
		"id": i, "bookingId": int(booking_id), "roomId": b.get("roomId"), "propertyId": b.get("propertyId"),
		"time": time or _now(), "read": (source != "guest") if read is None else read, "message": text,
		"source": source, "attachment": None, "attachmentName": None, "attachmentMimeType": None,
	}
	m.update(kw)
	state["messages"][str(i)] = m
	return m


def _busy(state, room, arrival, departure, exclude=None):
	return [
		b for b in state["bookings"].values()
		if b["roomId"] == room and b["status"] in ACTIVE and b["arrival"] < departure and arrival < b["departure"] and b["id"] != exclude
	]


def _free_unit(state, room, arrival, departure, exclude=None):
	taken = {b.get("unitId") for b in _busy(state, room, arrival, departure, exclude)}
	return next((u["id"] for u in ROOMS[room]["units"] if u["id"] not in taken), None)


# ───────────────────────── API tiruan ─────────────────────────


def _list(v):
	if v is None:
		return []
	return list(v) if isinstance(v, (list, tuple, set)) else [v]


def _ok(rows):
	return {"success": True, "type": "x", "count": len(rows), "pages": {"nextPageExists": False, "nextPageLink": None}, "data": rows}


def _err(msg):
	from booking_ops.beds24 import Beds24Error

	raise Beds24Error(_("Beds24 (sandbox): {0}").format(msg))


def handle(method, path, params=None, body=None):
	q = params or {}
	if method == "GET":
		if path == "/properties":
			return _ok(PROPS)
		state = _load()
		if path == "/bookings":
			return _ok(_bookings(state, q))
		if path.startswith("/inventory/rooms/"):
			return _ok(_inventory(state, path.rsplit("/", 1)[-1], q))
		if path == "/bookings/messages":
			return _ok(_messages(state, q))
	elif method == "POST" and path == "/bookings":
		return _with_state(lambda state: [_write(state, dict(r)) for r in _list(body)])
	elif method == "POST" and path == "/bookings/messages":
		return _with_state(lambda state: [_write_message(state, dict(r)) for r in _list(body)])
	_err(f"{method} {path} tidak didukung")


def _bookings(state, q):
	rows = sorted(state["bookings"].values(), key=lambda b: b["id"])
	statuses = set(_list(q.get("status"))) or {"confirmed", "request", "new", "black", "inquiry"}
	rows = [b for b in rows if b["status"] in statuses]
	ids = {cint(x) for x in _list(q.get("id"))}
	if ids:
		rows = [b for b in rows if b["id"] in ids]
	if q.get("arrivalFrom"):
		rows = [b for b in rows if b["arrival"] >= str(q["arrivalFrom"])]
	if q.get("modifiedFrom"):
		rows = [b for b in rows if b["modifiedTime"][:19] >= str(q["modifiedFrom"])[:19]]
	pids = {cint(x) for x in _list(q.get("propertyId"))}
	if pids:
		rows = [b for b in rows if b["propertyId"] in pids]
	return rows


def _messages(state, q):
	rows = sorted(state["messages"].values(), key=lambda m: m["time"])
	ids = {cint(x) for x in _list(q.get("bookingId"))}
	if ids:
		rows = [m for m in rows if m["bookingId"] in ids]
	pids = {cint(x) for x in _list(q.get("propertyId"))}
	if pids:
		rows = [m for m in rows if m["propertyId"] in pids]
	if q.get("filter") in ("read", "unread"):
		want = q["filter"] == "read"
		rows = [m for m in rows if bool(m["read"]) == want]
	if q.get("source"):
		rows = [m for m in rows if m["source"] == q["source"]]
	if q.get("maxAge"):
		since = _ago(24 * cint(q["maxAge"]))
		rows = [m for m in rows if m["time"] >= since]
	return rows


def _write_message(state, r):
	if r.get("id"):
		m = state["messages"].get(str(cint(r["id"])))
		if not m:
			return {"success": False, "errors": [{"action": "modify", "message": "Message not found"}]}
		if "read" in r:
			m["read"] = bool(r["read"])
		return {"success": True, "modified": {"id": m["id"]}}
	if str(cint(r.get("bookingId"))) not in state["bookings"]:
		return {"success": False, "errors": [{"action": "create", "message": "Invalid bookingId"}]}
	if not (r.get("message") or r.get("attachment")):
		return {"success": False, "errors": [{"action": "create", "message": "Message is empty"}]}
	m = _msg(state, r["bookingId"], r.get("source") or "host", r.get("message") or "",
			 attachment=r.get("attachment"), attachmentName=r.get("attachmentName"), attachmentMimeType=r.get("attachmentMimeType"))
	return {"success": True, "new": {"id": m["id"]}}


def _inventory(state, kind, q):
	pids = {cint(x) for x in _list(q.get("propertyId"))}
	rids = {cint(x) for x in _list(q.get("roomId"))}
	rooms = [r for r in ROOMS.values() if (not pids or r["propertyId"] in pids) and (not rids or r["id"] in rids)]
	out = []
	if kind == "offers":
		a, dep = str(q["arrival"]), str(q["departure"])
		nights = (date.fromisoformat(dep) - date.fromisoformat(a)).days
		people = cint(q.get("numAdults") or 1) + cint(q.get("numChildren"))
		for r in rooms:
			free = r["qty"] - len(_busy(state, r["id"], a, dep))
			offers = [{"offerId": 1, "offerName": "Standard", "price": r["rackRate"] * nights, "unitsAvailable": free}] if free > 0 and people <= r["maxPeople"] else []
			out.append({"roomId": r["id"], "propertyId": r["propertyId"], "offers": offers})
		return out
	start, end = date.fromisoformat(str(q["startDate"])), date.fromisoformat(str(q["endDate"]))
	for r in rooms:
		days, cal, x = {}, [], start
		while x <= end:
			free = r["qty"] - len(_busy(state, r["id"], str(x), str(x + timedelta(days=1))))
			weekend = x.weekday() >= 4
			days[str(x)] = free > 0
			cal.append({"from": str(x), "to": str(x), "numAvail": free, "price1": r["rackRate"] * (1.2 if weekend else 1), "minStay": 2 if weekend and r["id"] == 2101 else 1})
			x += timedelta(days=1)
		if kind == "availability":
			out.append({"roomId": r["id"], "propertyId": r["propertyId"], "name": r["name"], "availability": days})
		else:
			out.append({"roomId": r["id"], "propertyId": r["propertyId"], "calendar": cal})
	return out


def _write(state, r):
	actions = r.pop("actions", None) or {}
	if r.get("id"):
		b = state["bookings"].get(str(cint(r["id"])))
		if not b:
			return {"success": False, "errors": [{"action": "modify", "message": "Booking not found"}]}
		if {"arrival", "departure", "roomId"} & set(r) and r.get("status", b["status"]) != "cancelled":
			room = cint(r.get("roomId", b["roomId"]))
			a, dep = r.get("arrival", b["arrival"]), r.get("departure", b["departure"])
			if room not in ROOMS or len(_busy(state, room, a, dep, exclude=b["id"])) >= ROOMS[room]["qty"]:
				return {"success": False, "errors": [{"action": "modify", "message": "No availability for the requested dates"}]}
		b.update(r)
		if r.get("status") == "cancelled":
			b["cancelTime"] = _now()
		if "price" in r and b["invoiceItems"]:
			nights = (date.fromisoformat(b["departure"]) - date.fromisoformat(b["arrival"])).days or 1
			b["invoiceItems"][0].update({"qty": nights, "amount": float(r["price"]) / nights, "lineTotal": float(r["price"])})
		b["modifiedTime"] = _now()
		return {"success": True, "modified": {"id": b["id"]}}

	room = cint(r.get("roomId"))
	if room not in ROOMS:
		return {"success": False, "errors": [{"action": "create", "message": "Invalid roomId"}]}
	if actions.get("checkAvailability") and len(_busy(state, room, r["arrival"], r["departure"])) >= ROOMS[room]["qty"]:
		return {"success": False, "errors": [{"action": "create", "message": "No availability"}]}
	arrival = date.fromisoformat(r["arrival"])
	nights = (date.fromisoformat(r["departure"]) - arrival).days
	b = _mk(state, room, r.get("unitId"), arrival, nights, r.get("firstName", ""), r.get("lastName", ""), r.get("country2", ""), "direct", price=float(r.get("price") or 0))
	b.update(r)
	b.update({"propertyId": ROOMS[room]["propertyId"], "channel": "direct", "apiSource": "API"})
	if not actions.get("autoInvoiceItemCharge"):
		b["invoiceItems"] = []
	return {"success": True, "new": {"id": b["id"]}}


# ───────────────────────── Tombol sandbox ─────────────────────────


def _require_active():
	if not active():
		frappe.throw(_("Mode Sandbox tidak aktif."))


def reset():
	"""Kembalikan data contoh Beds24 tiruan (dokumen di ERPNext tidak dihapus)."""
	_require_active()
	with filelock("booking_ops_sandbox", timeout=20):
		state = _seed()
		old = _load_raw_next_id()
		state["next_id"] = max(state["next_id"], old)  # id baru tak bentrok dengan booking lama di ERPNext
		state["next_msg_id"] = max(state["next_msg_id"], _load_raw_next_id("next_msg_id"))
		_save(state)
	frappe.db.set_single_value("Booking Ops Settings", "pull_cursor", None)
	from booking_ops import sync

	out = sync.pull_changes(full=True)
	out["messages"] = sync.pull_messages(max_age=30).get("created", 0)
	return out


def _load_raw_next_id(key="next_id"):
	try:
		with open(_path(), encoding="utf-8") as fh:
			return cint(json.load(fh).get(key))
	except (OSError, ValueError):
		return 0


def simulate(kind="new"):
	"""Seolah-olah ada booking baru / pembatalan dari OTA, lalu diproses seperti webhook."""
	_require_active()
	from booking_ops import sync

	def new(state):
		today = date.today()
		for _try in range(40):
			room = random.choice(list(ROOMS))
			arrival = today + timedelta(days=random.randint(0, 14))
			nights = random.randint(1, 4)
			dep = str(arrival + timedelta(days=nights))
			unit = _free_unit(state, room, str(arrival), dep)
			if unit is not None:
				first, last, country = random.choice(GUESTS)
				return _mk(state, room, unit, arrival, nights, first, last, country, random.choice(OTA),
						   numAdult=random.randint(1, ROOMS[room]["maxPeople"]))
		frappe.throw(_("Sandbox penuh: tidak ada kamar kosong 2 minggu ke depan. Klik Reset Data Sandbox."))

	def cancel(state):
		today = str(date.today())
		rows = [b for b in state["bookings"].values() if b["status"] in ("confirmed", "new") and b["channel"] in OTA and b["arrival"] > today]
		if not rows:
			frappe.throw(_("Tidak ada booking OTA yang akan datang untuk dibatalkan."))
		b = random.choice(rows)
		b.update({"status": "cancelled", "subStatus": "cancelledByGuest", "cancelTime": _now(), "modifiedTime": _now()})
		return b

	if kind == "message":
		return _simulate_message()
	if kind not in ("new", "cancel"):
		frappe.throw(_("Jenis simulasi tidak dikenal."))
	b = _with_state(new if kind == "new" else cancel)
	doc = sync.pull_one(b["id"], source="webhook")
	sync.log("Masuk", "Webhook (sandbox)", b["id"], message=b["status"])
	frappe.db.commit()
	return {
		"booking_id": doc.name,
		"guest_name": doc.guest_name,
		"channel": doc.channel,
		"status": doc.status,
		"arrival": str(doc.arrival),
		"departure": str(doc.departure),
		"sales_order": doc.sales_order,
		"sync_state": doc.sync_state,
	}


def _simulate_message():
	"""Tamu (booking OTA yang akan datang / sedang menginap) mengirim pesan."""
	from booking_ops import sync

	def add(state):
		today = date.today()
		lo, hi = str(today - timedelta(days=3)), str(today + timedelta(days=10))
		rows = [
			b for b in state["bookings"].values()
			if b["status"] in ("confirmed", "new") and b["channel"] in OTA and lo <= b["arrival"] <= hi
			and frappe.db.exists("Beds24 Booking", str(b["id"]))
		]
		if not rows:
			frappe.throw(_("Tidak ada booking OTA aktif untuk dikirimi pesan. Klik Reset Data Sandbox."))
		b = random.choice(rows)
		return _msg(state, b["id"], "guest", random.choice(GUEST_MSGS))

	m = _with_state(add)
	sync.pull_messages(booking_id=m["bookingId"])
	sync.log("Masuk", "Pesan tamu (sandbox)", m["bookingId"], message=m["message"][:140])
	frappe.db.commit()
	b = frappe.db.get_value("Beds24 Booking", str(m["bookingId"]), ["guest_name", "channel"], as_dict=True)
	return {"booking_id": str(m["bookingId"]), "guest_name": b.guest_name, "channel": b.channel, "message": m["message"]}


def setup_demo(company=None):
	"""Satu perintah untuk mencoba di server uji:
	bench --site <site> execute booking_ops.sandbox.setup_demo [--kwargs "{'company': 'Nama PT'}"]

	Menyalakan sandbox + sinkron otomatis, mengisi setelan Sales Order yang kosong (Item jasa
	KAMAR-SANDBOX dibuat bila perlu), mengimpor properti contoh, lalu menarik semua booking.
	"""
	frappe.set_user("Administrator")
	s = frappe.get_doc("Booking Ops Settings")
	s.sandbox_mode = 1
	s.enable_sync = 1
	s.company = company or s.company or frappe.defaults.get_global_default("company") or frappe.get_all("Company", pluck="name", limit=1)[0]
	if not s.default_item:
		s.default_item = _service_item("KAMAR-SANDBOX", "Kamar Hotel (Sandbox)")
	s.customer_group = s.customer_group or _leaf("Customer Group", ["Individual", "Commercial"])
	s.territory = s.territory or _leaf("Territory", ["Indonesia", "Rest Of The World"])
	s.save()
	frappe.db.commit()
	from booking_ops import sync

	props = sync.import_properties()
	pulled = reset()
	frappe.db.commit()
	out = {"company": s.company, "item": s.default_item, **props, **pulled}
	print(out)
	return out


def _leaf(doctype, prefer):
	for name in prefer:
		if frappe.db.exists(doctype, name) and not frappe.db.get_value(doctype, name, "is_group"):
			return name
	rows = frappe.get_all(doctype, {"is_group": 0}, pluck="name", limit=1)
	return rows[0] if rows else None


def _service_item(code, name):
	if not frappe.db.exists("Item", code):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": name,
				"item_group": _leaf("Item Group", ["Services", "Layanan"]),
				"stock_uom": "Nos" if frappe.db.exists("UOM", "Nos") else frappe.get_all("UOM", pluck="name", limit=1)[0],
				"is_stock_item": 0,
				"include_item_in_manufacturing": 0,
			}
		).insert(ignore_permissions=True)
	return code
