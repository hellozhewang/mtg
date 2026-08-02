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
  function initSearch() {
    var input = document.querySelector('.search');
    if (!input) return;
    var tiles = toArray(document.querySelectorAll('.tile'));
    var rows = toArray(document.querySelectorAll('.card'));
    var items = tiles.length ? tiles : rows;
    if (!items.length) return;

    items.forEach(function (el) {
      el.setAttribute('data-key', fold(el.dataset.search || el.dataset.name || ''));
    });

    var sections = toArray(document.querySelectorAll('main section'));
    var empty = document.createElement('p');
    empty.className = 'nomatch';
    (document.querySelector('main') || document.body).appendChild(empty);

    function apply() {
      var q = fold(input.value);
      var shown = 0;
      items.forEach(function (el) {
        var hit = !q || el.getAttribute('data-key').indexOf(q) !== -1;
        el.classList.toggle('is-filtered', !hit);
        if (hit) shown++;
      });
      // Hide a section once every child is gone, so the page does not turn into
      // a column of empty headings.
      sections.forEach(function (sec) {
        sec.classList.toggle('is-filtered',
          !sec.querySelector('.tile:not(.is-filtered), .card:not(.is-filtered)'));
      });
      empty.textContent = 'Nothing matches “' + input.value + '”.';
      empty.classList.toggle('on', Boolean(q) && !shown);
    }

    input.addEventListener('input', apply);
    // `/` focuses the box, Escape clears it — the two shortcuts people try.
    document.addEventListener('keydown', function (ev) {
      if (ev.key === '/' && document.activeElement !== input) {
        ev.preventDefault();
        input.focus();
        input.select();
      } else if (ev.key === 'Escape' && document.activeElement === input) {
        input.value = '';
        apply();
        input.blur();
      }
    });
  }

  /* ---- list / gallery toggle --------------------------------------------- */
  function initViewToggle(cards) {
    var buttons = toArray(document.querySelectorAll('.btn[data-view]'));
    if (!buttons.length) return;
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        cards.dataset.view = btn.dataset.view;
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

  /* ---- hover preview ------------------------------------------------------ */
  // Returns { hide } so the lightbox can dismiss it without sharing a variable.
  function initPreview(cards) {
    var GAP = 18;
    var floater = document.createElement('img');
    floater.id = 'preview';
    floater.alt = '';
    document.body.appendChild(floater);

    function place(ev) {
      var w = floater.offsetWidth || 244;
      var h = floater.offsetHeight || 340;
      var x = ev.clientX + GAP;
      if (x + w > window.innerWidth - 8) x = ev.clientX - w - GAP;   // flip side
      var y = Math.min(Math.max(8, ev.clientY - h / 2), window.innerHeight - h - 8);
      floater.style.left = x + 'px';
      floater.style.top = Math.max(8, y) + 'px';
    }
    function hide() { floater.classList.remove('on'); }

    cards.addEventListener('mouseover', function (ev) {
      if (cards.dataset.view === 'gallery') return;   // the image is already there
      var li = ev.target.closest('.card[data-img]');
      if (!li) return;
      if (floater.getAttribute('src') !== li.dataset.img) floater.src = li.dataset.img;
      floater.classList.add('on');
      place(ev);
    });
    cards.addEventListener('mousemove', function (ev) {
      if (floater.classList.contains('on')) place(ev);
    });
    cards.addEventListener('mouseout', function (ev) {
      var to = ev.relatedTarget;
      if (!to || !to.closest || !to.closest('.card[data-img]')) hide();
    });

    return { hide: hide };
  }

  /* ---- lightbox ----------------------------------------------------------- */
  function initLightbox(cards, preview) {
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

    function open(li) {
      faces = [li.dataset.img];
      if (li.dataset.back) faces.push(li.dataset.back);
      face = 0;
      full.src = faces[0];
      full.alt = li.dataset.name || '';
      overlay.classList.toggle('two', faces.length > 1);
      overlay.classList.add('on');
      preview.hide();
    }
    function close() { overlay.classList.remove('on'); }

    cards.addEventListener('click', function (ev) {
      var li = ev.target.closest('.card[data-img]');
      if (li) open(li);
    });
    cards.addEventListener('keydown', function (ev) {
      if (ev.key !== 'Enter' && ev.key !== ' ') return;
      var li = ev.target.closest('.card[data-img]');
      if (li) { ev.preventDefault(); open(li); }
    });
    flip.addEventListener('click', function (ev) {
      ev.stopPropagation();                    // do not also close the overlay
      face = (face + 1) % faces.length;
      full.src = faces[face];
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
  initSearch();

  var cards = document.querySelector('.cards');
  if (!cards) return;                       // index page: nothing below applies

  initViewToggle(cards);
  initCopy();
  initLightbox(cards, initPreview(cards));
})();
