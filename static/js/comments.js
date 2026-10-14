function openCommentThread() {
  const target = document.getElementById(window.location.hash.slice(1));
  if (target && target.matches('details.post-comments')) target.open = true;
}
openCommentThread();
window.addEventListener('hashchange', openCommentThread);
for (const form of document.querySelectorAll('.comment-delete-form')) {
  form.addEventListener('submit', event => {
    if (!window.confirm('このコメントを削除しますか？ 返信は残ります。')) event.preventDefault();
  });
}
for (const form of document.querySelectorAll('.comment-form')) {
  form.addEventListener('submit', () => { form.querySelector('button[type="submit"]').disabled = true; });
}
window.addEventListener('pageshow', () => {
  document.querySelectorAll('.comment-form button[type="submit"]').forEach(button => button.disabled = false);
});
