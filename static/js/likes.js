function updateLikeUsers(control, result) {
  const details = control.querySelector('[data-like-users-details]');
  const count = details.querySelector('[data-like-count]');
  const list = details.querySelector('[data-like-users-list]');
  count.textContent = result.count;
  count.setAttribute('aria-label', `「いいね！」した人を表示（${result.count}件）`);
  list.replaceChildren(...result.users.map(username => {
    const item = document.createElement('li');
    item.textContent = `${username} さん`;
    return item;
  }));
  if (result.count === 0) details.open = false;
}

for (const details of document.querySelectorAll('[data-like-users-details]')) {
  const count = details.querySelector('[data-like-count]');
  count.addEventListener('click', event => {
    if (Number.parseInt(count.textContent, 10) === 0) event.preventDefault();
  });
}

for (const form of document.querySelectorAll('.like-form')) {
  const button = form.querySelector('button[type="submit"]');
  const control = form.closest('[data-like-control]');
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
      if (typeof result.liked !== 'boolean' || !Number.isInteger(result.count) ||
          !Array.isArray(result.users) || !result.users.every(username => typeof username === 'string')) {
        throw new Error('結果を確認できませんでした。もう一度お試しください。');
      }
      button.classList.toggle('is-liked', result.liked);
      button.setAttribute('aria-pressed', String(result.liked));
      const label = button.classList.contains('comment-like-button')
        ? (result.liked ? 'コメントのいいねを取り消す' : 'コメントにいいねする')
        : (result.liked ? 'いいねを取り消す' : 'いいねする');
      button.setAttribute('aria-label', `${label}（${result.count}件）`);
      button.querySelector('[aria-hidden]').textContent = result.liked ? '♥' : '♡';
      updateLikeUsers(control, result);
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
