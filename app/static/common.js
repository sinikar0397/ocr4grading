// Shared fetch + 성공/실패 표시 헬퍼. 페이지마다 같은 걸 다시 짜지 않으려고 분리.

async function callApi(url, options) {
  try {
    const res = await fetch(url, options);
    let body = null;
    try {
      body = await res.json();
    } catch {
      // 본문이 JSON이 아님 (빈 응답, 500 stacktrace 등) - null로 둔다
    }
    if (!res.ok) {
      const message = (body && (body.detail || body.message)) || `HTTP ${res.status}`;
      return { ok: false, status: res.status, message, body };
    }
    return { ok: true, status: res.status, body };
  } catch (err) {
    return { ok: false, status: 0, message: `네트워크 오류: ${err.message}` };
  }
}

function showStatus(el, result, successLabel) {
  if (result.ok) {
    el.textContent = `[성공] ${successLabel ?? ""}\n${JSON.stringify(result.body, null, 2)}`;
    el.style.color = "#0a7a2f";
    el.style.background = "#eafbf0";
  } else {
    el.textContent = `[실패] HTTP ${result.status} - ${result.message}`;
    el.style.color = "#a30000";
    el.style.background = "#fdeaea";
  }
  el.style.padding = "8px";
  el.style.whiteSpace = "pre-wrap";
}
