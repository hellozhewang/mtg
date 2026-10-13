/* Deck catalog. Copied verbatim to docs/app.js by scripts/build_site.py.
 *
 * Each card row carries up to three image sources, and which one is used is the
 * whole hosting policy in one place:
 *   data-thumb  a local file in docs/img/ — gallery grid. Committed, so it is
 *               same-origin and instant, and small enough not to bloat the repo.
 *   data-img    cards.scryfall.io at readable size — hover preview and zoom.
 *   data-back   the same, for the back face of a double-faced card.
 *
 * No build step and no framework: this file ships exactly as written.
 *
 * ---------------------------------------------------------------------------
 * TWO CONVENTIONS, both scar tissue. Three bugs here came from a name matching
 * more than it was meant to, and not one threw an error — each quietly did the
 * wrong thing until a rendered page showed it.
 *
 * 1. ONE FEATURE, ONE FUNCTION. Every feature is an `init*` with its own scope,
 *    and anything shared is passed as an argument. This all used to sit in a
 *    single IIFE where thirteen `var`s shared one scope, and the lightbox's
 *    `var box` silently reassigned the search box's `var box`. The filter then
 *    read `.value` off a <div>, got undefined, and treated every query as
 *    empty. Scoping makes that class of bug impossible; a prefix would only
 *    have made it less likely.
 *
 * 2. NEVER SELECT A BARE TAG INSIDE A COMPONENT. Qualify with the class that
 *    states the element's role — `img.thumb`, never `img`. A card row holds one
 *    <img> per mana symbol in its cost, so `querySelector('img')` matched a
 *    symbol and the gallery skipped every card that costs mana; separately the
 *    CSS rule `.card img` stretched those symbols to full width.
 * ---------------------------------------------------------------------------
 */
(function () {
  'use strict';

  /* ---- deck menu -------------------------------------------------------- */
  // On every page, not just the index: a deck page is the thing people share,
  // and landing on one should not be a dead end.
  function initDeckPicker() {
    var picker = document.querySelector('.deckpicker');
    if (!picker) return;
    picker.addEventListener('change', function () {
      if (picker.value) location.href = picker.value;
    });
  }

  /* ---- search / filter --------------------------------------------------- */
  // One box, two jobs: on the index it filters deck tiles (including by author),
  // on a deck page it filters card rows. Same code — only the elements carrying
  // the text differ.
  function initSearch(catalogState) {
    var input = document.querySelector('.search');
    if (!input) return;
    var tiles = toArray(document.querySelectorAll('.tile'));
    var rows = toArray(document.querySelectorAll('.card'));
    var items = tiles.length ? tiles : rows;
    if (!items.length) return;
    var strategy = document.querySelector('.strategy-filter');
    var clear = document.querySelector('.clear-filters');
    var results = document.querySelector('.catalog-results');

    items.forEach(function (el) {
      el.setAttribute('data-key', fold(el.dataset.search || el.dataset.name || ''));
    });
    var total = items.filter(function (el) { return !el.classList.contains('mirror'); }).length;

    var sections = toArray(document.querySelectorAll(tiles.length
      ? '.bracket-group, .strategy-group, .tier-group' : '.cards .cat'));
    var disclosures = toArray(document.querySelectorAll('.decks details'));
    var beforeFilter = null;
    var empty = document.createElement('p');
    empty.className = 'nomatch';
    (document.querySelector('main') || document.body).appendChild(empty);

    function apply() {
      var q = fold(input.value).trim();
      var theme = strategy ? strategy.value : '';
      var filtering = Boolean(q || theme);
      if (catalogState) catalogState.setFiltering(filtering);
      if (filtering && !beforeFilter) {
        beforeFilter = disclosures.map(function (section) { return section.open; });
      }
      var shown = 0;
      items.forEach(function (el) {
        var hit = (!q || el.getAttribute('data-key').indexOf(q) !== -1)
          && (!theme || (el.dataset.themes || '').split(' ').indexOf(theme) !== -1);
        el.classList.toggle('is-filtered', !hit);
        // A mirror is a second link to a deck already counted elsewhere.
        if (hit && !el.classList.contains('mirror')) shown++;
      });
      // Hide a section once every child is gone, so the page does not turn into
      // a column of empty headings.
      sections.forEach(function (sec) {
        var count = sec.querySelectorAll('.tile:not(.is-filtered), .card:not(.is-filtered)').length;
        sec.classList.toggle('is-filtered', !count);
        if (filtering && count && sec.matches('details')) sec.open = true;
      });
      if (!filtering && beforeFilter) {
        disclosures.forEach(function (section, i) { section.open = beforeFilter[i]; });
        beforeFilter = null;
      }
      empty.textContent = tiles.length ? 'No decks match these filters.'
        : 'Nothing matches “' + input.value + '”.';
      empty.classList.toggle('on', !shown);
      if (results) results.textContent = (q || theme ? shown + ' of ' : '')
        + total + ' decks';
      if (clear) clear.hidden = !q && !theme;
      if (catalogState) catalogState.save();
    }

    input.addEventListener('input', apply);
    if (strategy) strategy.addEventListener('change', apply);
    if (clear) clear.addEventListener('click', function () {
      input.value = '';
      if (strategy) strategy.value = '';
      apply();
      input.focus();
    });
    // `/` focuses the box, Escape clears it — the two shortcuts people try.
    document.addEventListener('keydown', function (ev) {
      var target = ev.target;
      var editing = target && (target.matches('input, textarea, select') || target.isContentEditable);
      if (ev.key === '/' && !editing) {
        ev.preventDefault();
        input.focus();
        input.select();
      } else if (ev.key === 'Escape' && document.activeElement === input) {
        input.value = '';
        apply();
        input.blur();
      }
    });
    apply();
    return apply;
  }

  /* ---- tooltip placement ------------------------------------------------ */
  // A chip near a tile edge cannot center a 250px tooltip on itself without
  // sending part of the popup outside the clipped tile. Recalculate on each
  // reveal so responsive tile widths and wrapped metadata stay correct.
  function initTooltips() {
    toArray(document.querySelectorAll('.tile [data-tip]')).forEach(function (tip) {
      function centerInTile() {
        // In list view a tile is a full-width row, so centring on it would fling
        // the tooltip most of the page away from the chip it belongs to. Nothing
        // is clipped there either, so the default placement is already right.
        if (tip.closest('.decks[data-view="list"]')) {
          tip.style.removeProperty('--tip-shift-x');
          return;
        }
        var tile = tip.closest('.tile');
        var tileBox = tile.getBoundingClientRect();
        var tipBox = tip.getBoundingClientRect();
        var shift = tileBox.left + tileBox.width / 2
          - tipBox.left - tipBox.width / 2;
        tip.style.setProperty('--tip-shift-x', shift + 'px');
      }
      tip.addEventListener('mouseenter', centerInTile);
      tip.addEventListener('focus', centerInTile);
    });
  }

  /* ---- remembered catalog state ---------------------------------------- */
  function initCatalogState() {
    var wrap = document.querySelector('.decks');
    if (!wrap) return null;
    // / and /index.html share a key. Separate catalog directories (including
    // public and private) keep independent preferences on the same origin.
    var key = 'mtg-catalog-state:' + new URL('.', location.href).pathname;
    var saved = {};
    var legacyLayout = null;
    try {
      legacyLayout = localStorage.getItem('mtg-catalog-layout');
      var parsed = JSON.parse(localStorage.getItem(key));
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) saved = parsed;
    } catch (e) { /* Storage can be blocked, or an old value may be invalid. */ }
    var sections = toArray(wrap.querySelectorAll('details'));
    var openStates = {};
    var filtering = false;
    function sectionKey(section) {
      if (section.classList.contains('strategy-group')) return 'category:' + section.dataset.theme;
      if (section.classList.contains('tier-group')) return 'tier:' + section.dataset.tier;
      return 'bracket:' + section.dataset.bracket;
    }
    sections.forEach(function (section) {
      var id = sectionKey(section);
      var open = saved.sections && saved.sections[id];
      if (typeof open === 'boolean') section.open = open;
      openStates[id] = section.open;
    });
    function captureSections() {
      sections.forEach(function (section) { openStates[sectionKey(section)] = section.open; });
    }
    function save() {
      // Search expands matching sections temporarily. Persist the states from
      // before filtering, including when a deck is opened from search results.
      if (!filtering) captureSections();
      try {
        localStorage.setItem(key, JSON.stringify({
          grouping: wrap.dataset.grouping, layout: wrap.dataset.view, sections: openStates
        }));
      } catch (e) { /* The catalog still works without persistent storage. */ }
    }
    sections.forEach(function (section) { section.addEventListener('toggle', save); });
    // Capture even a last-second toggle before navigation, without relying on
    // the asynchronously dispatched details toggle event.
    window.addEventListener('pagehide', save);
    return {
      grouping: ['categories', 'tiers'].indexOf(saved.grouping) !== -1 ? saved.grouping : 'list',
      layout: (saved.layout === 'list' || saved.layout === 'tiles') ? saved.layout
        : (legacyLayout === 'tiles' ? 'tiles' : 'list'),
      save: save,
      setFiltering: function (active) {
        if (active && !filtering) captureSections();
        filtering = active;
      }
    };
  }

  /* ---- catalog grouping and layout -------------------------------------- */
  // Move the same deck links between bracket, category and tier containers.
  // This preserves filters, tooltips, and one link per deck when switching views.
  //
  // `data-decks`, not `data-view`: the deck page's own toggle claims
  // `.btn[data-view]`, and one selector matching both sets of buttons is exactly
  // the bug convention 2 exists to prevent.
  function initCatalogView(refreshSearch, state) {
    var wrap = document.querySelector('.decks');
    var buttons = toArray(document.querySelectorAll('.btn[data-decks]'));
    if (!wrap || !buttons.length) return;
    var groupingButtons = toArray(document.querySelectorAll('.btn[data-grouping]'));
    var list = wrap.querySelector('.catalog-list');
    var categories = wrap.querySelector('.catalog-categories');
    var tierList = wrap.querySelector('.catalog-tiers');
    var actions = document.querySelector('.category-actions');
    // Mirrors (the local catalog's Goblins section) are rendered in place and
    // never move; only the real tile for each deck travels between views.
    var tiles = toArray(wrap.querySelectorAll('.tile:not(.mirror)'));
    var listTargets = new Map();
    var categoryTargets = new Map();
    var tierTargets = new Map();
    toArray(list.querySelectorAll('.bracket-group')).forEach(function (group) {
      listTargets.set(group.dataset.bracket, group.querySelector('.tiles'));
    });
    toArray(categories.querySelectorAll('.strategy-group')).forEach(function (category) {
      toArray(category.querySelectorAll('.bracket-group')).forEach(function (group) {
        categoryTargets.set(category.dataset.theme + ':' + group.dataset.bracket,
          group.querySelector('.tiles'));
      });
    });
    toArray(tierList.querySelectorAll('.tier-group')).forEach(function (group) {
      tierTargets.set(group.dataset.tier, group.querySelector('.tiles'));
    });
    // The top-level sections Expand all / Collapse all act on in each grouping.
    var collapsible = {
      categories: toArray(categories.querySelectorAll('.strategy-group')),
      tiers: toArray(tierList.querySelectorAll('.tier-group'))
    };

    function groupBy(view) {
      tiles.forEach(function (tile) {
        var target = view === 'categories'
          ? categoryTargets.get(tile.dataset.themes.split(' ')[0] + ':' + tile.dataset.bracket)
          : view === 'tiers' ? tierTargets.get(tile.dataset.tier)
          : listTargets.get(tile.dataset.bracket);
        target.appendChild(tile);
      });
      wrap.dataset.grouping = view;
      list.hidden = view !== 'list';
      categories.hidden = view !== 'categories';
      tierList.hidden = view !== 'tiers';
      actions.hidden = view === 'list';
      groupingButtons.forEach(function (btn) {
        btn.setAttribute('aria-pressed', String(btn.dataset.grouping === view));
      });
      if (refreshSearch) refreshSearch();
      state.save();
    }
    groupingButtons.forEach(function (btn) {
      btn.addEventListener('click', function () { groupBy(btn.dataset.grouping); });
    });
    toArray(actions.querySelectorAll('[data-categories]')).forEach(function (btn) {
      btn.addEventListener('click', function () {
        (collapsible[wrap.dataset.grouping] || []).forEach(function (section) {
          section.open = btn.dataset.categories === 'expand';
        });
        state.save();
      });
    });
    // New visitors start in List; returning visitors resume their chosen view.
    groupBy(state.grouping);

    function apply(view) {
      wrap.dataset.view = view;
      buttons.forEach(function (btn) {
        btn.setAttribute('aria-pressed', String(btn.dataset.decks === view));
      });
      state.save();
    }

    apply(state.layout);
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () { apply(btn.dataset.decks); });
    });
  }

  /* ---- guide sections ----------------------------------------------------- */
  // Every titled guide section is a <details open>; these two buttons set them all.
  // No saved state: a guide is read top to bottom, so it always opens expanded.
  function initGuideSections() {
    toArray(document.querySelectorAll('[data-guide-sections]')).forEach(function (btn) {
      btn.addEventListener('click', function () {
        var open = btn.dataset.guideSections === 'expand';
        toArray(document.querySelectorAll('.guide details.gsec')).forEach(function (d) {
          d.open = open;
        });
      });
    });
  }

  /* ---- list / gallery toggle --------------------------------------------- */
  function initViewToggle(cards) {
    var buttons = toArray(document.querySelectorAll('.btn[data-view]'));
    if (!buttons.length) return;
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var view = btn.dataset.view;
        // The guide is its own article, not another layout of the card list, so
        // the toggle swaps which of the two is visible rather than only
        // restyling one. `hidden` is used per the harness note about [hidden].
        var guide = document.querySelector('.guide');
        if (guide) {
          guide.hidden = view !== 'guide';
          cards.hidden = view === 'guide';
        }
        if (view !== 'guide') cards.dataset.view = view;
        buttons.forEach(function (other) {
          other.setAttribute('aria-pressed', String(other === btn));
        });
        if (btn.dataset.view === 'gallery') fillGallery();
      });
    });
  }

  // Injected on first switch rather than at build time, so the list view — the
  // common case — downloads no images at all.
  //
  // srcset, not a plain src: the committed thumbnail is 146x204, and a grid cell
  // renders around 147-172 CSS px. On a 1x screen that is fine, but on a 2x one
  // the browser wants ~293 device px and has 146 — half the detail, which reads
  // as blurry. Offering both widths lets the browser pick per display, and
  // `loading=lazy` means only the cards actually scrolled into view download the
  // larger file. `sizes` has to describe the real rendered width or the choice
  // is made against the wrong number.
  function fillGallery() {
    toArray(document.querySelectorAll('.card[data-thumb]')).forEach(function (li) {
      if (li.querySelector('img.thumb')) return;          // convention 2
      var img = new Image(146, 204);                      // reserves layout space
      img.className = 'thumb';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.alt = li.dataset.name || '';
      img.sizes = '(max-width: 560px) 46vw, 172px';
      // At 2x the 172px tile needs 344px, so the browser picks the 488w
      // candidate — which lives on cards.scryfall.io. When that host is
      // unreachable the tile renders empty, because a failed srcset candidate
      // does NOT fall back to src on its own. Drop srcset and keep the local
      // thumbnail instead.
      img.onerror = function () {
        img.onerror = null;                                // never loop
        img.removeAttribute('srcset');                     // stop re-picking it
        img.src = li.dataset.thumb;
      };
      if (li.dataset.img) {
        img.srcset = li.dataset.thumb + ' 146w, ' + li.dataset.img + ' 488w';
      }
      img.src = li.dataset.thumb;                          // fallback + instant paint
      li.appendChild(img);
    });
  }

  /* ---- copy decklist ------------------------------------------------------ */
  function initCopy() {
    var button = document.querySelector('.btn[data-copy]');
    var source = document.querySelector('.rawlist');
    if (!button || !source) return;

    function flash() {
      var was = button.textContent;
      button.textContent = 'Copied';
      setTimeout(function () { button.textContent = was; }, 1400);
    }
    // execCommand is the fallback, not the preference: navigator.clipboard is
    // undefined on insecure origins, which includes opening docs/ over file://.
    function selectAndCopy() {
      source.removeAttribute('aria-hidden');
      source.select();
      try { document.execCommand('copy'); flash(); } catch (e) { /* copy by hand */ }
      source.setAttribute('aria-hidden', 'true');
    }
    button.addEventListener('click', function () {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(source.value).then(flash, selectAndCopy);
      } else {
        selectAndCopy();
      }
    });
  }

  /* ---- local times ------------------------------------------------------- */
  // The build writes creation times in UTC so its output is the same on every
  // machine; show each visitor their own clock instead.
  function initLocalTimes() {
    function pad(n) { return (n < 10 ? '0' : '') + n; }
    toArray(document.querySelectorAll('[data-ts]')).forEach(function (el) {
      var when = new Date(Number(el.dataset.ts) * 1000);
      if (isNaN(when.getTime())) return;
      el.textContent = when.getFullYear() + '-' + pad(when.getMonth() + 1) + '-'
        + pad(when.getDate()) + ' ' + pad(when.getHours()) + ':' + pad(when.getMinutes());
    });
  }

  /* ---- random deck -------------------------------------------------------- */
  // One button in the topbar of every page. It draws from the deck picker's own
  // options (already on every page, hrefs already relative to it, the current
  // deck excluded), copies that deck's list, then opens its page.
  //
  // The deck is drawn when the PAGE loads, and its list (a small .txt the build
  // writes beside every deck page) is fetched in the background. That way the
  // click can copy synchronously, exactly like Copy decklist does: a clipboard
  // write that starts after an await is refused by Safari, and on plain http
  // (the private catalog opened from another device on the network)
  // navigator.clipboard does not exist at all, leaving only execCommand, which
  // must run inside the click. If the list is not back yet when the click
  // lands, a promise-valued ClipboardItem tries to keep the click's permission
  // while the fetch finishes. When everything fails (file://, where fetch is
  // blocked) the deck page offers a one-click copy instead.
  function initRandomDeck() {
    var button = document.querySelector('[data-random]');
    var picker = document.querySelector('.deckpicker');
    if (!button || !picker) return;
    var choices = toArray(picker.options).filter(function (o) { return o.value && !o.selected; });
    if (!choices.length) return;
    var href = choices[Math.floor(Math.random() * choices.length)].value;
    var ready = null;
    var pending = fetch(href.replace(/\.html$/, '.txt')).then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.text();
    });
    pending.then(function (text) { ready = text; }, function () { /* handled at click */ });

    button.addEventListener('click', function () {
      button.disabled = true;
      button.classList.add('rolling');
      var copied = ready !== null ? copyNow(ready) : copyWhenReady(pending);
      copied.then(function () { return 'copied'; }, function () { return 'manual'; })
        .then(function (state) { location.href = href + '?random=' + state; });
    });
  }

  // Synchronous, inside the click: the async API where the page is a secure
  // context, otherwise the same execCommand fallback Copy decklist uses.
  function copyNow(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).catch(function () {
        if (!execCopy(text)) throw new Error('copy refused');
      });
    }
    return execCopy(text) ? Promise.resolve() : Promise.reject(new Error('copy refused'));
  }

  function execCopy(text) {
    var area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.top = '-1000px';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    area.setSelectionRange(0, text.length);           // iOS ignores select() alone
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    document.body.removeChild(area);
    return ok;
  }

  function copyWhenReady(textPromise) {
    function writeText(text) {
      if (!navigator.clipboard) throw new Error('clipboard unavailable');
      return navigator.clipboard.writeText(text);
    }
    if (window.ClipboardItem && navigator.clipboard && navigator.clipboard.write) {
      try {
        var item = new ClipboardItem({ 'text/plain': textPromise.then(function (text) {
          return new Blob([text], { type: 'text/plain' });
        }) });
        return navigator.clipboard.write([item]).catch(function () { return textPromise.then(writeText); });
      } catch (e) { /* a ClipboardItem that rejects promises: use the fallback */ }
    }
    return textPromise.then(writeText);
  }

  // On the page a Random click opened: say whether the list is on the clipboard,
  // then drop the query so a reload or a shared link is just the deck.
  function initRandomNotice() {
    var match = /[?&]random=(copied|manual)/.exec(location.search);
    var main = document.querySelector('main');
    if (!match || !main) return;
    var note = document.createElement('p');
    note.className = 'random-notice' + (match[1] === 'manual' ? ' manual' : '');
    note.setAttribute('role', 'status');
    if (match[1] === 'copied') {
      note.textContent = '🎲 Random pick: the decklist is on your clipboard, ready to paste.';
    } else {
      // The automatic copy was refused, but a click on this page is allowed to
      // copy, so offer that click right here instead of pointing elsewhere.
      note.appendChild(document.createTextNode('🎲 Random pick. The automatic copy was blocked here, so one more click: '));
      var copy = document.createElement('button');
      copy.type = 'button';
      copy.className = 'btn';
      copy.textContent = 'Copy decklist';
      copy.addEventListener('click', function () {
        var deckCopy = document.querySelector('.btn[data-copy]');
        if (deckCopy) deckCopy.click();
        note.className = 'random-notice';
        note.textContent = '🎲 Random pick: the decklist is on your clipboard, ready to paste.';
      });
      note.appendChild(copy);
    }
    // Under the deck's title and commander line, where the eye lands first.
    var sub = main.querySelector('.sub');
    main.insertBefore(note, sub ? sub.nextSibling : main.firstChild);
    try { history.replaceState(null, '', location.pathname + location.hash); } catch (e) { /* cosmetic */ }
  }

  /* ---- readable image, with a local fallback ------------------------------ */
  // data-img points at cards.scryfall.io, a different host from the page. Some
  // networks refuse that host outright (ERR_CONNECTION_REFUSED), and an <img>
  // whose src fails renders as an empty frame with no hint why. The committed
  // thumbnail is always on disk, so drop back to it: small and soft, but you
  // can still see which card it is.
  function localFallback(li) {
    if (li.dataset.thumb) return li.dataset.thumb;       // list and gallery rows
    var t = li.querySelector && li.querySelector('img.gthumb');
    return t ? t.getAttribute('src') : '';               // guide rows
  }
  function loadWithFallback(img, remote, fallback) {
    img.onerror = function () {
      img.onerror = null;               // one retry only — never loop on failure
      if (fallback && img.getAttribute('src') !== fallback) img.src = fallback;
    };
    img.src = remote;
  }

  /* ---- hover preview ------------------------------------------------------ */
  // Returns { hide } so the lightbox can dismiss it without sharing a variable.
  function initPreview(root, catalog) {
    // Touch taps should follow the deck link without downloading a popup.
    if (!window.matchMedia('(hover: hover)').matches) return { hide: function () {} };
    var GAP = 18;
    var selector = catalog ? '.tile[data-img]' : '.card[data-img]';
    var floater = document.createElement('img');
    floater.id = 'preview';
    floater.alt = '';
    if (catalog) floater.className = 'commander-preview';
    document.body.appendChild(floater);

    function place(ev) {
      var w = floater.offsetWidth || (catalog ? 360 : 244);
      var h = floater.offsetHeight || (catalog ? 502 : 340);
      var x = ev.clientX + GAP;
      if (x + w > window.innerWidth - 8) x = ev.clientX - w - GAP;   // flip side
      var y = Math.min(Math.max(8, ev.clientY - h / 2), window.innerHeight - h - 8);
      floater.style.left = Math.max(8, Math.min(x, window.innerWidth - w - 8)) + 'px';
      floater.style.top = Math.max(8, y) + 'px';
    }
    function hide() { floater.classList.remove('on'); }
    function hoverTarget(node) {
      if (!node || !node.closest) return null;
      // Keep metadata tooltips clear. Only names and the art trigger a catalog preview.
      if (catalog && !node.closest('.tile-name, .tile-cmd, .art')) return null;
      var li = node.closest(selector);
      return li && root.contains(li) ? li : null;
    }
    function show(li, ev) {
      if (!catalog && root.dataset.view === 'gallery') return;
      if (!li) return;
      floater.alt = li.dataset.name || '';
      if (floater.getAttribute('src') !== li.dataset.img) {
        loadWithFallback(floater, li.dataset.img, localFallback(li));
      }
      floater.classList.add('on');
      place(ev);
    }
    root.addEventListener('mouseover', function (ev) {
      show(hoverTarget(ev.target), ev);
    });
    root.addEventListener('mousemove', function (ev) {
      if (floater.classList.contains('on')) place(ev);
    });
    root.addEventListener('mouseout', function (ev) {
      if (hoverTarget(ev.relatedTarget) !== hoverTarget(ev.target)) hide();
    });
    root.addEventListener('focusin', function (ev) {
      var li = ev.target.closest(selector);
      if (!li) return;
      var rect = li.getBoundingClientRect();
      show(li, {clientX: rect.right, clientY: rect.top + rect.height / 2});
    });
    root.addEventListener('focusout', hide);
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') hide();
    });
    // A view/filter change or scrolling must not leave a detached card floating.
    document.addEventListener('click', hide);
    document.addEventListener('input', hide);
    document.addEventListener('change', hide);
    window.addEventListener('scroll', hide, true);
    window.addEventListener('resize', hide);

    return { hide: hide };
  }

  /* ---- lightbox ----------------------------------------------------------- */
  // Matches a card row in EITHER view. The guide is a sibling of `.cards`, not a
  // child of it, and its rows are `.gcard` — so a lightbox bound to `.cards` and
  // looking for `.card` saw neither the container nor the class, and clicking a
  // guide card did nothing at all.
  var ZOOMABLE = '.card[data-img], .gcard[data-img], .gpiece[data-img]';

  function initLightbox(root, preview) {
    var overlay = document.createElement('div');
    overlay.id = 'lightbox';
    overlay.innerHTML =
      '<div class="box"><img class="lightbox-img" alt="">' +
      '<button class="btn flip">Flip ↻</button></div>';
    document.body.appendChild(overlay);

    var full = overlay.querySelector('img.lightbox-img');   // convention 2
    var flip = overlay.querySelector('.flip');
    var faces = [];
    var face = 0;
    var fallback = '';

    function open(li) {
      faces = [li.dataset.img];
      if (li.dataset.back) faces.push(li.dataset.back);
      face = 0;
      fallback = localFallback(li);
      loadWithFallback(full, faces[0], fallback);
      full.alt = li.dataset.name || '';
      overlay.classList.toggle('two', faces.length > 1);
      overlay.classList.add('on');
      preview.hide();
    }
    function close() { overlay.classList.remove('on'); }

    root.addEventListener('click', function (ev) {
      var li = ev.target.closest(ZOOMABLE);
      if (li) open(li);
    });
    root.addEventListener('keydown', function (ev) {
      if (ev.key !== 'Enter' && ev.key !== ' ') return;
      var li = ev.target.closest(ZOOMABLE);
      if (li) { ev.preventDefault(); open(li); }
    });
    flip.addEventListener('click', function (ev) {
      ev.stopPropagation();                    // do not also close the overlay
      face = (face + 1) % faces.length;
      loadWithFallback(full, faces[face], fallback);
    });
    overlay.addEventListener('click', close);
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') close();
    });
  }

  /* ---- helpers ------------------------------------------------------------ */
  function toArray(nodeList) { return Array.prototype.slice.call(nodeList); }

  // Fold case AND punctuation, so "zurvoltron" finds Zur-Voltron and "urzas"
  // finds Urza's Saga. Same rule the Discord !deck matcher uses.
  function fold(s) { return (s || '').toLowerCase().replace(/[^a-z0-9]/g, ''); }

  /* ---- start --------------------------------------------------------------- */
  initDeckPicker();
  initLocalTimes();
  initRandomDeck();
  initRandomNotice();
  var catalogState = initCatalogState();
  var refreshSearch = initSearch(catalogState);
  initTooltips();
  initCatalogView(refreshSearch, catalogState);
  var decks = document.querySelector('.decks');
  if (decks) initPreview(decks, true);

  var cards = document.querySelector('.cards');
  if (!cards) return;                       // index page: nothing below applies

  initViewToggle(cards);
  initGuideSections();
  initCopy();
  // Hover preview stays bound to `.cards`: a guide card is already rendered at
  // 200px, so a floating copy of the same image adds nothing there. Zoom binds
  // to <main>, which contains both the list and the guide.
  initLightbox(document.querySelector('main') || cards, initPreview(cards));
})();
