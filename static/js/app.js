document.addEventListener("DOMContentLoaded", () => {
  if (window.jQuery && window.jQuery.fn && window.jQuery.fn.select2) {
    window.jQuery(".select2-no-search").select2({ minimumResultsForSearch: Infinity, width: "resolve" });
  }
});
