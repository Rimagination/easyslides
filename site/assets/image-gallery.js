(() => {
  const tabs = [...document.querySelectorAll('[data-library]')];
  const grid = document.querySelector('#imageGrid');
  const status = document.querySelector('#imageLibraryStatus');
  const base = 'assets/image-references/';
  let selected = new URLSearchParams(location.search).get('library') === 'image' ? 'image' : 'native';
  const english = () => document.documentElement.lang === 'en';

  function selectLibrary(value, updateUrl = true) {
    selected = value;
    tabs.forEach(tab => {
      const active = tab.dataset.library === value;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      document.getElementById(tab.getAttribute('aria-controls')).hidden = !active;
    });
    if (updateUrl) {
      const url = new URL(location.href);
      url.searchParams.set('library', value);
      history.replaceState(null, '', url);
    }
    render();
  }

  function render() {
    const en = english();
    tabs[0].textContent = en ? 'Native templates' : '原生模板';
    tabs[1].textContent = en ? 'Image references' : '图片参考模板';
    if (selected !== 'image') return;
    grid.replaceChildren();
    const entries = window.imageReferenceTemplates;
    status.textContent = '';
    document.querySelector('#imageLibrarySummary').textContent = en
      ? 'Whole-deck visual references for AI image generation.'
      : '整套缩略图，用于 AI 生图的配色、版式与背景参考。';
    if (!Array.isArray(entries) || !entries.length) {
      status.textContent = en ? 'Image references are currently unavailable. Please try again later.' : '图片模板暂时无法加载，请稍后重试。';
      return;
    }
    entries.forEach(entry => {
      const card = document.createElement('article');
      card.className = 'work-card image-card';
      const link = document.createElement('a');
      link.className = 'image-sheet';
      link.href = base + entry.image;
      link.target = '_blank';
      link.rel = 'noopener';
      link.setAttribute('aria-label', (en ? 'View original: ' : '查看原图：') + entry.name);
      const img = document.createElement('img');
      img.src = base + entry.preview;
      img.alt = entry.name;
      img.loading = 'lazy';
      img.decoding = 'async';
      link.append(img);
      const title = document.createElement('h3');
      title.textContent = entry.name;
      const description = document.createElement('p');
      description.textContent = entry.style_summary;
      const id = document.createElement('code');
      id.textContent = entry.id;
      const actions = document.createElement('div');
      actions.className = 'image-actions';
      const original = document.createElement('a');
      original.href = link.href;
      original.target = '_blank';
      original.rel = 'noopener';
      original.textContent = en ? `View original · ${entry.slide_count} slides` : `查看原图 · ${entry.slide_count} 页`;
      const copy = document.createElement('button');
      copy.type = 'button';
      copy.textContent = en ? 'Copy template ID' : '复制模板 ID';
      copy.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(entry.id);
          copy.textContent = english() ? 'Copied' : '已复制';
          status.textContent = english() ? `Copied: ${entry.id}` : `已复制：${entry.id}`;
        } catch {
          status.textContent = english() ? `Copy this template ID: ${entry.id}` : `请复制此模板 ID：${entry.id}`;
          const range = document.createRange();
          range.selectNodeContents(id);
          const selection = window.getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          copy.textContent = english() ? 'ID selected' : '已选中 ID';
        }
      });
      actions.append(original, copy);
      card.append(link, title, description, id, actions);
      grid.append(card);
    });
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectLibrary(tab.dataset.library));
    tab.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + 1) % tabs.length;
      tabs[next].focus();
      selectLibrary(tabs[next].dataset.library);
    });
  });
  window.renderImageReferences = render;
  selectLibrary(selected, false);
})();
