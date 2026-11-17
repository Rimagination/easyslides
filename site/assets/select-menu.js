/* Small, select-only comboboxes. Native selects remain the source of truth. */
(() => {
  const menus = new Map();
  let opened;

  function close(menu = opened) {
    if (!menu) return;
    if (menu.panel.hidePopover && menu.panel.matches(':popover-open')) menu.panel.hidePopover();
    menu.panel.hidden = true;
    menu.trigger.setAttribute('aria-expanded', 'false');
    menu.trigger.removeAttribute('aria-activedescendant');
    if (opened === menu) opened = null;
  }

  function place(menu) {
    const rect = menu.trigger.getBoundingClientRect();
    const edge = 12;
    const below = innerHeight - rect.bottom - edge - 8;
    const above = rect.top - edge - 8;
    const upward = below < Math.min(menu.panel.scrollHeight, 320) && above > below;
    const available = Math.max(80, upward ? above : below);
    const width = Math.min(Math.max(rect.width, menu.select.id === 'heroWorkSelect' ? 360 : 230), innerWidth - edge * 2);
    Object.assign(menu.panel.style, {
      width: width + 'px', maxHeight: Math.min(440, available) + 'px',
      left: Math.min(Math.max(edge, rect.left), innerWidth - width - edge) + 'px',
      top: (upward ? Math.max(edge, rect.top - Math.min(menu.panel.scrollHeight, 440, available) - 8) : rect.bottom + 8) + 'px',
    });
  }

  function activate(menu, index, scroll = true) {
    menu.active = Math.max(0, Math.min(menu.rows.length - 1, index));
    menu.rows.forEach((row, i) => row.classList.toggle('is-active', i === menu.active));
    const row = menu.rows[menu.active];
    if (!row) return;
    menu.trigger.setAttribute('aria-activedescendant', row.id);
    if (scroll) {
      const top = row.offsetTop;
      if (top < menu.panel.scrollTop) menu.panel.scrollTop = top;
      else if (top + row.offsetHeight > menu.panel.scrollTop + menu.panel.clientHeight) menu.panel.scrollTop = top + row.offsetHeight - menu.panel.clientHeight;
    }
  }

  function open(menu) {
    close();
    opened = menu;
    menu.panel.hidden = false;
    if (menu.panel.showPopover) menu.panel.showPopover();
    menu.trigger.setAttribute('aria-expanded', 'true');
    place(menu);
    activate(menu, menu.select.selectedIndex);
  }

  function choose(menu, index) {
    const option = menu.select.options[index];
    if (!option || option.disabled) return;
    close(menu);
    menu.select.value = option.value;
    sync(menu.select);
    menu.select.dispatchEvent(new Event('change', { bubbles: true }));
    menu.trigger.focus({ preventScroll: true });
  }

  function optionContent(option) {
    const fragment = document.createDocumentFragment();
    if (option.dataset.thumbnail) {
      const img = document.createElement('img');
      Object.assign(img, { src: option.dataset.thumbnail, alt: '', width: 64, height: 40, decoding: 'async' });
      fragment.append(img);
    }
    const text = document.createElement('span');
    text.className = 'select-option-text';
    const title = document.createElement('span');
    title.className = 'select-option-title';
    title.textContent = option.textContent;
    text.append(title);
    if (option.dataset.detail) {
      const detail = document.createElement('small');
      detail.textContent = option.dataset.detail;
      text.append(detail);
    }
    fragment.append(text);
    return fragment;
  }

  function sync(select) {
    let menu = menus.get(select);
    if (!menu) {
      const wrapper = document.createElement('div');
      wrapper.className = 'select-menu';
      const trigger = document.createElement('button');
      trigger.type = 'button';
      trigger.id = select.id + '-trigger';
      trigger.className = 'select-trigger';
      trigger.setAttribute('role', 'combobox');
      trigger.setAttribute('aria-haspopup', 'listbox');
      trigger.setAttribute('aria-expanded', 'false');
      trigger.setAttribute('aria-controls', select.id + '-listbox');
      trigger.setAttribute('aria-labelledby', select.getAttribute('aria-labelledby') + ' ' + select.id + '-value');
      const current = document.createElement('span');
      current.className = 'select-current';
      current.id = select.id + '-value';
      trigger.append(current, EasySlidesIcons.create('chevron-down'));
      wrapper.append(trigger);
      select.after(wrapper);
      select.hidden = true;
      const panel = document.createElement('div');
      panel.id = select.id + '-listbox';
      panel.className = 'select-popover';
      panel.setAttribute('role', 'listbox');
      panel.setAttribute('aria-labelledby', select.getAttribute('aria-labelledby'));
      panel.setAttribute('popover', 'manual');
      panel.hidden = true;
      document.body.append(panel);
      menu = { select, trigger, current, panel, rows: [], active: 0, typed: '', typedAt: 0 };
      menus.set(select, menu);
      trigger.addEventListener('click', () => opened === menu ? close(menu) : open(menu));
      trigger.addEventListener('keydown', event => {
        const isOpen = opened === menu;
        if (event.key === 'Tab') { close(menu); return; }
        if (event.key === 'Escape') { close(menu); event.preventDefault(); return; }
        if (['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter', ' '].includes(event.key)) {
          event.preventDefault();
          if (!isOpen) { open(menu); return; }
          if (event.key === 'ArrowDown') activate(menu, menu.active + 1);
          else if (event.key === 'ArrowUp') activate(menu, menu.active - 1);
          else if (event.key === 'Home') activate(menu, 0);
          else if (event.key === 'End') activate(menu, menu.rows.length - 1);
          else choose(menu, menu.active);
        } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
          if (!isOpen) open(menu);
          menu.typed = (Date.now() - menu.typedAt > 700 ? '' : menu.typed) + event.key.toLowerCase();
          menu.typedAt = Date.now();
          const index = Array.from(select.options).findIndex(option => option.textContent.toLowerCase().startsWith(menu.typed));
          if (index >= 0) activate(menu, index);
        }
      });
    }
    close(menu);
    const selected = select.selectedOptions[0];
    if (selected) menu.current.replaceChildren(optionContent(selected));
    menu.panel.replaceChildren();
    menu.rows = [];
    Array.from(select.children).forEach(child => {
      const grouped = child.tagName === 'OPTGROUP';
      const group = document.createElement('div');
      if (grouped) {
        group.setAttribute('role', 'group');
        group.setAttribute('aria-label', child.label);
        const heading = document.createElement('div');
        heading.className = 'select-group-title';
        heading.setAttribute('aria-hidden', 'true');
        heading.textContent = child.label;
        group.append(heading);
      }
      (grouped ? Array.from(child.children) : [child]).forEach(option => {
        const index = menu.rows.length;
        const row = document.createElement('div');
        row.id = select.id + '-option-' + index;
        row.className = 'select-option';
        row.setAttribute('role', 'option');
        row.setAttribute('aria-selected', String(option.selected));
        row.append(optionContent(option), EasySlidesIcons.create('check'));
        row.addEventListener('pointermove', () => activate(menu, index, false));
        row.addEventListener('pointerdown', event => event.preventDefault());
        row.addEventListener('click', () => choose(menu, index));
        group.append(row);
        menu.rows.push(row);
      });
      menu.panel.append(group);
    });
  }

  document.addEventListener('pointerdown', event => {
    if (opened && !opened.panel.contains(event.target) && !opened.trigger.contains(event.target)) close();
  });
  document.addEventListener('focusin', event => {
    if (opened && event.target !== opened.trigger && !opened.panel.contains(event.target)) close();
  });
  window.addEventListener('resize', () => opened && place(opened));
  window.addEventListener('scroll', event => {
    if (opened && !opened.panel.contains(event.target)) close();
  }, true);
  window.EasySlidesSelect = { sync };
})();
