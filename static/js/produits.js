document.addEventListener('DOMContentLoaded', function() {
    var filterButtons = document.querySelectorAll('.filter-btn');
    var productCards = document.querySelectorAll('.product-card');
    var jsEmptyState = document.getElementById('jsEmptyState');
    var selectedCategory = 'all';

    function applyFilters() {
        var matchesFound = 0;
        productCards.forEach(function(card) {
            var cardCategory = card.getAttribute('data-category');
            var matchesCategory = (selectedCategory === 'all' || cardCategory === selectedCategory);
            if (matchesCategory) {
                card.style.display = 'flex';
                matchesFound++;
            } else {
                card.style.display = 'none';
            }
        });
        if (matchesFound === 0 && productCards.length > 0) {
            jsEmptyState.style.display = 'block';
        } else {
            jsEmptyState.style.display = 'none';
        }
    }

    filterButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            filterButtons.forEach(function(btn) { btn.classList.remove('active'); });
            this.classList.add('active');
            selectedCategory = this.getAttribute('data-category');
            applyFilters();
        });
    });

    applyFilters();
});
