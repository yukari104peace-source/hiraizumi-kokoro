// Fit the phrase itself; let its source link wrap independently.
const wordHeadings = [...document.querySelectorAll('.post-word-text .word-phrase')];
function fitWords() {
  for (const heading of wordHeadings) {
    const phrase = heading.querySelector('.word-phrase-text');
    if (!phrase) continue;
    phrase.style.removeProperty('font-size');
    const available = heading.clientWidth;
    if (!available) continue;
    const width = phrase.getBoundingClientRect().width;
    if (width > available) {
      const size = parseFloat(getComputedStyle(phrase).fontSize);
      // Leave one pixel for fractional layout rounding.
      phrase.style.fontSize = `${size * (available - 1) / width}px`;
    }
  }
}
let pending = false;
function scheduleWordFit() {
  if (pending) return;
  pending = true;
  requestAnimationFrame(() => { pending = false; fitWords(); });
}
fitWords();
window.addEventListener('resize', scheduleWordFit);
window.addEventListener('pageshow', scheduleWordFit);
if ('ResizeObserver' in window) {
  const observer = new ResizeObserver(scheduleWordFit);
  for (const heading of wordHeadings) observer.observe(heading.parentElement);
}
if (document.fonts) {
  document.fonts.ready.then(scheduleWordFit);
  document.fonts.addEventListener('loadingdone', scheduleWordFit);
}
