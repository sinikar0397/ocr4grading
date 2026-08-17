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

function setStatus(el, mode, text) {
  el.textContent = text;
  el.classList.remove("ok", "err", "pending");
  el.classList.add("is-visible", mode);
}

function showStatus(el, result, successLabel) {
  if (result.ok) {
    setStatus(el, "ok", successLabel ?? "완료");
  } else {
    setStatus(el, "err", `실패: ${result.message}`);
  }
}

// OCR처럼 실제 진행률을 알 수 없는 서버 작업 동안 보여줄 애니메이션 로딩바 + 경과 시간.
// 반환된 함수를 호출하면 멈추고 지운다.
function startLoadingBar(el, note) {
  el.innerHTML = `<div class="track"><div class="fill"></div></div><div class="elapsed"></div>`;
  const elapsedEl = el.querySelector(".elapsed");
  const start = Date.now();
  const tick = () => {
    const secs = Math.floor((Date.now() - start) / 1000);
    elapsedEl.textContent = `${secs}초 경과${note ? " — " + note : ""}`;
  };
  tick();
  const timer = setInterval(tick, 1000);
  return () => {
    clearInterval(timer);
    el.innerHTML = "";
  };
}

// 커스텀 스타일이 입혀진 .file-input 안의 <input type="file">은 선택 시 이름을 옆 span에 반영한다.
document.addEventListener("change", (e) => {
  if (e.target.matches(".file-input input[type='file']")) {
    const nameEl = e.target.closest(".file-input").querySelector(".file-input-name");
    const files = e.target.files;
    nameEl.textContent =
      files.length === 0 ? "선택된 파일 없음" :
      files.length === 1 ? files[0].name :
      `${files[0].name} 외 ${files.length - 1}장`;
  }
});
