(() => {
  const nativeGrid = document.querySelector('#nativeTemplateGrid');
  const imageGrid = document.querySelector('#imageGrid');
  const english = () => document.documentElement.lang === 'en';
  const demoWorks = { academic_general: 8, literature_minimal: 0, defense_leftnav: 1, defense_topnav: 2, nsfc_defense: 3, thu_speech: 4 };
  const nativeTemplates = [
    ['academic_general', '默认增强学术', 'Enhanced academic', '高信息密度 · 学科主题图 · 自定配色', 'Dense evidence · discipline imagery · custom colors', 'assets/slides/work-09/slide-09.jpg'],
    ['academic_classic', '经典通用学术', 'Classic academic', '研究背景 · 方法 · 结果 · 讨论', 'Background · methods · results · discussion', 'assets/native-templates/template-academic-classic.png'],
    ['academic_scqa', 'SCQA 学术叙事', 'SCQA academic', '情境 · 冲突 · 问题 · 回答', 'Situation · complication · question · answer', 'assets/native-templates/template-academic-scqa.png'],
    ['defense_leftnav', '左侧导航答辩', 'Defense / side navigation', '章节常驻左侧，突出答辩进程', 'Persistent side navigation for thesis defenses', 'assets/slides/work-02/slide-08.jpg'],
    ['defense_topnav', '顶部导航答辩', 'Defense / top navigation', '顶部章节导航，正文空间完整', 'Top chapter navigation with a full-width body', 'assets/slides/work-03/slide-08.jpg'],
    ['literature_minimal', '简洁文献汇报', 'Minimal literature report', '清晰的图文关系与论文证据', 'Clear figure–text relationships and paper evidence', 'assets/slides/work-01/slide-08.jpg'],
    ['nsfc_defense', '国自然基金答辩', 'NSFC grant defense', '研究问题 · 技术路线 · 创新与基础', 'Research questions · methods · novelty · track record', 'assets/slides/work-04/slide-05.jpg'],
    ['thu_speech', '清华学术汇报', 'Tsinghua academic talk', '学术演讲与正式汇报', 'Academic talks and formal presentations', 'assets/slides/work-05/slide-08.jpg'],
  ];

  function previewLink(source, thumbnail, title, className, width, height) {
    const link = document.createElement('a');
    link.className = className;
    link.href = source;
    link.target = '_blank';
    link.rel = 'noopener';
    link.setAttribute('aria-label', (english() ? 'View full size: ' : '查看大图：') + title);
    const img = document.createElement('img');
    Object.assign(img, { src: thumbnail, alt: title, loading: 'lazy', decoding: 'async', width, height });
    link.append(img);
    return link;
  }

  function copyButton(id, code, status) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'copy-id';
    const label = document.createElement('span');
    label.textContent = english() ? 'Copy ID' : '复制 ID';
    button.append(EasySlidesIcons.create('copy'), label);
    button.setAttribute('aria-label', (english() ? 'Copy template ID: ' : '复制模板 ID：') + id);
    button.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(id);
        label.textContent = english() ? 'Copied' : '已复制';
        button.querySelector('.lucide').replaceWith(EasySlidesIcons.create('check'));
        status.textContent = (english() ? 'Copied: ' : '已复制：') + id;
      } catch {
        const range = document.createRange();
        range.selectNodeContents(code);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        status.textContent = (english() ? 'Copy the selected ID: ' : '请复制选中的 ID：') + id;
      }
    });
    return button;
  }

  function render() {
    const en = english();
    const query = document.querySelector('#gallerySearch').value.trim().toLowerCase();
    nativeGrid.replaceChildren();
    imageGrid.replaceChildren();
    const nativeStatus = document.querySelector('#nativeTemplateStatus');
    const imageStatus = document.querySelector('#imageLibraryStatus');
    nativeStatus.textContent = imageStatus.textContent = '';
    const demoGrid = document.querySelector('#heroTemplateGrid');
    demoGrid.replaceChildren();
    nativeTemplates.forEach(([id, zh, name]) => {
      if (!(id in demoWorks)) return;
      const workIndex = demoWorks[id];
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'player-template';
      button.dataset.heroWork = workIndex;
      button.setAttribute('aria-pressed', String(Number(document.querySelector('#heroWorkSelect').value) === workIndex));
      const img = document.createElement('img');
      Object.assign(img, { src: `assets/native-templates/template-${id.replaceAll('_', '-')}.webp`, alt: '', width: 480, height: 270, loading: 'lazy', decoding: 'async' });
      const label = document.createElement('span');
      label.textContent = en ? name : zh;
      button.append(img, label);
      button.addEventListener('click', () => window.selectHeroWork(workIndex));
      demoGrid.append(button);
    });
    nativeTemplates.forEach(([id, zh, name, zhDescription, description, source]) => {
      if (query && ![id, zh, name, zhDescription, description].join(' ').toLowerCase().includes(query)) return;
      const title = en ? name : zh;
      const card = document.createElement('article');
      card.className = 'template-card';
      card.dataset.template = id;
      const preview = previewLink(source, `assets/native-templates/template-${id.replaceAll('_', '-')}.webp`, title, 'template-preview', 480, 270);
      const heading = document.createElement('div');
      heading.className = 'template-title';
      const h3 = document.createElement('h3');
      h3.textContent = title;
      heading.append(h3);
      if (id === 'academic_general') {
        const label = document.createElement('span');
        label.className = 'default-label';
        label.textContent = en ? 'DEFAULT' : '默认';
        heading.append(label);
      }
      const p = document.createElement('p');
      p.textContent = en ? description : zhDescription;
      const code = document.createElement('code');
      code.textContent = id;
      const actions = document.createElement('div');
      actions.className = 'template-actions';
      actions.append(code, copyButton(id, code, nativeStatus));
      card.append(preview, heading, p, actions);
      nativeGrid.append(card);
    });

    const entries = window.imageReferenceTemplates;
    if (!Array.isArray(entries) || !entries.length) {
      imageStatus.textContent = en ? 'Style sheets are unavailable. Please try again later.' : '参考风格暂时无法加载，请稍后重试。';
      return;
    }
    entries.forEach(entry => {
      if (query && ![entry.id, entry.name, entry.style_summary].join(' ').toLowerCase().includes(query)) return;
      const card = document.createElement('article');
      card.className = 'work-card image-card';
      const source = 'assets/image-references/' + entry.image;
      const preview = previewLink(source, `assets/style-previews/${entry.id}.webp`, entry.name, 'image-sheet', 640, 498);
      const h3 = document.createElement('h3');
      h3.textContent = entry.name;
      const p = document.createElement('p');
      p.textContent = entry.style_summary;
      const code = document.createElement('code');
      code.textContent = entry.id;
      const actions = document.createElement('div');
      actions.className = 'image-actions';
      const original = document.createElement('a');
      Object.assign(original, { href: source, target: '_blank', rel: 'noopener', textContent: en ? `Full size · ${entry.slide_count} slides` : `查看大图 · ${entry.slide_count} 页` });
      actions.append(original, copyButton(entry.id, code, imageStatus));
      card.append(preview, h3, p, code, actions);
      imageGrid.append(card);
    });
    const sections = [
      ['native-templates', '#nativeTemplateGrid > article'],
      ['native-work', '#worksGrid > article'],
      ['rebuild-work', '#rebuildWorksGrid > article'],
      ['image-references', '#imageGrid > article'],
    ];
    let matches = 0;
    sections.forEach(([id, selector]) => {
      const count = document.querySelectorAll(selector).length;
      matches += count;
      document.getElementById(id).hidden = Boolean(query && !count);
    });
    document.querySelector('.showcase-heading').hidden = Boolean(query && !document.querySelector('#worksGrid > article, #rebuildWorksGrid > article'));
    document.querySelector('#gallerySearchStatus').textContent = query
      ? en ? `${matches} results for “${query}”` : `“${query}” · ${matches} 项匹配`
      : '';
  }

  window.renderImageReferences = render;
  render();
  const playerObserver = new IntersectionObserver(([entry]) => {
    document.body.dataset.playerVisible = String(entry.isIntersecting);
  }, { rootMargin: '-88px 0px 0px 0px', threshold: 0 });
  playerObserver.observe(document.querySelector('#heroStageMount'));
  const sectionObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      document.querySelectorAll('.gallery-nav a').forEach(link => {
        if (link.hash === '#' + entry.target.id) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
      });
    });
  }, { rootMargin: '-165px 0px -45% 0px', threshold: 0 });
  document.querySelectorAll('.gallery-section').forEach(section => sectionObserver.observe(section));
  // Old category URLs now lead to an open section without hiding the others.
  const params = new URLSearchParams(location.search);
  if (params.get('view') !== 'detail' && (!location.hash || location.hash === '#catalog')) {
    const target = params.get('library') === 'image' ? 'image-references' : params.get('route') === 'rebuild' ? 'rebuild-work' : null;
    if (target) requestAnimationFrame(() => document.getElementById(target).scrollIntoView());
  }
})();
