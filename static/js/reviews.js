document.addEventListener('DOMContentLoaded', function () {
    /* ===== Interactive Star Rating ===== */
    const starInputs = document.querySelectorAll('.star-rating-input input');
    const starLabels = document.querySelectorAll('.star-rating-input label');

    starLabels.forEach(function (label) {
        label.addEventListener('mouseenter', function () {
            const value = this.getAttribute('data-value');
            highlightStars(value);
        });
    });

    const starContainer = document.querySelector('.star-rating-input');
    if (starContainer) {
        starContainer.addEventListener('mouseleave', function () {
            const checked = this.querySelector('input:checked');
            if (checked) {
                highlightStars(checked.value);
            } else {
                resetStars();
            }
        });
    }

    starInputs.forEach(function (input) {
        input.addEventListener('change', function () {
            highlightStars(this.value);
        });
    });

    function highlightStars(value) {
        starLabels.forEach(function (label) {
            var starValue = label.getAttribute('data-value');
            if (starValue <= value) {
                label.style.color = '#f59e0b';
            } else {
                label.style.color = '#cbd5e1';
            }
        });
    }

    function resetStars() {
        starLabels.forEach(function (label) {
            label.style.color = '#cbd5e1';
        });
    }

    /* ===== Image Upload Preview ===== */
    var imageInput = document.querySelector('.review-image-input');
    var imagePreview = document.querySelector('.review-image-preview');
    var fileNameDisplay = document.querySelector('.file-name');

    if (imageInput && imagePreview) {
        imageInput.addEventListener('change', function () {
            var file = this.files[0];
            if (file) {
                if (fileNameDisplay) {
                    fileNameDisplay.textContent = file.name;
                }
                var reader = new FileReader();
                reader.onload = function (e) {
                    imagePreview.src = e.target.result;
                    imagePreview.style.display = 'block';
                };
                reader.readAsDataURL(file);
            } else {
                if (fileNameDisplay) {
                    fileNameDisplay.textContent = '';
                }
                imagePreview.style.display = 'none';
            }
        });
    }

    /* ===== Distribution Bar Animation ===== */
    var distBars = document.querySelectorAll('.dist-bar-fill');
    if (distBars.length > 0) {
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    var target = entry.target;
                    var pct = target.getAttribute('data-pct');
                    if (pct) {
                        setTimeout(function () {
                            target.style.width = pct + '%';
                        }, 200);
                    }
                    observer.unobserve(target);
                }
            });
        }, { threshold: 0.3 });

        distBars.forEach(function (bar) {
            observer.observe(bar);
        });
    }

    /* ===== Load More Reviews ===== */
    var loadMoreBtn = document.querySelector('.load-more-btn');
    var reviewsList = document.querySelector('.reviews-list');

    if (loadMoreBtn && reviewsList) {
        loadMoreBtn.addEventListener('click', function () {
            var nextPage = this.getAttribute('data-next-page');
            var articleId = this.getAttribute('data-article-id');

            if (!nextPage || this.classList.contains('loading')) return;

            this.classList.add('loading');
            this.textContent = 'Chargement...';

            fetch('/api/produit/' + articleId + '/avis/?page=' + nextPage)
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    data.reviews.forEach(function (review) {
                        var card = createReviewCard(review);
                        reviewsList.insertAdjacentHTML('beforeend', card);
                    });

                    if (data.has_next) {
                        loadMoreBtn.setAttribute('data-next-page', data.next_page);
                        loadMoreBtn.textContent = 'Voir plus d\'avis';
                        loadMoreBtn.classList.remove('loading');
                    } else {
                        loadMoreBtn.style.display = 'none';
                    }
                })
                .catch(function () {
                    loadMoreBtn.textContent = 'Erreur de chargement';
                    loadMoreBtn.classList.remove('loading');
                });
        });
    }

    function createReviewCard(review) {
        var starsHtml = '';
        for (var i = 0; i < 5; i++) {
            starsHtml += i < review.rating ? '★' : '☆';
        }

        var verifiedBadge = '';
        if (review.achat_verifie) {
            verifiedBadge = '<span class="review-badge">✓ Achat vérifié</span>';
        }

        var imageHtml = '';
        if (review.image_url) {
            imageHtml = '<img src="' + escapeHtml(review.image_url) + '" alt="Photo avis" class="review-image-display" onclick="window.open(this.src)">';
        }

        var responseHtml = '';
        if (review.seller_response) {
            responseHtml = '<div class="seller-response"><strong>Réponse du vendeur</strong><p>' + escapeHtml(review.seller_response) + '</p></div>';
        }

        return '<div class="review-card">' +
            '<div class="review-card-header">' +
                '<div class="review-avatar">' + escapeHtml(review.user_initial) + '</div>' +
                '<div class="review-meta">' +
                    '<span class="review-user-name">' + escapeHtml(review.user_name) + verifiedBadge + '</span>' +
                    '<div><span class="review-stars">' + starsHtml + '</span><span class="review-date">' + escapeHtml(review.created_at) + '</span></div>' +
                '</div>' +
            '</div>' +
            '<p class="review-comment">' + escapeHtml(review.comment) + '</p>' +
            imageHtml +
            responseHtml +
        '</div>';
    }

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /* ===== Edit Review Toggle ===== */
    var editBtns = document.querySelectorAll('.edit-review-btn');
    editBtns.forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            var form = document.getElementById('edit-review-form-' + this.getAttribute('data-review-id'));
            if (form) {
                form.classList.toggle('active');
            }
        });
    });

    /* ===== Delete Confirmation ===== */
    var deleteBtns = document.querySelectorAll('.delete-review-btn');
    deleteBtns.forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            if (!confirm('Êtes-vous sûr de vouloir supprimer votre avis ?')) {
                e.preventDefault();
            }
        });
    });
});
