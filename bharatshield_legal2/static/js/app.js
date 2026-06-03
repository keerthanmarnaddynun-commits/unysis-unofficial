/** BharatShield Legal — shared frontend helpers */

function showAlert(el, message, type) {
  if (!el) return;
  el.textContent = message;
  el.className = "alert show alert-" + (type || "error");
}

function setLoading(btn, loading) {
  if (!btn) return;
  btn.disabled = loading;
  const label = btn.dataset.label || btn.textContent;
  if (loading) {
    btn.dataset.label = label;
    btn.innerHTML = '<span class="spinner"></span> Processing…';
  } else {
    btn.textContent = btn.dataset.label || label;
  }
}

async function apiDemoGenerate(politicianName, role) {
  const params = new URLSearchParams({
    politician_name: politicianName,
    role: role,
  });
  const res = await fetch("/api/v1/demo/generate?" + params.toString(), {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail;
    const msg = Array.isArray(detail)
      ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
      : detail || res.statusText || "Request failed";
    throw new Error(msg);
  }
  return res.json();
}

async function apiFullGenerate(body) {
  const res = await fetch("/api/v1/generate-legal-packet", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail;
    const msg = Array.isArray(detail)
      ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
      : detail || res.statusText || "Request failed";
    throw new Error(msg);
  }
  return res.json();
}

async function apiAdminFetch(path, adminKey, options) {
  const headers = Object.assign(
    { "X-Admin-Key": adminKey },
    (options && options.headers) || {}
  );
  const res = await fetch(path, Object.assign({}, options, { headers }));
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText || "Request failed");
  }
  return res;
}
