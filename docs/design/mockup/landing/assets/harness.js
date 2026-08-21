/* ═══════════════════════════════════════════════════════════════════════════
 * Harness — 목업 비교 컨트롤 런타임
 *
 * 화면 하단에 플로팅 바를 띄운다. 두 가지를 조작한다.
 *   1) 시안 전환 — 여러 목업 파일 사이를 오간다
 *   2) 설정값 조절 — 세그먼트(택1) · 슬라이더(숫자) · 컬러. 값은 CSS 변수로 실시간 주입
 * 그리고 정한 값을 CSS/YAML 스니펫으로 내보낸다.
 *
 * 자족적이다 — 스타일을 스스로 주입하므로 목업이 어떤 CSS 를 쓰든 <script> 한 줄이면 붙는다.
 * 의존성 없음. 제품 UI 가 아니다 — 코드로 옮길 때 이 바는 따라가지 않는다.
 *
 * 사용법·옵션은 SKILL.md 와 references/api.md 참고.
 * ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  var CSS =
    '.hns{position:fixed;left:50%;transform:translateX(-50%);bottom:8px;z-index:2147483000;' +
    'display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:999px;' +
    'background:#12141A;color:#F2F4F8;font-size:11.5px;line-height:1;' +
    'font-family:system-ui,-apple-system,sans-serif;box-shadow:0 2px 12px rgba(0,0,0,.28);' +
    'max-width:calc(100vw - 24px);flex-wrap:wrap;justify-content:center}' +
    '.hns-t{opacity:.6;font-weight:600;white-space:nowrap;padding-left:4px}' +
    '.hns-seg{display:flex;gap:2px;background:rgba(255,255,255,.1);border-radius:999px;padding:2px}' +
    '.hns-seg button{font:inherit;color:inherit;background:none;border:0;cursor:pointer;' +
    'height:22px;padding:0 10px;border-radius:999px;opacity:.72;white-space:nowrap;' +
    'transition:background-color 100ms ease-out,opacity 100ms ease-out}' +
    '.hns-seg button:hover{opacity:1}' +
    '.hns-seg button.on{background:#F2F4F8;color:#12141A;opacity:1;font-weight:700}' +
    '.hns-div{width:1px;height:16px;background:rgba(255,255,255,.16);flex:none}' +
    '.hns-range{display:flex;align-items:center;gap:6px}' +
    '.hns-range input{width:96px;accent-color:#F2F4F8;cursor:pointer}' +
    '.hns-num{font-family:ui-monospace,Menlo,monospace;font-size:10.5px;min-width:38px;' +
    'text-align:right;opacity:.85;font-variant-numeric:tabular-nums}' +
    '.hns-color{display:flex;align-items:center;gap:6px}' +
    '.hns-color input{width:24px;height:22px;padding:0;border:0;background:none;cursor:pointer}' +
    '.hns-cr{font-family:ui-monospace,Menlo,monospace;font-size:10px;padding:2px 6px;' +
    'border-radius:999px;background:rgba(255,255,255,.12);white-space:nowrap}' +
    '.hns-cr.pass{background:rgba(80,200,140,.22)}' +
    '.hns-cr.fail{background:rgba(230,110,90,.26)}' +
    '.hns-btn{font:inherit;color:inherit;background:rgba(255,255,255,.12);border:0;cursor:pointer;' +
    'height:22px;padding:0 10px;border-radius:999px;white-space:nowrap;opacity:.85}' +
    '.hns-btn:hover{opacity:1;background:rgba(255,255,255,.2)}' +
    '.hns-out{position:fixed;left:50%;transform:translateX(-50%);bottom:44px;z-index:2147483000;' +
    'width:min(560px,calc(100vw - 32px));background:#12141A;color:#F2F4F8;border-radius:10px;' +
    'padding:10px;box-shadow:0 6px 24px rgba(0,0,0,.34);display:none}' +
    '.hns-out.on{display:block}' +
    '.hns-out textarea{width:100%;height:150px;background:#0B0D12;color:#D8DEE9;border:0;' +
    'border-radius:6px;padding:8px;font-family:ui-monospace,Menlo,monospace;font-size:11px;' +
    'line-height:1.5;resize:vertical}' +
    '.hns-out .hns-hint{opacity:.6;font-size:10.5px;margin:6px 2px 0;' +
    'font-family:system-ui,sans-serif}';

  /* ── 대비(WCAG) ─────────────────────────────────────────────────────────── */
  function toRgb(c) {
    c = String(c).trim();
    if (c.charAt(0) === '#') {
      var h = c.slice(1);
      if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
      return [0, 2, 4].map(function (i) { return parseInt(h.slice(i, i + 2), 16); });
    }
    var m = c.match(/-?[\d.]+/g);
    return m ? m.slice(0, 3).map(Number) : null;
  }
  function luminance(c) {
    var rgb = toRgb(c);
    if (!rgb) return null;
    var s = rgb.map(function (v) {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * s[0] + 0.7152 * s[1] + 0.0722 * s[2];
  }
  function contrast(a, b) {
    var la = luminance(a), lb = luminance(b);
    if (la === null || lb === null) return null;
    var hi = Math.max(la, lb), lo = Math.min(la, lb);
    return (hi + 0.05) / (lo + 0.05);
  }

  /* ── 프레임 판별 ────────────────────────────────────────────────────────
   * file:// 은 프레임마다 origin 이 null(불투명)이라 부모의 DOM 을 직접 만질 수 없다.
   * postMessage 는 통과하므로 전환 요청만 그 경로로 보낸다. */
  var embedded = window.parent !== window;

  function el(tag, cls, html) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }

  function Harness() {}

  Harness.mount = function (opts) {
    opts = opts || {};
    var variants = opts.variants || [];
    var controls = opts.controls || [];
    var target = opts.target || document.documentElement;
    var storeKey = 'hns:' + (location.pathname.split('/').pop() || 'mockup');

    if (!document.getElementById('hns-css')) {
      var st = el('style');
      st.id = 'hns-css';
      st.textContent = CSS;
      document.head.appendChild(st);
    }

    /* 저장된 값 복원 — file:// 에서 localStorage 가 막히는 경우가 있어 try 로 감싼다 */
    var saved = {};
    if (opts.persist) {
      try { saved = JSON.parse(localStorage.getItem(storeKey) || '{}'); } catch (e) { saved = {}; }
    }
    var state = {};
    controls.forEach(function (c) {
      state[c.name] = (saved[c.name] !== undefined) ? saved[c.name] : c.value;
    });
    function save() {
      if (!opts.persist) return;
      try { localStorage.setItem(storeKey, JSON.stringify(state)); } catch (e) { /* 무시 */ }
    }

    /* 값 하나를 화면에 반영한다.
     * apply 콜백 > cssVar 주입 > data-{name} 속성 순으로 우선. */
    function applyOne(c, v) {
      state[c.name] = v;
      if (typeof c.apply === 'function') c.apply(v, target);
      else if (c.cssVar) target.style.setProperty(c.cssVar, v + (c.unit || ''));
      else document.body.setAttribute('data-' + c.name, v);
    }

    var bar = el('div', 'hns');

    /* ── 시안 전환 ── */
    if (variants.length > 1) {
      bar.appendChild(el('span', 'hns-t', opts.variantLabel || '시안'));
      var vseg = el('div', 'hns-seg');
      variants.forEach(function (v) {
        var b = el('button', v.id === opts.current ? 'on' : '', v.label);
        b.addEventListener('click', function () {
          if (v.id === opts.current) return;
          // switch.html 안이면 부모가 프레임을 갈아끼운다(각 시안의 상태가 보존된다)
          if (embedded) parent.postMessage({ type: 'hns-switch', to: v.id }, '*');
          else location.href = v.file;
        });
        vseg.appendChild(b);
      });
      bar.appendChild(vseg);
    }

    /* ── 설정 컨트롤 ── */
    var crNodes = [];   // 대비 배지들 — 값이 바뀔 때마다 다시 계산
    controls.forEach(function (c) {
      if (variants.length > 1 || bar.children.length) bar.appendChild(el('div', 'hns-div'));
      bar.appendChild(el('span', 'hns-t', c.label));

      if (c.kind === 'range') {
        var wrap = el('div', 'hns-range');
        var inp = el('input');
        inp.type = 'range';
        inp.min = c.min; inp.max = c.max; inp.step = c.step || 1;
        inp.value = state[c.name];
        var num = el('span', 'hns-num', state[c.name] + (c.unit || ''));
        inp.addEventListener('input', function () {
          applyOne(c, +inp.value);
          num.textContent = inp.value + (c.unit || '');
          refreshContrast(); save();
        });
        wrap.appendChild(inp); wrap.appendChild(num);
        bar.appendChild(wrap);

      } else if (c.kind === 'color') {
        var cw = el('div', 'hns-color');
        var ci = el('input');
        ci.type = 'color';
        ci.value = state[c.name];
        var chex = el('span', 'hns-num', state[c.name]);
        cw.appendChild(ci); cw.appendChild(chex);
        if (c.contrastAgainst) {
          var badge = el('span', 'hns-cr', '—');
          cw.appendChild(badge);
          crNodes.push({ ctrl: c, node: badge });
        }
        ci.addEventListener('input', function () {
          applyOne(c, ci.value);
          chex.textContent = ci.value;
          refreshContrast(); save();
        });
        bar.appendChild(cw);

      } else { /* segment */
        var seg = el('div', 'hns-seg');
        (c.options || []).forEach(function (o) {
          var b = el('button', o.v === state[c.name] ? 'on' : '', o.label);
          b.addEventListener('click', function () {
            Array.prototype.forEach.call(seg.children, function (x) {
              x.classList.toggle('on', x === b);
            });
            applyOne(c, o.v);
            refreshContrast(); save();
          });
          seg.appendChild(b);
        });
        bar.appendChild(seg);
      }
    });

    /* ── 내보내기 ── */
    var out = null;
    if (opts.exportAs) {
      bar.appendChild(el('div', 'hns-div'));
      var xb = el('button', 'hns-btn', '값 내보내기');
      bar.appendChild(xb);

      out = el('div', 'hns-out');
      var ta = el('textarea');
      ta.setAttribute('readonly', 'readonly');
      out.appendChild(ta);
      out.appendChild(el('div', 'hns-hint',
        'file:// 은 secure context 가 아니라 클립보드 API 가 막힌다 — 전체 선택돼 있으니 ⌘C 로 복사한다.'));
      document.body.appendChild(out);

      xb.addEventListener('click', function () {
        var on = out.classList.toggle('on');
        if (!on) return;
        ta.value = serialize(opts.exportAs, controls, state);
        ta.focus(); ta.select();
      });
    }

    /* 대비 배지 갱신 — 컨트롤 값이든 CSS 변수든 지금 계산된 값을 그대로 읽는다 */
    function refreshContrast() {
      var cs = getComputedStyle(target);
      crNodes.forEach(function (x) {
        var fg = state[x.ctrl.name];
        var bg = cs.getPropertyValue(x.ctrl.contrastAgainst).trim() || x.ctrl.contrastAgainst;
        var r = contrast(fg, bg);
        if (r === null) { x.node.textContent = '—'; x.node.className = 'hns-cr'; return; }
        x.node.textContent = r.toFixed(2) + ':1 ' + (r >= 7 ? 'AAA' : r >= 4.5 ? 'AA' : '미달');
        x.node.className = 'hns-cr ' + (r >= 4.5 ? 'pass' : 'fail');
      });
    }

    // 초기값을 화면에 한 번 반영
    controls.forEach(function (c) { applyOne(c, state[c.name]); });
    refreshContrast();

    document.body.appendChild(bar);
    return { bar: bar, state: state, apply: applyOne };
  };

  /* 현재 값을 스니펫으로. cssVar 가 있는 컨트롤만 대상 — 그것들이 코드로 옮겨질 값이다. */
  function serialize(cfg, controls, state) {
    var vars = controls.filter(function (c) { return c.cssVar; });
    if (!vars.length) return '(cssVar 를 가진 컨트롤이 없다 — 내보낼 값이 없음)';

    if (cfg.format === 'yaml') {
      return vars.map(function (c) {
        return '  ' + c.cssVar.replace(/^--/, '') + ': "' + state[c.name] + (c.unit || '') + '"';
      }).join('\n');
    }
    var sel = cfg.selector || ':root';
    return sel + ' {\n' + vars.map(function (c) {
      return '  ' + c.cssVar + ': ' + state[c.name] + (c.unit || '') + ';';
    }).join('\n') + '\n}';
  }

  Harness.contrast = contrast;
  window.Harness = Harness;
})();
