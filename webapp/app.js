/* ECO · Telegram Mini App & Multi-Tier Platform (Customer, Dealer, SuperAdmin) */
(function () {
  "use strict";

  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  const DEFAULT_COORDS = { lat: 41.2995, lon: 69.2401 };

  const state = {
    user: null,
    products: [],
    cart: { items: [], total: 0, total_qty: 0, max_qty: 50 },
    orders: [],
    regions: [],
    statuses: {},
    flow: [],
    activeTab: "catalog",
    activeSuperTab: "overview",
    activeDealerTab: "overview",
    modalProductId: null,
    superData: null,
    dealerData: null,
    map: null,
    marker: null,
    lat: DEFAULT_COORDS.lat,
    lon: DEFAULT_COORDS.lon,
    orderPlacedSuccess: false,
    selectedRegionId: null,
    selectedDistrict: null,
    currentShipmentConfirmId: null,
  };

  // ---------------- Yordamchilar ----------------
  function esc(val) {
    return String(val ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function money(n) {
    return Number(n || 0)
      .toLocaleString("en-US")
      .replace(/,/g, " ");
  }

  function fmtDt(s) {
    if (!s) return "-";
    const m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})/.exec(s);
    if (!m) return s;
    return `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}`;
  }

  function haptic(type = "light") {
    try {
      if (tg && tg.HapticFeedback) {
        if (type === "select") tg.HapticFeedback.selectionChanged();
        else tg.HapticFeedback.impactOccurred(type);
      }
    } catch (_) {}
  }

  let toastTimer = null;
  function showToast(msg, isError = false) {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.toggle("error", Boolean(isError));
    el.classList.remove("hidden");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add("hidden"), 2800);
  }

  async function api(path, options = {}) {
    const headers = Object.assign(
      { "Content-Type": "application/json" },
      options.headers || {}
    );
    if (tg && tg.initData) {
      headers["X-Telegram-Init-Data"] = tg.initData;
    }
    const res = await fetch(path, Object.assign({}, options, { headers }));
    let data = {};
    try {
      data = await res.json();
    } catch (_) {}
    if (!res.ok || data.ok === false) {
      const err = new Error(data.error || "Server bilan bog'lanishda xatolik");
      err.status = res.status;
      err.code = data.code;
      throw err;
    }
    return data;
  }

  function getCartQty(pid) {
    const item = state.cart.items.find((i) => i.product_id === pid);
    return item ? item.qty : 0;
  }

  function supportsTgContact() {
    return Boolean(tg && tg.initData && typeof tg.requestContact === "function");
  }

  function openModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove("hidden");
  }

  function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add("hidden");
  }

  // ---------------- Ko'rinishlar Boshqaruvi ----------------
  function hideAllViews() {
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  }

  function showCustomerTab(tab) {
    state.activeTab = tab;
    if (tab !== "cart") state.orderPlacedSuccess = false;

    document.querySelectorAll("#customerNav .nav-item").forEach((b) => {
      b.classList.toggle("active", b.dataset.tab === tab);
    });

    hideAllViews();
    const mapTabToView = {
      catalog: "viewCatalog",
      cart: "viewCart",
      orders: "viewOrders",
      profile: "viewProfile",
    };
    const target = document.getElementById(mapTabToView[tab] || "viewCatalog");
    if (target) target.classList.add("active");
    updateFloatingCartBar();

    if (tab === "cart") {
      renderCart();
      setTimeout(ensureMapInitialized, 60);
    } else if (tab === "orders") {
      refreshOrders();
    } else if (tab === "profile") {
      renderProfile();
    }
    haptic("select");
  }

  function showSuperTab(tab) {
    if (!state.user || !state.user.is_superadmin) return;
    state.activeSuperTab = tab;

    document.querySelectorAll("#superadminNav .nav-item").forEach((b) => {
      b.classList.toggle("active", b.dataset.superTab === tab);
    });

    hideAllViews();
    renderHeader();

    if (tab === "catalog") {
      const v = document.getElementById("viewCatalog");
      if (v) v.classList.add("active");
      renderCatalog();
      updateFloatingCartBar();
      haptic("select");
      return;
    }

    const mapTab = {
      overview: "viewSuperOverview",
      factory: "viewSuperFactory",
      shipments: "viewSuperShipments",
      dealers: "viewSuperDealers",
      products: "viewSuperProducts",
      orders: "viewSuperOrders",
      audit: "viewSuperAudit",
    };
    const target = document.getElementById(mapTab[tab] || "viewSuperOverview");
    if (target) target.classList.add("active");

    if (tab === "overview") loadSuperOverview();
    else if (tab === "factory") loadSuperFactory();
    else if (tab === "shipments") loadSuperShipments();
    else if (tab === "dealers") loadSuperDealers();
    else if (tab === "products") loadSuperProducts();
    else if (tab === "orders") loadSuperOrders();
    else if (tab === "audit") loadSuperAudit();
    haptic("select");
  }

  function showDealerTab(tab) {
    if (!state.user || !state.user.is_dealer) return;
    state.activeDealerTab = tab;

    document.querySelectorAll("#dealerNav .nav-item").forEach((b) => {
      b.classList.toggle("active", b.dataset.dealerTab === tab);
    });

    hideAllViews();
    const mapTab = {
      overview: "viewDealerOverview",
      inventory: "viewDealerInventory",
      shipments: "viewDealerShipments",
      orders: "viewDealerOrders",
      customers: "viewDealerCustomers",
      finance: "viewDealerFinance",
    };
    const target = document.getElementById(mapTab[tab] || "viewDealerOverview");
    if (target) target.classList.add("active");

    if (tab === "overview") loadDealerOverview();
    else if (tab === "inventory") loadDealerInventory();
    else if (tab === "shipments") loadDealerShipments();
    else if (tab === "orders") loadDealerOrders();
    else if (tab === "customers") loadDealerCustomers();
    else if (tab === "finance") loadDealerFinance();
    haptic("select");
  }

  function updateFloatingCartBar() {
    const bar = document.getElementById("floatingCartBar");
    if (!bar) return;
    if (state.user && state.user.is_dealer) {
      bar.classList.add("hidden");
      return;
    }
    if (state.user && state.user.is_superadmin && state.activeSuperTab !== "catalog") {
      bar.classList.add("hidden");
      return;
    }
    const hasItems = state.cart.total_qty > 0;
    const isCartView = state.activeTab === "cart";
    if (hasItems && !isCartView) {
      document.getElementById("floatingCartCount").textContent = `${state.cart.total_qty} ta`;
      document.getElementById("floatingCartTotal").textContent = `${money(state.cart.total)} so'm`;
      bar.classList.remove("hidden");
    } else {
      bar.classList.add("hidden");
    }
  }

  function renderHeader() {
    const u = state.user;
    if (!u) return;

    const sub = document.getElementById("brandSubTitle");
    const nameEl = document.getElementById("userBadgeName");
    const modeBtn = document.getElementById("btnToggleAdminMode");

    if (u.is_superadmin) {
      nameEl.textContent = `👑 SuperAdmin: ${u.name}`;
      if (modeBtn) {
        modeBtn.classList.remove("hidden");
        const inShop = state.activeSuperTab === "catalog";
        modeBtn.textContent = inShop ? "👑 Zavod Paneli" : "🛍 Tovarlarga o'tish";
      }
      sub.textContent = state.activeSuperTab === "catalog" ? "INNOVATION TOBACCO" : "ZAVOD BOSHQARUV PANELI";
      document.getElementById("customerNav").classList.add("hidden");
      document.getElementById("dealerNav").classList.add("hidden");
      document.getElementById("superadminNav").classList.remove("hidden");
      document.getElementById("ageGateModal").classList.add("hidden");
    } else if (u.is_dealer) {
      const reg = u.dealer_info ? u.dealer_info.region_name : "Hududiy";
      sub.textContent = `DILER · ${reg.toUpperCase()}`;
      nameEl.textContent = `🛡 Diler: ${u.name}`;
      if (modeBtn) modeBtn.classList.add("hidden");
      document.getElementById("customerNav").classList.add("hidden");
      document.getElementById("superadminNav").classList.add("hidden");
      document.getElementById("dealerNav").classList.remove("hidden");
      document.getElementById("floatingCartBar").classList.add("hidden");
      document.getElementById("ageGateModal").classList.add("hidden");
    } else {
      sub.textContent = "INNOVATION TOBACCO";
      nameEl.textContent = u.name || "Mijoz";
      if (modeBtn) modeBtn.classList.add("hidden");
      document.getElementById("superadminNav").classList.add("hidden");
      document.getElementById("dealerNav").classList.add("hidden");
      document.getElementById("customerNav").classList.remove("hidden");
    }
  }

  // ==================== MIJOZ QISMI (KATALOG, SAVATCHA, PROFIL) ====================
  function renderCatalog() {
    const grid = document.getElementById("catalogGrid");
    if (!grid) return;
    document.getElementById("productCountLabel").textContent = `${state.products.length} turdagi mahsulot`;

    grid.innerHTML = state.products
      .map((p) => {
        const qty = getCartQty(p.id);
        const keyClass = esc(p.key);
        const imgHtml = p.image_url
          ? `<img src="${esc(p.image_url)}" alt="${esc(p.name)}" loading="lazy" />`
          : "";
        const controlHtml = `
          <div class="qty-pill ${qty === 0 ? "is-zero" : ""}" data-pid="${p.id}">
            <button type="button" data-action="dec" data-pid="${p.id}" ${qty === 0 ? "disabled" : ""} aria-label="Kamaytirish">−</button>
            <span>${qty}</span>
            <button type="button" data-action="inc" data-pid="${p.id}" aria-label="Ko'paytirish">+</button>
          </div>`;

        return `
          <article class="product-card ${qty > 0 ? "in-cart" : ""}" data-pid="${p.id}">
            <div class="product-media" data-action="detail" data-pid="${p.id}">
              ${imgHtml}
              <span class="variant-tag ${keyClass}">${esc(p.key)}</span>
            </div>
            <div class="product-body">
              <h3 class="product-title" data-action="detail" data-pid="${p.id}">${esc(p.name)}</h3>
              <p class="product-desc">${esc(p.description)}</p>
              <div class="product-footer">
                <span class="product-price">${money(p.price)} so'm</span>
                ${controlHtml}
              </div>
            </div>
          </article>
        `;
      })
      .join("");
  }

  async function updateCartQty(pid, newQty) {
    const clamped = Math.max(0, Math.min(newQty, state.cart.max_qty || 50));
    try {
      const data = await api("/api/cart", {
        method: "POST",
        body: JSON.stringify({ product_id: pid, qty: clamped }),
      });
      state.cart = data.cart;
      haptic("light");
      renderCatalog();
      updateCartBadges();
      if (state.activeTab === "cart") renderCart();
      if (state.modalProductId === pid) syncProductModal();
    } catch (e) {
      showToast(e.message, true);
    }
  }

  function openProductModal(pid) {
    const p = state.products.find((item) => item.id === pid);
    if (!p) return;
    state.modalProductId = pid;
    const modal = document.getElementById("productModal");
    document.getElementById("modalProductImg").src = p.image_url || "";
    document.getElementById("modalProductImg").alt = p.name;
    const tag = document.getElementById("modalProductTag");
    tag.textContent = p.key.toUpperCase();
    tag.className = `variant-tag ${p.key}`;
    document.getElementById("modalProductName").textContent = p.name;
    document.getElementById("modalProductPrice").textContent = `${money(p.price)} so'm`;
    document.getElementById("modalProductDesc").textContent = p.description;
    syncProductModal();
    modal.classList.remove("hidden");
    haptic("select");
  }

  function syncProductModal() {
    if (!state.modalProductId) return;
    const qty = getCartQty(state.modalProductId);
    document.getElementById("modalQtyVal").textContent = String(qty);
    document.getElementById("modalDecBtn").disabled = qty === 0;
    const primary = document.getElementById("modalPrimaryBtn");
    primary.textContent = qty > 0 ? "Savatchaga o'tish" : "Savatchaga qo'shish";
  }

  function closeProductModal() {
    state.modalProductId = null;
    document.getElementById("productModal").classList.add("hidden");
  }

  function renderCart() {
    const successCard = document.getElementById("orderSuccessCard");
    const emptyCard = document.getElementById("cartEmpty");
    const filled = document.getElementById("cartFilled");
    const clearBtn = document.getElementById("btnClearCart");

    if (state.orderPlacedSuccess) {
      successCard.classList.remove("hidden");
      emptyCard.classList.add("hidden");
      filled.classList.add("hidden");
      clearBtn.classList.add("hidden");
      return;
    }

    successCard.classList.add("hidden");
    const hasItems = state.cart.items && state.cart.items.length > 0;

    if (!hasItems) {
      emptyCard.classList.remove("hidden");
      filled.classList.add("hidden");
      clearBtn.classList.add("hidden");
      return;
    }

    emptyCard.classList.add("hidden");
    filled.classList.remove("hidden");
    clearBtn.classList.remove("hidden");

    document.getElementById("cartTotalQty").textContent = `${state.cart.total_qty} ta`;
    document.getElementById("cartTotalSum").textContent = `${money(state.cart.total)} so'm`;

    const list = document.getElementById("cartItemsList");
    list.innerHTML = state.cart.items
      .map(
        (it) => `
        <div class="cart-item" data-pid="${it.product_id}">
          <div class="cart-item-info">
            <strong>${esc(it.name)}</strong>
            <span class="muted-label">${money(it.price)} so'm / dona</span>
          </div>
          <div class="qty-pill" data-pid="${it.product_id}">
            <button type="button" data-action="dec" data-pid="${it.product_id}">−</button>
            <span>${it.qty}</span>
            <button type="button" data-action="inc" data-pid="${it.product_id}">+</button>
          </div>
          <div class="cart-subtotal">${money(it.subtotal)} so'm</div>
        </div>
      `
      )
      .join("");

    const u = state.user;
    const regCard = document.getElementById("checkoutRegCard");
    const preview = document.getElementById("checkoutUserPreview");

    // Viloyat va Tuman tanlovini sinxronlash
    syncRegionDropdowns();

    if (!u || !u.is_registered) {
      regCard.classList.remove("hidden");
      preview.textContent = "Buyurtma berishdan avval aloqa ma'lumotlaringizni to'ldiring.";
    } else {
      regCard.classList.add("hidden");
      preview.textContent = `Buyurtmachi: ${esc(u.name)} (${esc(u.phone)})`;
    }
  }

  function syncRegionDropdowns() {
    const checkoutRegSel = document.getElementById("checkoutRegionSelect");
    const checkoutDistSel = document.getElementById("checkoutDistrictSelect");
    const profRegSel = document.getElementById("profRegionSelect");
    const profDistSel = document.getElementById("profDistrictSelect");

    function populateRegions(sel, currentVal) {
      if (!sel) return;
      const opts = ['<option value="">Viloyatni tanlang</option>'];
      state.regions.forEach((r) => {
        const isSel = Number(r.id) === Number(currentVal);
        opts.push(`<option value="${r.id}" ${isSel ? "selected" : ""}>${esc(r.name)}</option>`);
      });
      sel.innerHTML = opts.join("");
    }

    function populateDistricts(sel, regId, currentDistrict) {
      if (!sel) return;
      const region = state.regions.find((r) => Number(r.id) === Number(regId));
      if (!region || !region.districts || !region.districts.length) {
        sel.innerHTML = '<option value="">Tumanni tanlang</option>';
        return;
      }
      const opts = ['<option value="">Tumanni tanlang</option>'];
      region.districts.forEach((d) => {
        const isSel = d === currentDistrict;
        opts.push(`<option value="${esc(d)}" ${isSel ? "selected" : ""}>${esc(d)}</option>`);
      });
      sel.innerHTML = opts.join("");
    }

    const uReg = state.user ? state.user.region_id : null;
    const uDist = state.user ? state.user.district : null;

    populateRegions(checkoutRegSel, uReg);
    populateDistricts(checkoutDistSel, uReg, uDist);

    populateRegions(profRegSel, uReg);
    populateDistricts(profDistSel, uReg, uDist);
  }

  function updateCartBadges() {
    const count = state.cart.total_qty || 0;
    const badge = document.getElementById("navCartBadge");
    if (count > 0) {
      badge.textContent = String(count);
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
    updateFloatingCartBar();
  }

  function ensureMapInitialized() {
    const container = document.getElementById("deliveryMap");
    if (!container || state.map) return;
    try {
      if (!window.L) throw new Error("Leaflet kutubxonasi mavjud emas");
      state.map = L.map("deliveryMap", { zoomControl: true }).setView(
        [state.lat, state.lon],
        13
      );
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "© OpenStreetMap",
      }).addTo(state.map);

      state.marker = L.marker([state.lat, state.lon], { draggable: true }).addTo(
        state.map
      );
      state.marker.on("dragend", (e) => {
        const pos = e.target.getLatLng();
        setCoords(pos.lat, pos.lng);
      });

      state.map.on("click", (e) => {
        setCoords(e.latlng.lat, e.latlng.lng);
      });
    } catch (_) {
      document.getElementById("mapOfflineFallback").classList.remove("hidden");
    }
  }

  function setCoords(lat, lon) {
    state.lat = Number(lat);
    state.lon = Number(lon);
    document.getElementById("latInput").value = state.lat.toFixed(6);
    document.getElementById("lonInput").value = state.lon.toFixed(6);
    if (state.marker) state.marker.setLatLng([state.lat, state.lon]);
    if (state.map) state.map.panTo([state.lat, state.lon]);
  }

  async function placeOrder() {
    const btn = document.getElementById("btnPlaceOrder");
    btn.disabled = true;
    btn.textContent = "Buyurtma tekshirilmoqda...";

    const regSelect = document.getElementById("checkoutRegionSelect");
    const distSelect = document.getElementById("checkoutDistrictSelect");
    const regionId = regSelect ? Number(regSelect.value) : null;
    const district = distSelect ? distSelect.value : "";

    if (!regionId) {
      showToast("Iltimos, yetkazib berish viloyatini tanlang!", true);
      btn.disabled = false;
      btn.textContent = "✅ Buyurtmani tasdiqlash";
      return;
    }

    try {
      const data = await api("/api/orders", {
        method: "POST",
        body: JSON.stringify({
          lat: state.lat,
          lon: state.lon,
          expected_total: state.cart.total,
          region_id: regionId,
          district: district,
          payment_method: "cash",
        }),
      });

      state.orderPlacedSuccess = true;
      document.getElementById("successOrderId").textContent = `№${data.order.id}`;
      state.cart = data.cart;
      state.orders.unshift(data.order);
      updateCartBadges();
      renderCart();
      haptic("heavy");
      showToast(`Buyurtma №${data.order.id} qabul qilindi!`);
    } catch (e) {
      if (e.code === "price_changed") {
        await bootstrap();
      }
      showToast(e.message, true);
    } finally {
      btn.disabled = false;
      btn.textContent = "✅ Buyurtmani tasdiqlash";
    }
  }

  async function refreshOrders() {
    try {
      const data = await api("/api/orders");
      state.orders = data.orders;
      renderOrders();
    } catch (e) {
      showToast(e.message, true);
    }
  }

  function renderOrders() {
    const list = document.getElementById("ordersList");
    if (!state.orders || state.orders.length === 0) {
      list.innerHTML = `
        <div class="empty-card">
          <div class="empty-icon">📦</div>
          <h3>Buyurtmalar yo'q</h3>
          <p>Hozircha hech qanday buyurtma bermagansiz.</p>
        </div>
      `;
      return;
    }

    list.innerHTML = state.orders
      .map((o) => {
        const itemsHtml = o.items
          .map((i) => `<li>${esc(i.product_name)} × ${i.qty} — <b>${money(i.subtotal)} so'm</b></li>`)
          .join("");
        const regText = o.region_name ? `${esc(o.region_name)}${o.district ? ", " + esc(o.district) : ""}` : "";

        return `
          <div class="order-card">
            <div class="order-head">
              <strong>Buyurtma №${o.id}</strong>
              <span class="status-badge ${o.status}">${o.status_emoji} ${esc(o.status_label)}</span>
            </div>
            ${regText ? `<div class="muted-label small">📍 ${regText}</div>` : ""}
            <div class="order-date">${fmtDt(o.created_at)}</div>
            <ul class="order-items-list">${itemsHtml}</ul>
            <div class="order-foot">
              <span>Jami:</span>
              <strong class="gold-text">${money(o.total)} so'm</strong>
            </div>
          </div>
        `;
      })
      .join("");
  }

  function renderProfile() {
    const u = state.user;
    if (!u) return;
    const initial = (u.name || "E").trim().charAt(0).toUpperCase() || "E";
    document.getElementById("profileAvatar").textContent = initial;
    document.getElementById("profileDisplayName").textContent = u.name || "Foydalanuvchi";
    document.getElementById("profileDisplayPhone").textContent = u.phone || "Telefon kiritilmagan";
    document.getElementById("profileAgeBadge").textContent = u.age_ok ? "✅ 21+ tasdiqlangan" : "🔞 21+";
    document.getElementById("profileRegionBadge").textContent = u.region_name ? `📍 ${u.region_name}` : "Hudud: tanlanmagan";
    document.getElementById("profileIdBadge").textContent = `ID: ${u.tg_id}`;

    document.getElementById("profNameInput").value = u.name || "";
    document.getElementById("profPhoneInput").value = u.phone || "+998";
    syncRegionDropdowns();
  }

  // ==================== SUPERADMIN QISMI ====================
  async function loadSuperOverview() {
    try {
      const data = await api("/api/superadmin/overview");
      state.superData = data;
      renderSuperKpis(data.analytics);
      renderSuperRegionsTable(data.analytics.regions_report);
      renderSuperRanking(data.analytics.products_ranking);
    } catch (e) {
      showToast(e.message, true);
    }
  }

  function renderSuperKpis(a) {
    const grid = document.getElementById("superKpiGrid");
    grid.innerHTML = `
      <div class="kpi-card">
        <span class="kpi-title">Bugungi Savdo</span>
        <span class="kpi-val">${money(a.today.revenue)} so'm</span>
        <span class="kpi-sub">${a.today.count} ta buyurtma</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-title">Oylik Savdo</span>
        <span class="kpi-val">${money(a.month.revenue)} so'm</span>
        <span class="kpi-sub">${a.month.count} ta buyurtma</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-title">Yalpi Foyda (Sof)</span>
        <span class="kpi-val" style="color: #4ade80;">${money(a.gross_profit)} so'm</span>
        <span class="kpi-sub">Sotuv - Tannarx</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-title">Dilerlar Qarzdorligi</span>
        <span class="kpi-val" style="color: #f87171;">${money(a.total_dealer_debt)} so'm</span>
        <span class="kpi-sub">Zavodga to'lanmagan</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-title">Yuborilgan Tovar</span>
        <span class="kpi-val">${money(a.shipped_goods_value)} so'm</span>
        <span class="kpi-sub">Dilerlarga yetkazilgan</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-title">Jami Tushum</span>
        <span class="kpi-val">${money(a.payments_received)} so'm</span>
        <span class="kpi-sub">Dilerlardan kelgan</span>
      </div>
    `;
  }

  function renderSuperRegionsTable(report) {
    const tbody = document.getElementById("superRegionsTableBody");
    tbody.innerHTML = report
      .map(
        (r) => `
        <tr>
          <td><strong>${esc(r.region_name)}</strong></td>
          <td>
            <div>${esc(r.dealer_name)}</div>
            <div class="muted-label small">${esc(r.dealer_phone)}</div>
          </td>
          <td><b>${r.current_stock}</b> dona</td>
          <td>${r.orders_count} ta</td>
          <td><b>${money(r.sales_revenue)}</b> so'm</td>
          <td style="color: ${r.debt > 0 ? "#f87171" : "#4ade80"}; font-weight: 700;">
            ${money(r.debt)} so'm
          </td>
        </tr>
      `
      )
      .join("");
  }

  function renderSuperRanking(ranking) {
    const list = document.getElementById("superProductsRanking");
    list.innerHTML = ranking
      .map(
        (p, idx) => `
        <div class="ranking-item">
          <span><b>#${idx + 1}</b> ${esc(p.name)}</span>
          <span><strong>${p.sold_qty} dona</strong> (${money(p.revenue)} so'm)</span>
        </div>
      `
      )
      .join("");
  }

  async function loadSuperFactory() {
    try {
      const data = await api("/api/superadmin/factory/inventory");
      const list = document.getElementById("superFactoryInventoryList");
      list.innerHTML = data.inventory
        .map(
          (i) => `
          <div class="stock-item-card">
            <div class="shipment-head">
              <strong>${esc(i.name)}</strong>
              <span class="badge badge-info">Zavod Ombori</span>
            </div>
            <div class="shipment-meta">
              <span>Mavjud qoldiq: <b class="gold-text" style="font-size: 16px;">${i.factory_stock} ta</b></span>
              <span>Tannarx: <b>${money(i.cost_price)} so'm</b></span>
              <span>Dilerga narx: <b>${money(i.wholesale_price)} so'm</b></span>
              <span>Chakana narx: <b>${money(i.price)} so'm</b></span>
            </div>
          </div>
        `
        )
        .join("");
    } catch (e) {
      showToast(e.message, true);
    }
  }

  async function loadSuperShipments() {
    try {
      const data = await api("/api/superadmin/shipments");
      const list = document.getElementById("superShipmentsList");
      if (!data.shipments || !data.shipments.length) {
        list.innerHTML = '<div class="empty-card"><p>Jo\'natmalar tarixi yo\'q.</p></div>';
        return;
      }
      list.innerHTML = data.shipments
        .map(
          (s) => `
          <div class="shipment-card">
            <div class="shipment-head">
              <span class="shipment-track">${esc(s.tracking_no)}</span>
              <span class="badge ${s.status === "delivered" ? "badge-success" : s.status === "partial" ? "badge-danger" : "badge-warning"}">
                ${s.status === "delivered" ? "✅ Yetkazildi" : s.status === "partial" ? "⚠️ Tafovut bilan qabul" : "🚚 Yo'lda"}
              </span>
            </div>
            <div class="shipment-meta">
              <span>Viloyat: <b>${esc(s.region_name)}</b></span>
              <span>Diler: <b>${esc(s.dealer_name)}</b></span>
              <span>Qiymati: <b>${money(s.total_wholesale)} so'm</b></span>
              <span>Sana: ${fmtDt(s.created_at)}</span>
            </div>
            ${s.notes ? `<div class="shipment-items-box">${esc(s.notes)}</div>` : ""}
          </div>
        `
        )
        .join("");
    } catch (e) {
      showToast(e.message, true);
    }
  }

  async function loadSuperDealers() {
    try {
      const data = await api("/api/superadmin/dealers");
      const list = document.getElementById("superDealersList");
      list.innerHTML = data.dealers
        .map(
          (d) => `
          <div class="dealer-item-card">
            <div class="dealer-item-head">
              <strong>${esc(d.name)}</strong>
              <span class="badge ${d.status === "active" ? "badge-success" : "badge-danger"}">
                ${d.status === "active" ? "Faol" : "Bloklangan"}
              </span>
            </div>
            <div class="dealer-item-meta">
              <span>Viloyat: <b>${esc(d.region_name)}</b></span>
              <span>Telegram ID: <code>${d.tg_id}</code></span>
              <span>Telefon: ${esc(d.phone || "-")}</span>
              <span>Model: <b>${d.wholesale_model === "consignment" ? "Realizatsiya" : "Ulgurji"}</b></span>
            </div>
            <div class="form-actions" style="margin-top: 6px;">
              <button type="button" class="btn-secondary btn-sm" data-pay-dealer="${d.id}" data-dealer-name="${esc(d.name)}">💰 To'lov qayd qilish</button>
              <button type="button" class="icon-pill-btn" data-toggle-dealer="${d.id}" data-cur-status="${d.status}">
                ${d.status === "active" ? "Bloklash" : "Faollashtirish"}
              </button>
            </div>
          </div>
        `
        )
        .join("");
    } catch (e) {
      showToast(e.message, true);
    }
  }

  async function loadSuperProducts() {
    try {
      const data = await api("/api/superadmin/products");
      const list = document.getElementById("superProductsList");
      list.innerHTML = data.products
        .map(
          (p) => `
          <div class="panel-card">
            <div class="shipment-head">
              <strong>${esc(p.name)} (${esc(p.key)})</strong>
              <span class="badge ${p.active ? "badge-success" : "badge-danger"}">${p.active ? "Sotuvda" : "Yashirilgan"}</span>
            </div>
            <div class="form-stack" style="margin-top: 8px;">
              <div class="coords-row">
                <label class="field compact">
                  <span>Chakana narx (so'm)</span>
                  <input type="number" id="pPrice-${p.id}" value="${p.price}" />
                </label>
                <label class="field compact">
                  <span>Tannarx (so'm)</span>
                  <input type="number" id="pCost-${p.id}" value="${p.cost_price}" />
                </label>
                <label class="field compact">
                  <span>Diler narxi (so'm)</span>
                  <input type="number" id="pWholesale-${p.id}" value="${p.wholesale_price}" />
                </label>
              </div>
              <div class="form-actions">
                <button type="button" class="btn-primary btn-sm" data-save-prod="${p.id}">Saqlash</button>
              </div>
            </div>
          </div>
        `
        )
        .join("");
    } catch (e) {
      showToast(e.message, true);
    }
  }

  async function loadSuperOrders() {
    try {
      const regFilter = document.getElementById("superOrderRegionFilter") ? document.getElementById("superOrderRegionFilter").value : "";
      const stFilter = document.getElementById("superOrderStatusFilter") ? document.getElementById("superOrderStatusFilter").value : "";
      let url = "/api/superadmin/orders?limit=100";
      if (regFilter) url += `&region_id=${encodeURIComponent(regFilter)}`;
      if (stFilter && stFilter !== "all") url += `&status=${encodeURIComponent(stFilter)}`;
      const data = await api(url);
      const list = document.getElementById("superOrdersList");
      const orders = data.orders || [];
      if (!orders.length) {
        list.innerHTML = `<div class="empty-state">Buyurtmalar topilmadi.</div>`;
        return;
      }
      list.innerHTML = orders
        .map(
          (o) => `
          <div class="order-card">
            <div class="order-head">
              <strong>№${o.id} · ${esc(o.user_name)}</strong>
              <span class="status-badge ${o.status}">${o.status_emoji} ${esc(o.status_label)}</span>
            </div>
            <div class="muted-label small">📍 ${esc(o.region_name || "-")}, ${esc(o.district || "")} | Diler: ${esc(o.dealer_name || "Yo'q")}</div>
            <div class="order-date">${fmtDt(o.created_at)} | Tel: ${esc(o.phone)}</div>
            <div class="order-foot">
              <span>Jami:</span>
              <strong class="gold-text">${money(o.total)} so'm</strong>
            </div>
          </div>
        `
        )
        .join("");
    } catch (e) {
      showToast(e.message, true);
    }
  }

  async function loadSuperAudit() {
    try {
      const data = await api("/api/superadmin/audit");
      const list = document.getElementById("superAuditList");
      list.innerHTML = data.logs
        .map(
          (l) => `
          <div class="ranking-item" style="font-size: 12px;">
            <div>
              <strong>${esc(l.action)}</strong> (${esc(l.entity)} #${l.entity_id || ""})
              <div class="muted-label small">${esc(l.details_json)}</div>
            </div>
            <span class="muted-label">${fmtDt(l.created_at)}</span>
          </div>
        `
        )
        .join("");
    } catch (e) {
      showToast(e.message, true);
    }
  }

  // ==================== DILER QISMI ====================
  async function loadDealerOverview() {
    try {
      const data = await api("/api/dealer/overview");
      state.dealerData = data;
      const d = data.dealer;
      document.getElementById("dealerRegionTitle").textContent = `${d.region_name} Dileri`;
      document.getElementById("dealerSubLabel").textContent = `${d.name} (${d.phone || ""}) · Model: ${d.wholesale_model === "consignment" ? "Realizatsiya" : "Ulgurji"}`;

      const f = data.finance;
      const grid = document.getElementById("dealerKpiGrid");
      grid.innerHTML = `
        <div class="kpi-card">
          <span class="kpi-title">Bugungi Sotuv</span>
          <span class="kpi-val">${money(f.sales_today.revenue)} so'm</span>
          <span class="kpi-sub">${f.sales_today.orders_count} ta buyurtma</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-title">Oylik Sotuv</span>
          <span class="kpi-val">${money(f.sales_month.revenue)} so'm</span>
          <span class="kpi-sub">${f.sales_month.orders_count} ta buyurtma</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-title">Zavod Oldidagi Qarz</span>
          <span class="kpi-val" style="color: ${f.current_debt > 0 ? "#f87171" : "#4ade80"};">${money(f.current_debt)} so'm</span>
          <span class="kpi-sub">To'lanishi kutilmoqda</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-title">Olingan Tovarlar</span>
          <span class="kpi-val">${money(f.shipped_goods_value)} so'm</span>
          <span class="kpi-sub">Zavoddan yetkazilgan</span>
        </div>
      `;

      // Kutilayotgan jo'natmalar
      const incList = document.getElementById("dealerIncomingList");
      if (data.pending_shipments && data.pending_shipments.length) {
        document.getElementById("dealerPendingShipmentsCard").classList.remove("hidden");
        incList.innerHTML = data.pending_shipments
          .map(
            (s) => `
            <div class="shipment-card">
              <div class="shipment-head">
                <span class="shipment-track">${esc(s.tracking_no)}</span>
                <button type="button" class="btn-primary btn-sm" data-confirm-shp="${s.id}">📥 Qabul qilish va tekshirish</button>
              </div>
              <div class="shipment-meta">
                <span>Qiymati: <b>${money(s.total_wholesale)} so'm</b></span>
                <span>Yuborilgan sana: ${fmtDt(s.shipped_at)}</span>
              </div>
            </div>
          `
          )
          .join("");
      } else {
        document.getElementById("dealerPendingShipmentsCard").classList.add("hidden");
      }
    } catch (e) {
      showToast(e.message, true);
    }
  }

  async function loadDealerInventory() {
    try {
      const data = await api("/api/dealer/inventory");
      const grid = document.getElementById("dealerInventoryGrid");
      grid.innerHTML = data.inventory
        .map(
          (i) => `
          <div class="stock-item-card">
            <div class="shipment-head">
              <strong>${esc(i.name)}</strong>
              <span class="badge ${i.stock > 0 ? "badge-success" : "badge-danger"}">${i.stock > 0 ? "Mavjud" : "Tugagan"}</span>
            </div>
            <div class="shipment-meta">
              <span>Mavjud erkin qoldiq: <b class="gold-text" style="font-size: 16px;">${i.stock} ta</b></span>
              <span>Buyurtmada band: <b>${i.reserved} ta</b></span>
              <span>Jami sotilgan: <b>${i.sold} ta</b></span>
            </div>
          </div>
        `
        )
        .join("");
    } catch (e) {
      showToast(e.message, true);
    }
  }

  async function loadDealerShipments() {
    try {
      const data = await api("/api/dealer/shipments");
      const list = document.getElementById("dealerShipmentsHistory");
      list.innerHTML = data.shipments
        .map((s) => {
          const itemsHtml = (s.items || [])
            .map(
              (it) => `
              <div style="display: flex; justify-content: space-between; font-size: 12px; margin-top: 4px;">
                <span>${esc(it.product_name)}</span>
                <span>Yuborildi: <b>${it.sent_qty} ta</b> | Qabul: <b>${it.received_qty} ta</b> ${it.discrepancy_qty !== 0 ? `<b style="color:#f87171;">(Tafovut: ${it.discrepancy_qty})</b>` : ""}</span>
              </div>`
            )
            .join("");

          return `
            <div class="shipment-card">
              <div class="shipment-head">
                <span class="shipment-track">${esc(s.tracking_no)}</span>
                <span class="badge ${s.status === "delivered" ? "badge-success" : s.status === "partial" ? "badge-danger" : "badge-warning"}">
                  ${s.status === "delivered" ? "✅ To'liq qabul" : s.status === "partial" ? "⚠️ Tafovut bilan" : "🚚 Yo'lda"}
                </span>
              </div>
              <div class="shipment-items-box">${itemsHtml}</div>
              <div class="shipment-meta" style="margin-top: 6px;">
                <span>Qiymati: <b>${money(s.total_wholesale)} so'm</b></span>
                <span>Qabul vaqti: ${fmtDt(s.received_at || s.created_at)}</span>
              </div>
            </div>
          `;
        })
        .join("");
    } catch (e) {
      showToast(e.message, true);
    }
  }

  async function loadDealerOrders() {
    try {
      const data = await api("/api/dealer/orders");
      const list = document.getElementById("dealerOrdersList");
      if (!data.orders || !data.orders.length) {
        list.innerHTML = '<div class="empty-card"><p>Hududingizda yangi buyurtmalar yo\'q.</p></div>';
        return;
      }

      list.innerHTML = data.orders
        .map((o) => {
          const itemsHtml = o.items
            .map((i) => `<li>${esc(i.product_name)} × ${i.qty} — <b>${money(i.subtotal)} so'm</b></li>`)
            .join("");

          return `
            <div class="order-card">
              <div class="order-head">
                <strong>№${o.id} · ${esc(o.user_name)}</strong>
                <span class="status-badge ${o.status}">${o.status_emoji} ${esc(o.status_label)}</span>
              </div>
              <div class="muted-label small">📍 Tuman: <b>${esc(o.district || "-")}</b> | Tel: <b>${esc(o.phone)}</b></div>
              <div class="order-date">${fmtDt(o.created_at)}</div>
              <ul class="order-items-list">${itemsHtml}</ul>
              <div class="order-foot">
                <span>Jami to'lov:</span>
                <strong class="gold-text">${money(o.total)} so'm</strong>
              </div>
              ${!o.is_final ? `
                <div class="order-actions-grid" style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px;">
                  ${o.status === "new" ? `<button type="button" class="btn-primary btn-sm" data-dstatus="accepted" data-oid="${o.id}">✅ Qabul qilish</button>` : ""}
                  ${o.status === "accepted" ? `<button type="button" class="btn-secondary btn-sm" data-dstatus="preparing" data-oid="${o.id}">👨‍🍳 Tayyorlash</button>` : ""}
                  ${o.status === "preparing" ? `<button type="button" class="btn-primary btn-sm" data-dstatus="delivering" data-oid="${o.id}">🚚 Yetkazishga berish</button>` : ""}
                  ${o.status === "delivering" ? `<button type="button" class="btn-primary btn-sm" style="background:#28a86b;" data-dstatus="done" data-oid="${o.id}">🎉 Yakunlandi (Topshirildi)</button>` : ""}
                  <button type="button" class="ghost-danger-btn btn-sm" data-dstatus="cancelled" data-oid="${o.id}">❌ Bekor qilish</button>
                </div>
              ` : `
                <div style="display: flex; gap: 6px; margin-top: 8px;">
                  <span class="badge ${o.status === "done" ? "badge-success" : "badge-danger"}">${o.status_emoji} ${o.status_label}</span>
                  ${o.status === "done" ? `<button type="button" class="icon-pill-btn" data-dstatus="returned" data-oid="${o.id}">🔄 Qaytarish (Voz kechildi)</button>` : ""}
                </div>
              `}
            </div>
          `;
        })
        .join("");
    } catch (e) {
      showToast(e.message, true);
    }
  }

  async function loadDealerCustomers() {
    try {
      const data = await api("/api/dealer/customers");
      const list = document.getElementById("dealerCustomersList");
      list.innerHTML = data.customers
        .map(
          (c) => `
          <div class="ranking-item">
            <div>
              <strong>${esc(c.name)}</strong>
              <div class="muted-label small">${esc(c.district || "")} · ${esc(c.phone)}</div>
            </div>
            <span class="muted-label">${fmtDt(c.registered_at)}</span>
          </div>
        `
        )
        .join("");
    } catch (e) {
      showToast(e.message, true);
    }
  }

  async function loadDealerFinance() {
    try {
      const data = await api("/api/dealer/finance");
      const f = data.summary;
      const banner = document.getElementById("dealerFinanceBanner");
      banner.innerHTML = `
        <span class="kpi-title">Zavod Oldidagi Qarzdorlik:</span>
        <span class="finance-debt-num">${money(f.current_debt)} so'm</span>
        <div class="shipment-meta">
          <span>Kirim tovarlar: <b>${money(f.shipped_goods_value)} so'm</b></span>
          <span>To'langan summa: <b>${money(f.payments_to_factory)} so'm</b></span>
        </div>
      `;

      const list = document.getElementById("dealerLedgerList");
      list.innerHTML = data.ledger
        .map(
          (l) => `
          <div class="ranking-item">
            <div>
              <strong>${l.operation_type === "shipment_charge" ? "📥 Tovar kirimi (Qarz)" : "💸 To'lov qilindi"}</strong>
              <div class="muted-label small">${esc(l.note || "")}</div>
            </div>
            <span style="font-weight: 700; color: ${l.amount > 0 ? "#f87171" : "#4ade80"};">
              ${l.amount > 0 ? "+" : ""}${money(l.amount)} so'm
            </span>
          </div>
        `
        )
        .join("");
    } catch (e) {
      showToast(e.message, true);
    }
  }

  // ==================== BOOTSTRAP VA ISHGA TUSHIRISH ====================
  async function bootstrap() {
    try {
      const data = await api("/api/bootstrap");
      state.user = data.user;
      state.products = data.products;
      state.cart = data.cart;
      state.orders = data.orders;
      state.regions = data.regions || [];
      state.statuses = data.statuses;
      state.flow = data.flow;

      const superRegF = document.getElementById("superOrderRegionFilter");
      if (superRegF && state.regions.length) {
        superRegF.innerHTML = '<option value="">Barcha viloyatlar</option>' + 
          state.regions.map(r => `<option value="${r.id}">${esc(r.name)}</option>`).join("");
      }
      const superStF = document.getElementById("superOrderStatusFilter");
      if (superStF && state.statuses) {
        superStF.innerHTML = '<option value="">Barcha holatlar</option>' + 
          Object.keys(state.statuses).map(k => `<option value="${k}">${esc(state.statuses[k])}</option>`).join("");
      }

      renderCatalog();
      updateCartBadges();
      renderOrders();
      renderProfile();
      renderHeader();

      if (state.user.is_superadmin) {
        showSuperTab(state.activeSuperTab || "catalog");
      } else if (state.user.is_dealer) {
        showDealerTab(state.activeDealerTab || "overview");
      } else {
        syncAgeGate();
        showCustomerTab(state.activeTab || "catalog");
      }
    } catch (e) {
      if (e.status === 401) {
        document.getElementById("blockedMessage").textContent = e.message;
        hideAllViews();
        document.getElementById("viewBlocked").classList.add("active");
      } else {
        showToast(e.message, true);
      }
    }
  }

  function syncAgeGate() {
    const gate = document.getElementById("ageGateModal");
    if (!state.user || state.user.is_admin || state.user.age_ok) {
      gate.classList.add("hidden");
      return;
    }
    document.getElementById("ageGateActions").classList.remove("hidden");
    document.getElementById("ageBlockedNotice").classList.add("hidden");
    gate.classList.remove("hidden");
  }

  // ==================== HODISALAR (EVENT LISTENERS) ====================
  function bindEvents() {
    // Mode toggle (SuperAdmin <-> Do'kon)
    const toggleBtn = document.getElementById("btnToggleAdminMode");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => {
        if (!state.user || !state.user.is_superadmin) return;
        if (state.activeSuperTab === "catalog") {
          showSuperTab("overview");
        } else {
          showSuperTab("catalog");
        }
      });
    }

    // Mijoz pastki menyusi
    document.getElementById("customerNav").addEventListener("click", (e) => {
      const btn = e.target.closest(".nav-item");
      if (btn && btn.dataset.tab) showCustomerTab(btn.dataset.tab);
    });

    // SuperAdmin pastki menyusi
    document.getElementById("superadminNav").addEventListener("click", (e) => {
      const btn = e.target.closest(".nav-item");
      if (btn && btn.dataset.superTab) showSuperTab(btn.dataset.superTab);
    });

    // Diler pastki menyusi
    document.getElementById("dealerNav").addEventListener("click", (e) => {
      const btn = e.target.closest(".nav-item");
      if (btn && btn.dataset.dealerTab) showDealerTab(btn.dataset.dealerTab);
    });

    // Floating cart tugmasi
    document.getElementById("btnGoCartFromFloat").addEventListener("click", () => showCustomerTab("cart"));

    // Katalog amallari (Mijoz)
    document.getElementById("catalogGrid").addEventListener("click", (e) => {
      const target = e.target.closest("[data-action]");
      if (!target) return;
      const pid = Number(target.dataset.pid);
      const act = target.dataset.action;
      if (act === "detail") {
        openProductModal(pid);
      } else if (act === "inc") {
        updateCartQty(pid, getCartQty(pid) + 1);
      } else if (act === "dec") {
        updateCartQty(pid, getCartQty(pid) - 1);
      }
    });

    // Savatcha ichidagi + / - amallari
    document.getElementById("cartItemsList").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-action]");
      if (!btn) return;
      const pid = Number(btn.dataset.pid);
      if (btn.dataset.action === "inc") updateCartQty(pid, getCartQty(pid) + 1);
      if (btn.dataset.action === "dec") updateCartQty(pid, getCartQty(pid) - 1);
    });

    // Savatchani tozalash
    document.getElementById("btnClearCart").addEventListener("click", async () => {
      await api("/api/cart", { method: "DELETE" });
      state.cart = { items: [], total: 0, total_qty: 0, max_qty: 50 };
      renderCatalog();
      updateCartBadges();
      renderCart();
    });

    // GPS joylashuvni aniqlash
    document.getElementById("btnDetectLocation").addEventListener("click", () => {
      if (!navigator.geolocation) {
        showToast("Qurilmangizda geolokatsiya qo'llab-quvvatlanmaydi", true);
        return;
      }
      showToast("Joylashuv aniqlanmoqda...");
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setCoords(pos.coords.latitude, pos.coords.longitude);
          showToast("Joylashuvingiz aniqlandi ✅");
        },
        () => showToast("Joylashuvni aniqlab bo'lmadi. Xaritadan nuqtani tanlang.", true),
        { enableHighAccuracy: true, timeout: 8000 }
      );
    });

    // Koordinata kiritilganda xaritani surish
    document.getElementById("latInput").addEventListener("change", (e) => setCoords(e.target.value, state.lon));
    document.getElementById("lonInput").addEventListener("change", (e) => setCoords(state.lat, e.target.value));

    // Buyurtma berish
    document.getElementById("btnPlaceOrder").addEventListener("click", placeOrder);

    // Viloyat tanlanganda tumanlarni yangilash
    document.getElementById("checkoutRegionSelect").addEventListener("change", (e) => {
      const regId = e.target.value;
      const region = state.regions.find((r) => Number(r.id) === Number(regId));
      const distSel = document.getElementById("checkoutDistrictSelect");
      if (!region || !region.districts) {
        distSel.innerHTML = '<option value="">Tumanni tanlang</option>';
        return;
      }
      distSel.innerHTML = ['<option value="">Tumanni tanlang</option>']
        .concat(region.districts.map((d) => `<option value="${esc(d)}">${esc(d)}</option>`))
        .join("");
    });

    document.getElementById("profRegionSelect").addEventListener("change", (e) => {
      const regId = e.target.value;
      const region = state.regions.find((r) => Number(r.id) === Number(regId));
      const distSel = document.getElementById("profDistrictSelect");
      if (!region || !region.districts) {
        distSel.innerHTML = '<option value="">Tumanni tanlang</option>';
        return;
      }
      distSel.innerHTML = ['<option value="">Tumanni tanlang</option>']
        .concat(region.districts.map((d) => `<option value="${esc(d)}">${esc(d)}</option>`))
        .join("");
    });

    // Profilni saqlash
    document.getElementById("btnSaveProfile").addEventListener("click", async () => {
      const name = document.getElementById("profNameInput").value.trim();
      const phone = document.getElementById("profPhoneInput").value.trim();
      const region_id = Number(document.getElementById("profRegionSelect").value) || null;
      const district = document.getElementById("profDistrictSelect").value || "";

      try {
        const data = await api("/api/register", {
          method: "POST",
          body: JSON.stringify({ name, phone, region_id, district }),
        });
        state.user = data.user;
        renderHeader();
        renderProfile();
        showToast("Ma'lumotlar saqlandi ✅");
      } catch (err) {
        showToast(err.message, true);
      }
    });

    // SuperAdmin buyurtma filtrlari
    const superRegF = document.getElementById("superOrderRegionFilter");
    if (superRegF) superRegF.addEventListener("change", loadSuperOrders);
    const superStF = document.getElementById("superOrderStatusFilter");
    if (superStF) superStF.addEventListener("change", loadSuperOrders);

    // Modallarni yopish tugmalari
    document.querySelectorAll("[data-close-modal]").forEach((b) => {
      b.addEventListener("click", () => closeModal(b.dataset.closeModal));
    });

    // 21+ Yosh tasdiqlash
    document.getElementById("btnAgeYes").addEventListener("click", async () => {
      try {
        const data = await api("/api/age-confirm", { method: "POST" });
        state.user = data.user;
        document.getElementById("ageGateModal").classList.add("hidden");
        showToast("Yoshingiz tasdiqlandi ✅");
      } catch (e) {
        showToast(e.message, true);
      }
    });

    document.getElementById("btnAgeNo").addEventListener("click", () => {
      document.getElementById("ageGateActions").classList.add("hidden");
      document.getElementById("ageBlockedNotice").classList.remove("hidden");
    });

    // CSV Eksport
    document.getElementById("btnExportCsv").addEventListener("click", () => {
      window.location.href = "/api/superadmin/export";
    });

    // SuperAdmin: Yangi Jo'natma Modali ochish
    document.getElementById("btnOpenNewShipment").addEventListener("click", () => {
      const sel = document.getElementById("shipmentDealerSelect");
      const dealers = state.superData ? state.superData.dealers : [];
      sel.innerHTML = dealers
        .filter((d) => d.status === "active")
        .map((d) => `<option value="${d.id}">${esc(d.region_name)} — ${esc(d.name)}</option>`)
        .join("");

      const builder = document.getElementById("shipmentItemsBuilder");
      builder.innerHTML = state.products
        .map(
          (p) => `
          <div class="build-item-row">
            <div>
              <strong>${esc(p.name)}</strong>
              <div class="muted-label small">Ulgurji narx: ${money(p.wholesale_price)} so'm</div>
            </div>
            <input type="number" min="0" value="0" placeholder="Soni" data-ship-pid="${p.id}" data-wholesale="${p.wholesale_price}" class="ship-qty-input" />
          </div>
        `
        )
        .join("");
      openModal("newShipmentModal");
    });

    // SuperAdmin: Jo'natmani yuborish
    document.getElementById("btnSubmitShipment").addEventListener("click", async () => {
      const dealer_id = Number(document.getElementById("shipmentDealerSelect").value);
      const notes = document.getElementById("shipmentNotesInput").value.trim();
      const items = [];
      document.querySelectorAll(".ship-qty-input").forEach((inp) => {
        const qty = Number(inp.value);
        if (qty > 0) {
          items.push({
            product_id: Number(inp.dataset.shipPid),
            sent_qty: qty,
            unit_price: Number(inp.dataset.wholesale),
          });
        }
      });

      if (!items.length) {
        showToast("Kamida bitta mahsulot miqdorini kiriting!", true);
        return;
      }

      try {
        await api("/api/superadmin/shipments", {
          method: "POST",
          body: JSON.stringify({ dealer_id, items, notes }),
        });
        closeModal("newShipmentModal");
        showToast("Jo'natma dilerga jo'natildi ✅");
        loadSuperShipments();
        loadSuperFactory();
      } catch (e) {
        showToast(e.message, true);
      }
    });

    // SuperAdmin: Diler biriktirish
    document.getElementById("btnOpenAddDealer").addEventListener("click", () => {
      const sel = document.getElementById("dealerRegionSelect");
      sel.innerHTML = state.regions.map((r) => `<option value="${r.id}">${esc(r.name)}</option>`).join("");
      document.getElementById("dealerNameInput").value = "";
      document.getElementById("dealerTgIdInput").value = "";
      document.getElementById("dealerPhoneInput").value = "+998";
      openModal("dealerModal");
    });

    document.getElementById("btnSaveDealer").addEventListener("click", async () => {
      const region_id = Number(document.getElementById("dealerRegionSelect").value);
      const name = document.getElementById("dealerNameInput").value.trim();
      const tg_id = Number(document.getElementById("dealerTgIdInput").value);
      const phone = document.getElementById("dealerPhoneInput").value.trim();
      const wholesale_model = document.getElementById("dealerModelSelect").value;
      const status = document.getElementById("dealerStatusSelect").value;

      try {
        await api("/api/superadmin/dealers", {
          method: "POST",
          body: JSON.stringify({ region_id, name, tg_id, phone, wholesale_model, status }),
        });
        closeModal("dealerModal");
        showToast("Diler muvaffaqiyatli saqlandi ✅");
        loadSuperDealers();
      } catch (e) {
        showToast(e.message, true);
      }
    });

    // SuperAdmin: Dilerga to'lov qayd qilish
    document.addEventListener("click", (e) => {
      const payBtn = e.target.closest("[data-pay-dealer]");
      if (payBtn) {
        const did = Number(payBtn.dataset.payDealer);
        const name = payBtn.dataset.dealerName;
        document.getElementById("paymentDealerNameBadge").textContent = `Diler: ${name}`;
        document.getElementById("dealerPaymentModal").dataset.targetDid = did;
        document.getElementById("paymentAmountInput").value = "";
        openModal("dealerPaymentModal");
      }
    });

    document.getElementById("btnSaveDealerPayment").addEventListener("click", async () => {
      const did = Number(document.getElementById("dealerPaymentModal").dataset.targetDid);
      const amount = Number(document.getElementById("paymentAmountInput").value);
      const payment_method = document.getElementById("paymentMethodSelect").value;
      const note = document.getElementById("paymentNoteInput").value.trim();

      try {
        await api(`/api/superadmin/dealers/${did}/payments`, {
          method: "POST",
          body: JSON.stringify({ amount, payment_method, note }),
        });
        closeModal("dealerPaymentModal");
        showToast("To'lov muvaffaqiyatli qabul qilindi ✅");
        loadSuperOverview();
        loadSuperDealers();
      } catch (e) {
        showToast(e.message, true);
      }
    });

    // SuperAdmin: Zavod qoldig'ini to'ldirish
    document.getElementById("btnOpenAdjustFactory").addEventListener("click", () => {
      const sel = document.getElementById("factoryStockProductSelect");
      sel.innerHTML = state.products.map((p) => `<option value="${p.id}">${esc(p.name)}</option>`).join("");
      document.getElementById("factoryStockQtyInput").value = "";
      document.getElementById("factoryStockReasonInput").value = "Ishlab chiqarishdan kirim";
      openModal("factoryStockModal");
    });

    document.getElementById("btnSaveFactoryStock").addEventListener("click", async () => {
      const product_id = Number(document.getElementById("factoryStockProductSelect").value);
      const change_qty = Number(document.getElementById("factoryStockQtyInput").value);
      const reason = document.getElementById("factoryStockReasonInput").value.trim();

      try {
        await api("/api/superadmin/factory/inventory/adjust", {
          method: "POST",
          body: JSON.stringify({ product_id, change_qty, reason }),
        });
        closeModal("factoryStockModal");
        showToast("Zavod qoldig'i yangilandi ✅");
        loadSuperFactory();
      } catch (e) {
        showToast(e.message, true);
      }
    });

    // Diler: Jo'natmani Qabul Qilish Modali
    document.addEventListener("click", async (e) => {
      const confBtn = e.target.closest("[data-confirm-shp]");
      if (confBtn) {
        const shpId = Number(confBtn.dataset.confirmShp);
        state.currentShipmentConfirmId = shpId;
        document.getElementById("dealerConfirmShipmentNumber").textContent = `Jo'natma №${shpId}`;
        const list = document.getElementById("dealerReceivedItemsList");
        list.innerHTML = "Yuklanmoqda...";
        openModal("dealerConfirmModal");

        try {
          const data = await api("/api/dealer/shipments");
          const shp = (data.shipments || []).find((s) => s.id === shpId);
          if (shp && shp.items) {
            list.innerHTML = shp.items
              .map(
                (it) => `
                <div class="check-item-row">
                  <div>
                    <strong>${esc(it.product_name)}</strong>
                    <div class="muted-label small">Yuborilgan: ${it.sent_qty} ta</div>
                  </div>
                  <input type="number" min="0" value="${it.sent_qty}" data-rec-pid="${it.product_id}" class="dealer-rec-input" />
                </div>
              `
              )
              .join("");
          }
        } catch (err) {
          showToast(err.message, true);
        }
      }
    });

    // Diler: Qabulni tasdiqlash
    document.getElementById("btnSubmitDealerConfirm").addEventListener("click", async () => {
      const shpId = state.currentShipmentConfirmId;
      const notes = document.getElementById("dealerConfirmNotesInput").value.trim();
      const received_items = {};
      document.querySelectorAll(".dealer-rec-input").forEach((inp) => {
        received_items[inp.dataset.recPid] = Number(inp.value);
      });

      try {
        const res = await api(`/api/dealer/shipments/${shpId}/confirm`, {
          method: "POST",
          body: JSON.stringify({ received_items, notes }),
        });
        closeModal("dealerConfirmModal");
        if (res.status === "partial") {
          showToast("⚠️ Tovarlar tafovut bilan qabul qilindi (SuperAdminga bildirildi)", true);
        } else {
          showToast("✅ Barcha tovarlar to'liq qabul qilindi va omborga kirdi!");
        }
        loadDealerOverview();
        loadDealerInventory();
        loadDealerShipments();
      } catch (err) {
        showToast(err.message, true);
      }
    });

    // Diler: Buyurtma holatini o'zgartirish
    document.getElementById("dealerOrdersList").addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-dstatus]");
      if (!btn) return;
      const oid = Number(btn.dataset.oid);
      const status = btn.dataset.dstatus;
      btn.disabled = true;

      try {
        await api(`/api/dealer/orders/${oid}/status`, {
          method: "POST",
          body: JSON.stringify({ status }),
        });
        haptic("medium");
        showToast(`Buyurtma №${oid} holati yangilandi`);
        await loadDealerOrders();
        await loadDealerOverview();
      } catch (err) {
        showToast(err.message, true);
        btn.disabled = false;
      }
    });

    // Yangilash tugmalari
    document.getElementById("btnRefreshSuper").addEventListener("click", loadSuperOverview);
    document.getElementById("btnRefreshDealer").addEventListener("click", loadDealerOverview);
    document.getElementById("btnRefreshDealerInventory" || "btnRefreshDealer").addEventListener("click", loadDealerInventory);
    document.getElementById("btnRefreshDealerOrders").addEventListener("click", loadDealerOrders);
    document.getElementById("btnRefreshOrders").addEventListener("click", refreshOrders);
  }

  function initTelegramTheme() {
    if (!tg) return;
    try {
      tg.ready();
      tg.expand();
      if (typeof tg.disableVerticalSwipes === "function") tg.disableVerticalSwipes();
      if (typeof tg.enableClosingConfirmation === "function") tg.enableClosingConfirmation();
      if (typeof tg.setHeaderColor === "function") tg.setHeaderColor("#0b0e0c");
      if (typeof tg.setBackgroundColor === "function") tg.setBackgroundColor("#0b0e0c");
    } catch (_) {}
  }

  document.addEventListener("DOMContentLoaded", () => {
    initTelegramTheme();
    bindEvents();
    bootstrap();
  });
})();
