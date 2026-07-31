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
 */
(function () {
  'use strict';

  // The deck menu is on every page, not just the index, because a deck page is
  // the thing people share and landing on one should not be a dead end.
  var picker = document.querySelector('.deckpicker');
  if (picker) {
    picker.addEventListener('change', function () {
      if (picker.value) location.href = picker.value;
    });
  }

  /* ---- search / filter ------------------------------------------------- */
  // One box, two jobs: on the index it filters deck tiles, on a deck page it
  // filters card rows. Both work the same way, so the code is shared -- the only
  // difference is which elements carry the searchable text.
  //
  // `searchBox`, not `box`: the lightbox below also wanted `box`, and since both
  // are `var` in the same function scope the lightbox silently reassigned it.
  // The filter then read `.value` off a <div> and got undefined, so every query
  // looked empty and nothing was ever hidden -- on deck pages only, because the
  // index returns before the lightbox code runs.
  var searchBox = document.querySelector('.search');
  if (searchBox) (function () {
    var tiles = [].slice.call(document.querySelectorAll('.tile'));
    var rows = [].slice.call(document.querySelectorAll('.card'));
    var items = tiles.length ? tiles : rows;
    if (!items.length) return;

    // Fold case AND punctuation, so "zurvoltron" finds Zur-Voltron and "urzas"
    // finds Urza's Saga. Same rule the Discord !deck matcher uses.
    function norm(s) { return (s || '').toLowerCase().replace(/[^a-z0-9]/g, ''); }
    items.forEach(function (el) {
      el._key = norm(el.dataset.search || el.dataset.name || el.textContent);
    });

    // Sections wrap the items; hide one once all its children are filtered out
    // rather than leaving a column of empty headings.
    var sections = [].slice.call(document.querySelectorAll('main section'));
    var empty = document.createElement('p');
    empty.className = 'nomatch';
    (document.querySelector('main') || document.body).appendChild(empty);

    function apply() {
      var q = norm(searchBox.value);
      var shown = 0;
      items.forEach(function (el) {
        var hit = !q || el._key.indexOf(q) !== -1;
        el.classList.toggle('is-filtered', !hit);
        if (hit) shown++;
      });
      sections.forEach(function (sec) {
        var any = sec.querySelector('.tile:not(.is-filtered), .card:not(.is-filtered)');
        sec.classList.toggle('is-filtered', !any);
      });
      empty.textContent = 'Nothing matches \u201c' + searchBox.value + '\u201d.';
      empty.classList.toggle('on', q && !shown);
    }

    searchBox.addEventListener('input', apply);
    // `/` focuses the searchBox, Escape clears it -- the two shortcuts people try.
    document.addEventListener('keydown', function (ev) {
      if (ev.key === '/' && document.activeElement !== searchBox) {
        ev.preventDefault(); searchBox.focus(); searchBox.select();
      } else if (ev.key === 'Escape' && document.activeElement === searchBox) {
        searchBox.value = ''; apply(); searchBox.blur();
      }
    });
  })();

  var cards = document.querySelector('.cards');
  if (!cards) return;                       // index page: nothing below applies

  /* ---- view toggle ---------------------------------------------------- */
  // Gallery images are injected on first switch rather than at build time, so
  // the list view — the common case — downloads no images at all.
  var toggles = document.querySelectorAll('.btn[data-view]');
  Array.prototype.forEach.call(toggles, function (btn) {
    btn.addEventListener('click', function () {
      cards.dataset.view = btn.dataset.view;
      Array.prototype.forEach.call(toggles, function (b) {
        b.setAttribute('aria-pressed', String(b === btn));
      });
      if (btn.dataset.view === 'gallery') fillGallery();
    });
  });

  function fillGallery() {
    var list = document.querySelectorAll('.card[data-thumb]');
    Array.prototype.forEach.call(list, function (li) {
      // `img.thumb`, NOT any <img>: a card row already contains one <img> per
      // mana symbol in its cost, so a bare `querySelector('img')` matched those
      // and the guard skipped every card that costs mana. The only cards that
      // rendered were transforming double-faced ones, which carry no top-level
      // mana cost and so had no symbol to trip over.
      if (li.querySelector('img.thumb')) return;
      var img = new Image(146, 204);        // intrinsic size => no layout shift
      img.className = 'thumb';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.alt = li.dataset.name || '';
      img.src = li.dataset.thumb;
      li.appendChild(img);
    });
  }

  /* ---- copy decklist -------------------------------------------------- */
  var copyBtn = document.querySelector('.btn[data-copy]');
  var raw = document.querySelector('.rawlist');
  if (copyBtn && raw) {
    copyBtn.addEventListener('click', function () {
      function done() {
        var was = copyBtn.textContent;
        copyBtn.textContent = 'Copied';
        setTimeout(function () { copyBtn.textContent = was; }, 1400);
      }
      // execCommand is the fallback, not the preference: navigator.clipboard is
      // undefined on insecure origins, which includes opening docs/ over file://.
      function selectAndCopy() {
        raw.removeAttribute('aria-hidden');
        raw.select();
        try { document.execCommand('copy'); done(); } catch (e) { /* copy by hand */ }
        raw.setAttribute('aria-hidden', 'true');
      }
      if (navigator.clipboard) {
        navigator.clipboard.writeText(raw.value).then(done, selectAndCopy);
      } else {
        selectAndCopy();
      }
    });
  }

  /* ---- hover preview --------------------------------------------------- */
  var preview = document.createElement('img');
  preview.id = 'preview';
  preview.alt = '';
  document.body.appendChild(preview);

  var GAP = 18;
  function place(ev) {
    var w = preview.offsetWidth || 244;
    var h = preview.offsetHeight || 340;
    var x = ev.clientX + GAP;
    if (x + w > window.innerWidth - 8) x = ev.clientX - w - GAP;   // flip side
    var y = Math.min(Math.max(8, ev.clientY - h / 2), window.innerHeight - h - 8);
    preview.style.left = x + 'px';
    preview.style.top = Math.max(8, y) + 'px';
  }

  cards.addEventListener('mouseover', function (ev) {
    if (cards.dataset.view === 'gallery') return;      // the image is already there
    var li = ev.target.closest('.card[data-img]');
    if (!li) return;
    if (preview.getAttribute('src') !== li.dataset.img) preview.src = li.dataset.img;
    preview.classList.add('on');
    place(ev);
  });
  cards.addEventListener('mousemove', function (ev) {
    if (preview.classList.contains('on')) place(ev);
  });
  cards.addEventListener('mouseout', function (ev) {
    var to = ev.relatedTarget;
    if (!to || !to.closest || !to.closest('.card[data-img]')) {
      preview.classList.remove('on');
    }
  });

  /* ---- lightbox -------------------------------------------------------- */
  var box = document.createElement('div');
  box.id = 'lightbox';
  box.innerHTML =
    '<div class="box"><img alt=""><button class="btn flip">Flip &#8635;</button></div>';
  document.body.appendChild(box);
  var big = box.querySelector('img');
  var flip = box.querySelector('.flip');
  var sides = [];
  var side = 0;

  function open(li) {
    sides = [li.dataset.img];
    if (li.dataset.back) sides.push(li.dataset.back);
    side = 0;
    big.src = sides[0];
    big.alt = li.dataset.name || '';
    box.classList.toggle('two', sides.length > 1);
    box.classList.add('on');
    preview.classList.remove('on');
  }
  function close() { box.classList.remove('on'); }

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
    ev.stopPropagation();                        // do not also close the box
    side = (side + 1) % sides.length;
    big.src = sides[side];
  });
  box.addEventListener('click', close);
  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape') close();
  });
})();
