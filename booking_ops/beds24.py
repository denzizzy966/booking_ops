"""Klien Beds24 API v2 (https://beds24.com/api/v2).

Autentikasi: refresh token (dari invite code) → access token 24 jam, di-cache di redis.
Alternatif: long life token dipakai langsung. Semua request lewat `request()`.
Mode Sandbox (Booking Ops Settings) → `request()` dilayani `booking_ops.sandbox`, tanpa HTTP.
"""

import frappe
import requests
from frappe import _

from booking_ops import sandbox

TOKEN_CACHE_KEY = "booking_ops:beds24_token"
TIMEOUT = 30
MAX_PAGES = 100


class Beds24Error(frappe.ValidationError):
	pass


def _settings():
	return frappe.get_cached_doc("Booking Ops Settings")


def _base():
	return ((_settings().api_base or "https://beds24.com/api/v2").strip()).rstrip("/")


def _secret(field):
	return _settings().get_password(field, raise_exception=False) or ""


def connect(invite_code):
	"""Tukar invite code → refresh token (disimpan di Booking Ops Settings)."""
	if sandbox.active():
		return "SANDBOX"
	r = requests.get(
		f"{_base()}/authentication/setup",
		headers={"code": invite_code.strip(), "deviceName": "ERPNext Booking Ops"},
		timeout=TIMEOUT,
	)
	data = _json(r)
	if not r.ok or not data.get("refreshToken"):
		raise Beds24Error(_("Beds24 menolak invite code: {0}").format(_err_text(data, r)))
	frappe.cache.set_value(TOKEN_CACHE_KEY, data.get("token"), expires_in_sec=_ttl(data))
	return data["refreshToken"]


def _ttl(data):
	try:
		return max(int(data.get("expiresIn") or 86400) - 300, 60)
	except (TypeError, ValueError):
		return 3600


def access_token(force=False):
	long_life = _secret("long_life_token")
	if long_life:
		return long_life
	if not force:
		tok = frappe.cache.get_value(TOKEN_CACHE_KEY)
		if tok:
			return tok
	refresh = _secret("refresh_token")
	if not refresh:
		raise Beds24Error(_("Beds24 belum terhubung. Isi invite code di Booking Ops Settings lalu klik Hubungkan."))
	r = requests.get(f"{_base()}/authentication/token", headers={"refreshToken": refresh}, timeout=TIMEOUT)
	data = _json(r)
	if not r.ok or not data.get("token"):
		raise Beds24Error(_("Gagal memperbarui token Beds24: {0}").format(_err_text(data, r)))
	frappe.cache.set_value(TOKEN_CACHE_KEY, data["token"], expires_in_sec=_ttl(data))
	return data["token"]


def _json(r):
	try:
		return r.json()
	except ValueError:
		return {}


def _err_text(data, r):
	if isinstance(data, dict):
		msg = data.get("error") or data.get("message")
		if msg:
			return str(msg)
	return f"HTTP {r.status_code}"


def request(method, path, params=None, json=None, _retried=False):
	"""Satu request ber-token. 401 → token diperbarui sekali lalu diulang."""
	if sandbox.active():
		return sandbox.handle(method, path, params, json)
	r = requests.request(
		method,
		f"{_base()}{path}",
		params=_clean(params),
		json=json,
		headers={"token": access_token(force=_retried), "accept": "application/json"},
		timeout=TIMEOUT,
	)
	if r.status_code == 401 and not _retried and not _secret("long_life_token"):
		frappe.cache.delete_value(TOKEN_CACHE_KEY)
		return request(method, path, params, json, _retried=True)
	data = _json(r)
	if not r.ok or (isinstance(data, dict) and data.get("success") is False):
		raise Beds24Error(_("Beds24 {0} {1}: {2}").format(method, path, _err_text(data, r)))
	return data


def _clean(params):
	"""Buang None; boolean → 'true'/'false'; list → parameter berulang (requests)."""
	out = {}
	for k, v in (params or {}).items():
		if v is None or v == "" or v == []:
			continue
		out[k] = ("true" if v else "false") if isinstance(v, bool) else v
	return out


def get_all(path, params=None):
	"""GET berhalaman: gabungkan `data` dari semua halaman (pages.nextPageExists)."""
	params = dict(params or {})
	out = []
	for page in range(1, MAX_PAGES + 1):
		params["page"] = page
		data = request("GET", path, params)
		out.extend(data.get("data") or [])
		if not (data.get("pages") or {}).get("nextPageExists"):
			break
	return out


# ── Endpoint yang dipakai ──

ALL_STATUSES = ["confirmed", "request", "new", "cancelled", "black", "inquiry"]


def get_bookings(**filters):
	params = {"includeInvoiceItems": True, "includeInfoItems": True, "status": ALL_STATUSES}
	params.update(filters)
	return get_all("/bookings", params)


def get_booking(booking_id):
	rows = get_bookings(id=[int(booking_id)])
	return rows[0] if rows else None


def post_bookings(rows):
	"""POST /bookings (buat/ubah). Kembalikan list hasil per baris; error baris → Beds24Error."""
	res = request("POST", "/bookings", json=rows)
	res = res if isinstance(res, list) else [res]
	errors = []
	for item in res:
		if not item.get("success"):
			errs = item.get("errors") or []
			errors.append("; ".join(str(e.get("message") or e.get("action") or e) for e in errs) or str(item))
	if errors:
		raise Beds24Error(_("Beds24 menolak booking: {0}").format(" | ".join(errors)))
	return res


def get_properties():
	return get_all("/properties", {"includeAllRooms": True, "includeUnitDetails": True})


def get_availability(start, end, room_ids=None, property_ids=None):
	"""end = malam terakhir (sehari sebelum keberangkatan)."""
	return get_all(
		"/inventory/rooms/availability",
		{"startDate": start, "endDate": end, "roomId": room_ids, "propertyId": property_ids},
	)


def get_calendar(start, end, room_ids=None, property_ids=None):
	return get_all(
		"/inventory/rooms/calendar",
		{
			"startDate": start,
			"endDate": end,
			"roomId": room_ids,
			"propertyId": property_ids,
			"includeNumAvail": True,
			"includePrices": True,
			"includeMinStay": True,
		},
	)


def get_offers(arrival, departure, num_adult=1, num_child=0, room_ids=None, property_ids=None):
	return get_all(
		"/inventory/rooms/offers",
		{
			"arrival": arrival,
			"departure": departure,
			"numAdults": int(num_adult or 1),
			"numChildren": int(num_child or 0),
			"roomId": room_ids,
			"propertyId": property_ids,
		},
	)
