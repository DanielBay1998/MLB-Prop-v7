(function () {
  const buttons = Array.from(document.querySelectorAll('[data-tab]'));
  const panels = Array.from(document.querySelectorAll('.tab-panel'));
  function setActive(tab) {
    buttons.forEach((btn) => btn.classList.toggle('is-active', btn.dataset.tab === tab));
    panels.forEach((panel) => panel.classList.toggle('hidden', panel.id !== `tab-${tab}`));
    window.location.hash = tab;
  }
  buttons.forEach((btn) => btn.addEventListener('click', () => setActive(btn.dataset.tab)));
  const initial = (window.location.hash || '#dashboard').replace('#', '');
  setActive(initial);
})();
