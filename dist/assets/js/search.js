// Reversing-Offline-Search-Web client-side search engine.
// Hand-written, no external libraries. Runs as a plain <script src> (no
// modules) so it works under file:// without CORS/module restrictions.
//
// Expects window.SEARCH_INDEX to already be defined (loaded via
// <script src="./assets/search-index.js"> before this file).
//
// Ranking priority (implemented as a single weighted scoring function,
// not literal separate passes):
//   1. exact title match
//   2. exact mnemonic / keyword / symptom_keywords match
//   3. heading match
//   4. alias match
//   5. body match
//   6. fuzzy / partial / n-gram match
"use strict";

var RevSearch = (function () {

  // ---------------------------------------------------------------
  // Tokenization / normalization helpers
  // ---------------------------------------------------------------

  function normalize(s) {
    if (!s) return "";
    return String(s).toLowerCase().replace(/\s+/g, " ").trim();
  }

  function tokenize(s) {
    var norm = normalize(s);
    if (!norm) return [];
    return norm.split(" ").filter(function (t) { return t.length > 0; });
  }

  // Generate n-grams of a normalized (whitespace-stripped) string. Used so
  // that Korean queries without exact word segmentation (e.g. "rsp 뭐임",
  // "함수 호출") still overlap with indexed text.
  function ngrams(s, n) {
    var compact = normalize(s).replace(/\s+/g, "");
    var out = [];
    if (compact.length < n) {
      if (compact.length > 0) out.push(compact);
      return out;
    }
    for (var i = 0; i <= compact.length - n; i++) {
      out.push(compact.substr(i, n));
    }
    return out;
  }

  function ngramSet(s) {
    var set = Object.create(null);
    var g2 = ngrams(s, 2);
    var g3 = ngrams(s, 3);
    for (var i = 0; i < g2.length; i++) set[g2[i]] = true;
    for (var j = 0; j < g3.length; j++) set[g3[j]] = true;
    return set;
  }

  function ngramOverlapCount(querySet, docSet) {
    var count = 0;
    for (var k in querySet) {
      if (docSet[k]) count++;
    }
    return count;
  }

  // ---------------------------------------------------------------
  // Index preparation: precompute normalized/lowercased fields once.
  // ---------------------------------------------------------------

  var prepared = null;

  function fieldArray(doc, key) {
    var v = doc[key];
    if (!v) return [];
    if (Array.isArray(v)) return v;
    return [v];
  }

  function prepareIndex(rawIndex) {
    return rawIndex.map(function (doc) {
      var titleNorm = normalize(doc.title);
      var headings = fieldArray(doc, "headings");
      var keywords = fieldArray(doc, "keywords");
      var aliases = fieldArray(doc, "aliases");
      var symptoms = fieldArray(doc, "symptom_keywords");
      var bodyNorm = normalize(doc.body_text || "");

      var keywordSetNorm = {};
      keywords.concat(symptoms).forEach(function (k) {
        keywordSetNorm[normalize(k)] = true;
      });
      var aliasSetNorm = {};
      aliases.forEach(function (a) {
        aliasSetNorm[normalize(a)] = true;
      });
      var headingsNorm = headings.map(normalize);

      // Combined text for fuzzy n-gram fallback (title/headings/aliases/
      // keywords weigh more than raw body, but we still include a slice of
      // body so full-text fuzzy matching remains possible).
      var fuzzyText = [
        doc.title || "",
        headings.join(" "),
        keywords.join(" "),
        aliases.join(" "),
        symptoms.join(" "),
        (doc.body_text || "").slice(0, 4000)
      ].join(" ");

      return {
        doc: doc,
        titleNorm: titleNorm,
        headings: headings,
        headingsNorm: headingsNorm,
        keywords: keywords,
        aliases: aliases,
        symptoms: symptoms,
        keywordSetNorm: keywordSetNorm,
        aliasSetNorm: aliasSetNorm,
        bodyNorm: bodyNorm,
        ngSet: ngramSet(fuzzyText)
      };
    });
  }

  function getPrepared() {
    if (prepared === null) {
      var raw = (typeof window !== "undefined" && window.SEARCH_INDEX) ? window.SEARCH_INDEX : [];
      prepared = prepareIndex(raw);
    }
    return prepared;
  }

  // ---------------------------------------------------------------
  // Scoring
  // ---------------------------------------------------------------

  var WEIGHTS = {
    TITLE_EXACT: 1000,
    TITLE_CONTAINS: 400,
    TITLE_TOKEN: 60,
    KEYWORD_EXACT: 320,
    KEYWORD_TOKEN: 140,
    HEADING_CONTAINS: 150,
    HEADING_TOKEN: 45,
    ALIAS_EXACT: 220,
    ALIAS_TOKEN: 90,
    BODY_CONTAINS: 80,
    BODY_TOKEN: 18,
    NGRAM: 4,
    STUCK_SYMPTOM_BOOST: 260
  };

  function scoreDoc(entry, query, queryNorm, queryTokens, queryNgSet, stuckMode) {
    var score = 0;
    var reasons = []; // {weight, label}

    // 1. exact / partial title match
    if (entry.titleNorm === queryNorm) {
      score += WEIGHTS.TITLE_EXACT;
      reasons.push({ w: WEIGHTS.TITLE_EXACT, label: "제목 완전 일치" });
    } else if (queryNorm.length > 0 && entry.titleNorm.indexOf(queryNorm) !== -1) {
      score += WEIGHTS.TITLE_CONTAINS;
      reasons.push({ w: WEIGHTS.TITLE_CONTAINS, label: "제목에 검색어 포함" });
    } else {
      var titleTokHits = 0;
      queryTokens.forEach(function (t) {
        if (entry.titleNorm.indexOf(t) !== -1) titleTokHits++;
      });
      if (titleTokHits > 0) {
        score += titleTokHits * WEIGHTS.TITLE_TOKEN;
        reasons.push({ w: titleTokHits * WEIGHTS.TITLE_TOKEN, label: "제목 단어 일치" });
      }
    }

    // 2. exact mnemonic / keyword / symptom match
    if (entry.keywordSetNorm[queryNorm]) {
      score += WEIGHTS.KEYWORD_EXACT;
      reasons.push({ w: WEIGHTS.KEYWORD_EXACT, label: "키워드 일치: " + query });
    }
    var kwTokHits = 0, kwTokMatch = null;
    queryTokens.forEach(function (t) {
      if (entry.keywordSetNorm[t]) { kwTokHits++; kwTokMatch = t; }
    });
    if (kwTokHits > 0) {
      score += kwTokHits * WEIGHTS.KEYWORD_TOKEN;
      reasons.push({ w: kwTokHits * WEIGHTS.KEYWORD_TOKEN, label: "키워드 일치: " + kwTokMatch });
    }
    if (stuckMode && kwTokHits === 0 && entry.symptoms.length > 0) {
      // In stuck mode, give symptom-heavy articles a boost even on fuzzy overlap.
      var symNorm = entry.symptoms.map(normalize).join(" ");
      var symOverlap = ngramOverlapCount(queryNgSet, ngramSet(symNorm));
      if (symOverlap > 0) {
        score += WEIGHTS.STUCK_SYMPTOM_BOOST * Math.min(1, symOverlap / 6);
        reasons.push({ w: WEIGHTS.STUCK_SYMPTOM_BOOST, label: "증상 검색 일치" });
      }
    }

    // 3. heading match
    var headingHitFull = entry.headingsNorm.some(function (h) {
      return queryNorm.length > 0 && h.indexOf(queryNorm) !== -1;
    });
    if (headingHitFull) {
      score += WEIGHTS.HEADING_CONTAINS;
      reasons.push({ w: WEIGHTS.HEADING_CONTAINS, label: "소제목 일치" });
    } else {
      var headTokHits = 0;
      queryTokens.forEach(function (t) {
        if (entry.headingsNorm.some(function (h) { return h.indexOf(t) !== -1; })) headTokHits++;
      });
      if (headTokHits > 0) {
        score += headTokHits * WEIGHTS.HEADING_TOKEN;
        reasons.push({ w: headTokHits * WEIGHTS.HEADING_TOKEN, label: "소제목 단어 일치" });
      }
    }

    // 4. alias match
    if (entry.aliasSetNorm[queryNorm]) {
      score += WEIGHTS.ALIAS_EXACT;
      reasons.push({ w: WEIGHTS.ALIAS_EXACT, label: "별칭 일치: " + query });
    }
    var aliasTokHits = 0, aliasTokMatch = null;
    queryTokens.forEach(function (t) {
      if (entry.aliasSetNorm[t]) { aliasTokHits++; aliasTokMatch = t; }
    });
    if (aliasTokHits > 0) {
      score += aliasTokHits * WEIGHTS.ALIAS_TOKEN;
      reasons.push({ w: aliasTokHits * WEIGHTS.ALIAS_TOKEN, label: "별칭 일치: " + aliasTokMatch });
    }

    // 5. body match
    if (queryNorm.length > 0 && entry.bodyNorm.indexOf(queryNorm) !== -1) {
      score += WEIGHTS.BODY_CONTAINS;
      reasons.push({ w: WEIGHTS.BODY_CONTAINS, label: "본문 일치" });
    } else {
      var bodyTokHits = 0;
      queryTokens.forEach(function (t) {
        if (entry.bodyNorm.indexOf(t) !== -1) bodyTokHits++;
      });
      if (bodyTokHits > 0) {
        score += bodyTokHits * WEIGHTS.BODY_TOKEN;
        reasons.push({ w: bodyTokHits * WEIGHTS.BODY_TOKEN, label: "본문 단어 일치" });
      }
    }

    // 6. fuzzy / partial n-gram match (fallback, lowest weight tier)
    var overlap = ngramOverlapCount(queryNgSet, entry.ngSet);
    if (overlap > 0) {
      var fuzzyScore = overlap * WEIGHTS.NGRAM;
      score += fuzzyScore;
      reasons.push({ w: fuzzyScore, label: "유사 검색어 일치" });
    }

    reasons.sort(function (a, b) { return b.w - a.w; });
    return { score: score, reason: reasons.length ? reasons[0].label : "" };
  }

  // ---------------------------------------------------------------
  // Snippet extraction + highlighting
  // ---------------------------------------------------------------

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function buildSnippet(doc, queryTokens, queryNorm) {
    var body = doc.body_text || "";
    if (!body) return "";
    var lower = body.toLowerCase();
    var idx = -1;
    if (queryNorm) idx = lower.indexOf(queryNorm);
    if (idx === -1) {
      for (var i = 0; i < queryTokens.length; i++) {
        idx = lower.indexOf(queryTokens[i]);
        if (idx !== -1) break;
      }
    }
    var start, end;
    if (idx === -1) {
      start = 0;
      end = Math.min(body.length, 160);
    } else {
      start = Math.max(0, idx - 60);
      end = Math.min(body.length, idx + 100);
    }
    var snippet = body.slice(start, end);
    if (start > 0) snippet = "…" + snippet;
    if (end < body.length) snippet = snippet + "…";

    var escaped = escapeHtml(snippet);
    var termsToHighlight = queryNorm ? [queryNorm].concat(queryTokens) : queryTokens;
    termsToHighlight = termsToHighlight.filter(function (t) { return t && t.length >= 1; });
    // Sort longest-first so multi-word query highlights before its sub-tokens.
    termsToHighlight.sort(function (a, b) { return b.length - a.length; });
    termsToHighlight.forEach(function (t) {
      if (!t) return;
      var re = new RegExp("(" + t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig");
      escaped = escaped.replace(re, "<mark>$1</mark>");
    });
    return escaped;
  }

  // ---------------------------------------------------------------
  // Public search function
  // ---------------------------------------------------------------

  function search(query, options) {
    options = options || {};
    var stuckMode = !!options.stuckMode;
    var limit = options.limit || 20;

    var queryNorm = normalize(query);
    var queryTokens = tokenize(query);
    if (!queryNorm) return [];
    var queryNgSet = ngramSet(query);

    var entries = getPrepared();
    var scored = entries.map(function (entry) {
      var r = scoreDoc(entry, query, queryNorm, queryTokens, queryNgSet, stuckMode);
      return { entry: entry, score: r.score, reason: r.reason };
    }).filter(function (r) { return r.score > 0; });

    scored.sort(function (a, b) { return b.score - a.score; });

    var top = scored.slice(0, limit);

    return top.map(function (r) {
      var doc = r.entry.doc;
      var related = (doc.related_ids || []).slice(0, 3).map(function (rid) {
        var match = entries.filter(function (e) { return e.doc.id === rid; })[0];
        if (!match) return null;
        return { id: rid, title: match.doc.title, url: match.doc.url };
      }).filter(Boolean);

      return {
        id: doc.id,
        title: doc.title,
        slug: doc.slug,
        url: doc.url,
        category: doc.category,
        difficulty: doc.difficulty,
        platform: doc.platform || [],
        format: doc.format || [],
        tools: doc.tools || [],
        score: r.score,
        reason: r.reason,
        snippet: buildSnippet(doc, queryTokens, queryNorm),
        related: related
      };
    });
  }

  function byCategory(category, limit) {
    limit = limit || 50;
    var entries = getPrepared();
    var matches = entries.filter(function (e) { return e.doc.category === category; });
    matches.sort(function (a, b) {
      return (a.doc.id || "").localeCompare(b.doc.id || "");
    });
    return matches.slice(0, limit).map(function (entry) {
      var doc = entry.doc;
      var related = (doc.related_ids || []).slice(0, 3).map(function (rid) {
        var match = entries.filter(function (e) { return e.doc.id === rid; })[0];
        if (!match) return null;
        return { id: rid, title: match.doc.title, url: match.doc.url };
      }).filter(Boolean);
      return {
        id: doc.id,
        title: doc.title,
        slug: doc.slug,
        url: doc.url,
        category: doc.category,
        difficulty: doc.difficulty,
        platform: doc.platform || [],
        format: doc.format || [],
        tools: doc.tools || [],
        score: 0,
        reason: "카테고리 일치: " + category,
        snippet: escapeHtml((doc.body_text || "").slice(0, 160)) + ((doc.body_text || "").length > 160 ? "…" : ""),
        related: related
      };
    });
  }

  return {
    search: search,
    byCategory: byCategory,
    _internal: { normalize: normalize, tokenize: tokenize, ngrams: ngrams, ngramSet: ngramSet }
  };
})();

// ---------------------------------------------------------------
// DOM wiring (index.html home page + optional article-page redirect box)
// ---------------------------------------------------------------
(function () {
  "use strict";

  function qs(sel, root) { return (root || document).querySelector(sel); }

  function difficultyLabel(d) {
    var map = { beginner: "입문", basic: "기초", intermediate: "중급" };
    return map[d] || d || "";
  }

  function renderResults(results, query) {
    var container = document.getElementById("search-results");
    if (!container) return;
    container.innerHTML = "";

    var meta = document.createElement("div");
    meta.className = "search-meta";
    meta.textContent = query
      ? ('"' + query + '" 검색 결과 ' + results.length + '건')
      : "";
    container.appendChild(meta);

    if (query && results.length === 0) {
      var empty = document.createElement("p");
      empty.textContent = "검색 결과가 없습니다. 다른 단어로 시도해보세요 (예: mnemonic 이름, 증상 표현 등).";
      container.appendChild(empty);
      return;
    }

    results.forEach(function (r) {
      var card = document.createElement("div");
      card.className = "result-card";

      var h3 = document.createElement("h3");
      var a = document.createElement("a");
      a.href = r.url;
      a.textContent = r.title;
      h3.appendChild(a);
      card.appendChild(h3);

      var tags = document.createElement("div");
      tags.className = "result-tags";
      [r.category, difficultyLabel(r.difficulty)].concat(r.platform, r.format, r.tools)
        .filter(Boolean)
        .forEach(function (t) {
          var span = document.createElement("span");
          span.className = "tag";
          span.textContent = t;
          tags.appendChild(span);
        });
      card.appendChild(tags);

      if (r.reason) {
        var reason = document.createElement("div");
        reason.className = "result-reason";
        reason.textContent = "왜 이 결과가 나왔나: " + r.reason;
        card.appendChild(reason);
      }

      if (r.snippet) {
        var snip = document.createElement("div");
        snip.className = "result-snippet";
        snip.innerHTML = r.snippet;
        card.appendChild(snip);
      }

      if (r.related && r.related.length) {
        var relWrap = document.createElement("div");
        relWrap.className = "result-related";
        relWrap.appendChild(document.createTextNode("관련 글: "));
        r.related.forEach(function (rel) {
          var relA = document.createElement("a");
          relA.href = rel.url;
          relA.textContent = rel.title;
          relWrap.appendChild(relA);
        });
        card.appendChild(relWrap);
      }

      container.appendChild(card);
    });
  }

  function runSearch(query) {
    var stuckBox = document.getElementById("stuck-mode");
    var stuckMode = stuckBox ? stuckBox.checked : false;
    var results = RevSearch.search(query, { stuckMode: stuckMode, limit: 30 });
    renderResults(results, query);
  }

  function runCategory(cat) {
    var results = RevSearch.byCategory(cat);
    var container = document.getElementById("search-results");
    if (!container) return;
    renderResults(results, "");
    var meta = container.querySelector(".search-meta");
    if (meta) meta.textContent = '카테고리 "' + cat + '" 글 ' + results.length + '건';
    if (results.length === 0) {
      var empty = document.createElement("p");
      empty.textContent = "이 카테고리에는 아직 작성된 글이 없습니다 (다음 단계에서 채워질 예정입니다).";
      container.appendChild(empty);
    }
  }

  function getQueryParam(name) {
    var params = new URLSearchParams(window.location.search);
    return params.get(name) || "";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("search-form");
    var input = document.getElementById("search-input");
    if (!form || !input) return;

    var stuckBox = document.getElementById("stuck-mode");
    if (stuckBox && getQueryParam("stuck") === "1") {
      stuckBox.checked = true;
    }

    var initialQ = getQueryParam("q");
    var initialCat = getQueryParam("cat");

    if (initialQ) {
      input.value = initialQ;
      runSearch(initialQ);
    } else if (initialCat) {
      runCategory(initialCat);
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      runSearch(input.value);
      var url = new URL(window.location.href);
      url.searchParams.set("q", input.value);
      url.searchParams.delete("cat");
      window.history.replaceState({}, "", url);
    });

    if (stuckBox) {
      stuckBox.addEventListener("change", function () {
        if (input.value) runSearch(input.value);
      });
    }
  });
})();
