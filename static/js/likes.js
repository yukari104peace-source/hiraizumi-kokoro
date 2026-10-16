for (const form of document.querySelectorAll('.like-form')) {
  const button = form.querySelector('button[type="submit"]');
  const count = form.querySelector('[data-like-count]') || button.querySelector('span:last-child');
  const status = document.createElement('p');
  status.className = 'like-status';
  status.setAttribute('role', 'status');
  status.hidden = true;
  form.append(status);
  let busy = false;
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    busy = true;
    button.disabled = true;
    status.hidden = true;
    try {
      // The hidden input named "action" shadows the form.action DOM property.
      const response = await fetch(form.getAttribute('action'), {
        method: 'POST', body: new FormData(form), credentials: 'same-origin',
        headers: {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || '保存できませんでした。もう一度お試しください。');
      if (typeof result.liked !== 'boolean' || !Number.isInteger(result.count)) {
        throw new Error('結果を確認できませんでした。もう一度お試しください。');
      }
      button.classList.toggle('is-liked', result.liked);
      button.setAttribute('aria-pressed', String(result.liked));
      const label = button.classList.contains('comment-like-button')
        ? (result.liked ? 'コメントのいいねを取り消す' : 'コメントにいいねする')
        : (result.liked ? 'いいねを取り消す' : 'いいねする');
      button.setAttribute('aria-label', `${label}（${result.count}件）`);
      button.querySelector('[aria-hidden]').textContent = result.liked ? '♥' : '♡';
      count.textContent = result.count;
      form.elements.namedItem('action').value = result.liked ? 'unlike' : 'like';
    } catch (error) {
      status.textContent = error instanceof TypeError || error instanceof SyntaxError
        ? '通信結果を確認できませんでした。もう一度お試しください。' : error.message;
      status.hidden = false;
    } finally {
      busy = false;
      button.disabled = false;
    }
  });
}
