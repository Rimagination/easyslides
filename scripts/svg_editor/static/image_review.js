/* Native browser annotations target the original image; this viewer never writes. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const viewport = document.querySelector('.viewport');
  let slides = [], page = -1, loading = false;
  function status(message, error = false) {
    $('status').textContent = message;
    $('status').className = error ? 'error' : '';
  }
  function imageUrl(slide) {
    return `/api/source-review/image/${encodeURIComponent(slide.name)}?v=${encodeURIComponent(slide.version)}`;
  }
  function zoom() {
    if (page < 0) return;
    const slide = slides[page], css = getComputedStyle(viewport);
    const width = Math.max(1, viewport.clientWidth - parseFloat(css.paddingLeft) - parseFloat(css.paddingRight));
    const height = Math.max(1, viewport.clientHeight - parseFloat(css.paddingTop) - parseFloat(css.paddingBottom));
    const mode = $('zoom').value;
    const size = mode === 'fit' ? Math.min(width, height * slide.width / slide.height, slide.width)
      : mode === 'width' ? width : slide.width * Number(mode);
    $('canvas').style.width = `${size}px`;
  }
  function showPage(index, push = true) {
    if (loading || index < 0 || index >= slides.length) return;
    page = index;
    const slide = slides[page], image = $('original'), url = new URL(location.href);
    url.searchParams.set('slide', slide.name);
    if (push) history.pushState(null, '', url); else history.replaceState(null, '', url);
    document.title = `第 ${page+1} 页 · ${slide.name} · imagegen 原图`;
    image.hidden = false;
    image.alt = `imagegen 原图，第 ${page+1} 页，${slide.name}`;
    image.dataset.sourceSlide = slide.name;
    image.dataset.sourceVersion = slide.version;
    image.dataset.sourceWidth = slide.width;
    image.dataset.sourceHeight = slide.height;
    image.width = slide.width;
    image.height = slide.height;
    status('正在读取原图');
    image.src = imageUrl(slide);
    $('source-name').href = image.src;
    $('source-name').textContent = slide.name;
    $('source-name').hidden = false;
    $('page-label').textContent = `${page+1} / ${slides.length}`;
    $('prev').disabled = page === 0;
    $('next').disabled = page === slides.length-1;
    $('zoom').disabled = false;
    document.querySelectorAll('.thumb').forEach((button, i) => {
      if (i === page) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
    });
    document.querySelector('.thumb[aria-current="page"]').scrollIntoView({block:'nearest', inline:'nearest'});
    zoom();
    viewport.scrollTo(0, 0);
  }
  function fromUrl() {
    const name = new URL(location.href).searchParams.get('slide');
    const index = name ? slides.findIndex(slide => slide.name === name) : 0;
    if (index < 0) {
      page = -1;
      $('original').hidden = $('source-name').hidden = true;
      $('prev').disabled = $('next').disabled = $('zoom').disabled = true;
      $('page-label').textContent = `— / ${slides.length}`;
      document.querySelectorAll('.thumb').forEach(button => button.removeAttribute('aria-current'));
      status(`找不到原图 ${name}，请选择页码`, true);
    } else showPage(index, false);
  }
  async function load() {
    if (loading) return;
    loading = true;
    $('reload').disabled = true;
    $('prev').disabled = $('next').disabled = $('zoom').disabled = true;
    $('slides').inert = true;
    status('正在读取原图');
    try {
      const response = await fetch('/api/source-review', {cache:'no-store'});
      if (!response.ok) throw new Error(`读取失败（HTTP ${response.status}），请刷新重试`);
      const data = await response.json();
      slides = data.slides;
      page = -1;
      $('original').hidden = $('source-name').hidden = true;
      $('project').textContent = data.project;
      $('slides').replaceChildren();
      slides.forEach((slide, index) => {
        const button = document.createElement('button');
        button.className = 'thumb'; button.title = slide.name;
        button.setAttribute('aria-label', `第 ${index+1} 页，${slide.name}`);
        const image = document.createElement('img');
        image.src = imageUrl(slide); image.alt = ''; image.loading = 'lazy';
        const label = document.createElement('span'); label.textContent = String(index+1);
        button.append(image, label); button.onclick = () => showPage(index);
        $('slides').append(button);
      });
      loading = false;
      if (slides.length) fromUrl();
      else { $('page-label').textContent = '0 / 0'; status('没有找到原图'); }
    } catch (error) {
      page = -1;
      $('original').hidden = $('source-name').hidden = true;
      status(error.message, true);
    } finally { loading = false; $('reload').disabled = false; $('slides').inert = false; }
  }
  $('original').onload = () => { if (page >= 0) status(`${slides[page].width} × ${slides[page].height}`); };
  $('original').onerror = () => status('原图加载失败，请刷新重试', true);
  $('prev').onclick = () => showPage(page-1);
  $('next').onclick = () => showPage(page+1);
  $('zoom').onchange = zoom;
  $('reload').onclick = load;
  window.addEventListener('popstate', fromUrl);
  new ResizeObserver(zoom).observe(viewport);
  load();
})();
