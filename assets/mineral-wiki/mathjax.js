/* Arithmatex preserves the source before Markdown can interpret underscores. */
var mineralMathRoot = null;
var mineralMathQueue = Promise.resolve();

function renderMineralMath() {
  if (typeof window.MathJax.typesetPromise !== "function") return;
  mineralMathQueue = mineralMathQueue.then(function () {
    return window.MathJax.startup.promise;
  }).then(function () {
    var root = document.querySelector("article");
    if (!root || root === mineralMathRoot) return;
    if (mineralMathRoot) window.MathJax.typesetClear([mineralMathRoot]);
    mineralMathRoot = root;
    window.MathJax.texReset();
    return window.MathJax.typesetPromise([root]);
  }).catch(function (error) {
    console.error("No se pudieron mostrar las fórmulas.", error);
  });
}

window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex"
  },
  startup: {
    /* Render each article once, after the mobile layout is ready. Reprocessing
       MathJax's own assistive MathML would otherwise create nested output. */
    typeset: false,
    ready: function () {
      window.MathJax.startup.defaultReady();
      window.MathJax.startup.promise.then(renderMineralMath);
    }
  }
};

/* Also render pages loaded through Material's optional instant navigation. */
if (typeof document$ !== "undefined") {
  document$.subscribe(renderMineralMath);
}
