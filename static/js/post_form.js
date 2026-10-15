// Links added by the draw operation also use the same confirmation.
document.addEventListener("click", (event) => {
  const link = event.target.closest("a.source");
  if (link && !window.confirm("外部の解説ページを別のタブで開きますか？")) event.preventDefault();
});
const form = document.getElementById("post-form");
if (form) {
  let dirty = false, busy = false, previewURL = null, suggestion = "", offered = [];
  const error = document.getElementById("form-error");
  const draw = document.getElementById("draw");
  const caption = form.elements.caption;
  const token = document.getElementById("draw-token");
  const reset = document.getElementById("reset-caption");
  const preview = document.getElementById("photo-preview");
  let savedPreview = preview.getAttribute("src") || "";
  const status = document.getElementById("save-status");
  function setSaveStatus(message = "", state = "") {
    status.textContent = message;
    status.dataset.state = state;
    status.hidden = !message;
  }
  for (const radio of form.querySelectorAll('input[name="word_id"]')) {
    if (radio.checked) suggestion = radio.dataset.suggestion;
    radio.addEventListener("change", () => {
      if (!caption.value || caption.value === suggestion || window.confirm("新しい文章案に置き換えますか？")) caption.value = radio.dataset.suggestion;
      suggestion = radio.dataset.suggestion; reset.disabled = false; dirty = true; setSaveStatus("変更はまだ保存されていません。", "unsaved");
    });
  }
  reset.disabled = !form.querySelector('input[name="word_id"]:checked');
  function lock(value) {
    busy = value;
    form.querySelectorAll("button, input, select, textarea").forEach(button => button.disabled = value);
    reset.disabled = value || !form.querySelector('input[name="word_id"]:checked');
  }
  async function send(url, data) {
    const response = await fetch(url, {method: "POST", body: data, headers: {"X-Requested-With": "XMLHttpRequest"}});
    let body;
    try { body = await response.json(); } catch { throw new Error("通信に失敗しました。入力を残したまま再試行してください。"); }
    if (!response.ok) {
      const details = body.fields ? Object.values(body.fields).flat().join(" ") : "";
      throw new Error([body.error || "操作できませんでした。", details].join(" "));
    }
    return body;
  }
  form.addEventListener("input", () => { dirty = true; setSaveStatus("変更はまだ保存されていません。", "unsaved"); });
  form.elements.photo.addEventListener("change", () => {
    if (previewURL) URL.revokeObjectURL(previewURL);
    const file = form.elements.photo.files[0];
    preview.hidden = !file && !savedPreview;
    if (!file && savedPreview) preview.src = savedPreview;
    if (file) { previewURL = URL.createObjectURL(file); preview.src = previewURL; }
  });
  form.elements.location.addEventListener("change", () => {
    const other = form.elements.location.value === "other";
    document.getElementById("other-location").hidden = !other;
    if (!other) form.elements.location_other.value = "";
  });
  draw.addEventListener("click", async () => {
    if (busy) return;
    lock(true); error.textContent = "";
    const data = new FormData();
    data.set("csrf_token", form.elements.csrf_token.value);
    if (token.value) data.set("previous", token.value);
    try {
      const result = await send(draw.dataset.url, data);
      token.value = result.token; offered = result.words; suggestion = ""; dirty = true; setSaveStatus("変更はまだ保存されていません。", "unsaved");
      const container = document.getElementById("word-options");
      container.replaceChildren();
      for (const word of offered) {
        const card = document.createElement("article");
        const label = document.createElement("label"), radio = document.createElement("input");
        radio.type = "radio"; radio.name = "word_id"; radio.value = word.id;
        label.append(radio, document.createTextNode(" " + word.phrase)); card.append(label);
        for (const text of [word.reading, word.explanation]) {
          const p = document.createElement("p"); p.textContent = text; card.append(p);
        }
        const a = document.createElement("a");
        a.textContent = word.source_label; a.href = word.reference_url;
        a.className = "source"; a.target = "_blank"; a.rel = "noopener noreferrer"; card.append(a);
        radio.addEventListener("change", () => {
          if (!caption.value || caption.value === suggestion || window.confirm("新しい文章案に置き換えますか？ キャンセルすると入力した文章を残します。")) caption.value = word.suggested_caption;
          suggestion = word.suggested_caption; reset.disabled = false; dirty = true; setSaveStatus("変更はまだ保存されていません。", "unsaved");
        });
        container.append(card);
      }
      draw.textContent = "もう一度引く";
    } catch (e) { error.textContent = e.message; }
    finally { lock(false); }
  });
  document.getElementById("save-draft").addEventListener("click", async event => {
    if (busy) return;
    const url = event.currentTarget.dataset.url;
    const data = new FormData(form);
    lock(true); error.textContent = ""; setSaveStatus("保存しています…", "saving");
    try {
      const result = await send(url, data);
      form.elements.draft_id.value = result.id;
      form.elements.version.value = result.version;
      document.getElementById("delete-draft-area").hidden = false;
      if (result.image_url) {
        savedPreview = result.image_url + "?v=" + result.version;
        preview.src = savedPreview; preview.hidden = false;
        form.elements.photo.value = "";
        if (previewURL) { URL.revokeObjectURL(previewURL); previewURL = null; }
      }
      dirty = false; setSaveStatus("✓ 下書きを保存しました。あとから続きを編集できます。", "saved");
    } catch (e) { setSaveStatus(); error.textContent = e.message; }
    finally { lock(false); }
  });
  document.getElementById("delete-draft").addEventListener("click", async event => {
    if (busy || !form.elements.draft_id.value) return;
    if (!window.confirm("下書きと保存した写真を削除しますか？ 未保存の変更も失われます。元に戻せません。")) return;
    const url = event.currentTarget.dataset.url;
    const data = new FormData();
    for (const name of ["csrf_token", "draft_id", "version", "submission_key"]) data.set(name, form.elements[name].value);
    lock(true); error.textContent = ""; setSaveStatus();
    try {
      const result = await send(url, data);
      dirty = false; window.location.assign(result.redirect);
    } catch (e) { error.textContent = e.message; lock(false); }
  });
  reset.addEventListener("click", () => {
    if (window.confirm("文章案に戻しますか？")) { caption.value = suggestion; dirty = true; setSaveStatus("変更はまだ保存されていません。", "unsaved"); }
  });
  form.addEventListener("submit", async event => {
    event.preventDefault(); if (busy) return;
    const data = new FormData(form); lock(true); error.textContent = "";
    try { const result = await send(form.action, data); dirty = false; window.location.assign(result.redirect); }
    catch (e) { error.textContent = e.message; lock(false); }
  });
  window.addEventListener("beforeunload", event => {
    if (dirty) { event.preventDefault(); event.returnValue = ""; }
  });
  document.addEventListener("click", event => {
    const link = event.target.closest("a");
    if (dirty && link && link.target !== "_blank") {
      if (!window.confirm("保存していない変更があります。移動しますか？")) event.preventDefault();
      else dirty = false;
    }
  });
}

for (const deleteForm of document.querySelectorAll(".delete-post-form")) {
  const button = deleteForm.querySelector("button");
  button.disabled = false;
  deleteForm.addEventListener("submit", event => {
    if (!window.confirm("この投稿と写真を削除しますか？ 元に戻せません。")) {
      event.preventDefault();
      return;
    }
    button.disabled = true;
  });
}
window.addEventListener("pageshow", () => {
  document.querySelectorAll(".delete-post-form button").forEach(button => button.disabled = false);
});
