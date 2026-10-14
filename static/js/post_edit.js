const editForm = document.getElementById("edit-post-form");
if (editForm) {
  let dirty = false, busy = false, previewURL = null;
  const preview = document.getElementById("edit-preview");
  const savedPreview = preview.src;
  const error = document.getElementById("edit-error");
  const draw = document.getElementById("edit-draw");
  const options = document.getElementById("edit-word-options");
  const useCaption = document.getElementById("edit-use-caption");
  let suggestion = null;
  function lock(value) {
    busy = value;
    editForm.querySelectorAll("button,input,select,textarea").forEach(el => el.disabled = value);
    useCaption.disabled = value || suggestion === null;
  }
  editForm.addEventListener("change", event => {
    if (event.target.name === "edit_word_id") {
      suggestion = event.target.value ? event.target.dataset.suggestion : null;
      useCaption.disabled = suggestion === null;
      dirty = true;
    }
  });
  useCaption.addEventListener("click", () => {
    if (suggestion !== null && window.confirm("ひとことを選んだことばの文章案に置き換えますか？")) {
      editForm.elements.caption.value = suggestion;
      dirty = true;
    }
  });
  draw.addEventListener("click", async () => {
    if (busy) return;
    const data = new FormData();
    data.set("csrf_token", editForm.elements.csrf_token.value);
    if (editForm.elements.edit_draw_token.value) data.set("previous", editForm.elements.edit_draw_token.value);
    lock(true); error.textContent = "";
    try {
      const response = await fetch(draw.dataset.url, {method: "POST", body: data, headers: {"X-Requested-With": "XMLHttpRequest"}});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "ことばを引けませんでした。");
      editForm.elements.edit_draw_token.value = result.token;
      options.replaceChildren();
      editForm.querySelector('input[name="edit_word_id"][value=""]').checked = true;
      suggestion = null;
      for (const word of result.words) {
        const card = document.createElement("article");
        const label = document.createElement("label");
        const radio = document.createElement("input");
        radio.type = "radio"; radio.name = "edit_word_id"; radio.value = word.id;
        radio.dataset.suggestion = word.suggested_caption;
        label.append(radio, document.createTextNode(" " + word.phrase)); card.append(label);
        for (const text of [word.reading, word.explanation]) {
          const paragraph = document.createElement("p"); paragraph.textContent = text; card.append(paragraph);
        }
        const link = document.createElement("a"); link.textContent = word.source_label;
        link.href = word.reference_url; link.className = "source"; link.target = "_blank"; link.rel = "noopener noreferrer";
        card.append(link); options.append(card);
      }
      dirty = true;
    } catch (e) {
      error.textContent = e instanceof SyntaxError ? "通信に失敗しました。もう一度お試しください。" : e.message;
    } finally { lock(false); }
  });
  editForm.addEventListener("input", () => dirty = true);
  editForm.elements.photo.addEventListener("change", () => {
    if (previewURL) URL.revokeObjectURL(previewURL);
    const file = editForm.elements.photo.files[0];
    previewURL = file ? URL.createObjectURL(file) : null;
    preview.src = previewURL || savedPreview;
  });
  editForm.elements.location.addEventListener("change", () => {
    const other = editForm.elements.location.value === "other";
    document.getElementById("edit-other").hidden = !other;
    if (!other) editForm.elements.location_other.value = "";
  });
  editForm.addEventListener("submit", async event => {
    event.preventDefault();
    if (busy) return;
    const data = new FormData(editForm);
    lock(true); error.textContent = "";
    try {
      const response = await fetch(editForm.action, {method: "POST", body: data, headers: {"X-Requested-With": "XMLHttpRequest"}});
      const result = await response.json();
      if (!response.ok) throw new Error([result.error || "保存できませんでした。", ...Object.values(result.fields || {}).flat()].join(" "));
      dirty = false;
      window.location.assign(result.redirect);
    } catch (e) {
      error.textContent = e instanceof SyntaxError ? "通信に失敗しました。入力を残したまま再試行してください。" : e.message;
      lock(false);
    }
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
