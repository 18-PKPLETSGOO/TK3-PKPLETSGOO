document.addEventListener('DOMContentLoaded', function () {
  var input = document.getElementById('candidateSearch');
  var clearBtn = document.getElementById('clearSearch');
  var noResult = document.getElementById('noSearchResult');

  if (!input) return;

  input.addEventListener('input', filterCandidates);
  clearBtn.addEventListener('click', function () {
    input.value = '';
    filterCandidates();
    input.focus();
  });

  function filterCandidates() {
    var query = input.value.trim().toLowerCase();
    var items = document.querySelectorAll('.candidate-item');
    var visibleCount = 0;

    clearBtn.style.display = query ? 'inline-block' : 'none';

    items.forEach(function (item) {
      var text = item.textContent.toLowerCase();
      var match = text.includes(query);
      item.style.display = match ? '' : 'none';
      if (match) visibleCount++;
    });

    noResult.style.display = (query && visibleCount === 0) ? '' : 'none';
  }
});
