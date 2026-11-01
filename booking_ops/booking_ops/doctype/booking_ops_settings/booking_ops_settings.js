const M = 'booking_ops.booking_ops.doctype.booking_ops_settings.booking_ops_settings.'

function run(frm, method, args, busy) {
	return frappe.call({ method: M + method, args: args || {}, freeze: true, freeze_message: busy })
		.then((r) => { frm.reload_doc(); return r.message })
}

function simulate(frm, kind) {
	run(frm, 'sandbox_simulate', { kind }, __('Mengirim simulasi webhook…')).then((m) => {
		const so = m.sales_order ? __('Sales Order {0}', [`<a href="/app/sales-order/${m.sales_order}">${m.sales_order}</a>`]) : __('tanpa Sales Order ({0})', [m.sync_state])
		frappe.msgprint({
			title: kind === 'new' ? __('Booking baru masuk') : __('Booking dibatalkan'),
			indicator: kind === 'new' ? 'green' : 'orange',
			message: `<b>#${m.booking_id}</b> · ${frappe.utils.escape_html(m.guest_name || '')} · ${m.channel}<br>${m.arrival} → ${m.departure}<br>${so}`,
		})
	})
}

frappe.ui.form.on('Booking Ops Settings', {
	refresh(frm) {
		frm.add_custom_button(__('Buka Aplikasi'), () => window.open('/booking_ops', '_blank'))
	},
	connect_btn(frm) {
		const go = () => run(frm, 'connect', {}, __('Menghubungkan ke Beds24…'))
			.then((m) => frappe.show_alert({ message: m.status, indicator: m.ok ? 'green' : 'red' }))
		frm.is_dirty() ? frm.save().then(go) : go()
	},
	test_btn(frm) {
		run(frm, 'test_connection', {}, __('Mengetes koneksi…'))
			.then((m) => frappe.show_alert({ message: m.status, indicator: m.ok ? 'green' : 'red' }))
	},
	import_btn(frm) {
		run(frm, 'import_properties', {}, __('Mengambil properti & kamar…')).then((m) =>
			frappe.msgprint(__('{0} properti, {1} tipe kamar diambil. Petakan Item ERPNext di daftar Beds24 Room.', [m.properties, m.rooms])))
	},
	pull_btn(frm) {
		run(frm, 'pull_now', {}, __('Sinkron booking…')).then((m) =>
			frappe.show_alert({ message: m.skipped ? m.message : __('{0} diambil · {1} baru · {2} berubah · {3} gagal', [m.fetched, m.created, m.updated, m.errors]), indicator: m.errors ? 'orange' : 'green' }))
	},
	sandbox_ota_btn(frm) { simulate(frm, 'new') },
	sandbox_cancel_btn(frm) { simulate(frm, 'cancel') },
	sandbox_reset_btn(frm) {
		frappe.confirm(__('Kembalikan data contoh sandbox lalu tarik ulang semua booking? Dokumen ERPNext yang sudah ada tidak dihapus.'), () =>
			run(frm, 'sandbox_reset', {}, __('Menyiapkan data sandbox…')).then((m) =>
				frappe.show_alert({ message: __('{0} booking diambil · {1} baru · {2} berubah · {3} gagal', [m.fetched, m.created, m.updated, m.errors]), indicator: m.errors ? 'orange' : 'green' })))
	},
	full_pull_btn(frm) {
		frappe.confirm(__('Tarik ulang semua booking sejak {0} hari lalu? Berjalan di latar.', [frm.doc.initial_days_back || 30]), () =>
			run(frm, 'pull_now', { full: 1 }).then(() => frappe.show_alert(__('Dijadwalkan. Lihat Beds24 Sync Log.'))))
	},
})
