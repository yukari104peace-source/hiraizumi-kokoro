const editForm = document.getElementById("edit-post-form");
if (editForm) {
  let dirty = false, busy = false, previewURL = null;
  const preview = document.getElementById("edit-preview");
  const savedPreview = preview.src;
  const error = document.getElementById("edit-error");
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
    busy = true; error.textContent = "";
    editForm.querySelectorAll("button,input,select,textarea").forEach(el => el.disabled = true);
    try {
      const response = await fetch(editForm.action, {method: "POST", body: data, headers: {"X-Requested-With": "XMLHttpRequest"}});
      const result = await response.json();
      if (!response.ok) throw new Error([result.error || "保存できませんでした。", ...Object.values(result.fields || {}).flat()].join(" "));
      dirty = false;
      window.location.assign(result.redirect);
    } catch (e) {
      error.textContent = e instanceof SyntaxError ? "通信に失敗しました。入力を残したまま再試行してください。" : e.message;
      busy = false;
      editForm.querySelectorAll("button,input,select,textarea").forEach(el => el.disabled = false);
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
