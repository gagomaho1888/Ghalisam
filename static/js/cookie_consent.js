document.addEventListener('DOMContentLoaded', function () {
    var consent = getCookie('cookie_consent');
    if (!consent) {
        var banner = document.getElementById('cookie-banner');
        if (banner) {
            banner.style.display = 'block';
        }
    }

    var acceptBtn = document.getElementById('cookie-accept');
    var rejectBtn = document.getElementById('cookie-reject');

    if (acceptBtn) {
        acceptBtn.addEventListener('click', function () {
            setConsent('accepted');
        });
    }

    if (rejectBtn) {
        rejectBtn.addEventListener('click', function () {
            setConsent('rejected');
        });
    }

    function setConsent(value) {
        setCookie('cookie_consent', value, 365);
        var banner = document.getElementById('cookie-banner');
        if (banner) {
            banner.style.display = 'none';
        }
        var xhr = new XMLHttpRequest();
        xhr.open('POST', '/cookie-consent/', true);
        xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
        xhr.setRequestHeader('X-CSRFToken', getCSRFToken());
        xhr.send('consent=' + value);
    }

    function getCookie(name) {
        var nameEQ = name + '=';
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var c = cookies[i].trim();
            if (c.indexOf(nameEQ) === 0) {
                return c.substring(nameEQ.length);
            }
        }
        return null;
    }

    function setCookie(name, value, days) {
        var expires = '';
        if (days) {
            var date = new Date();
            date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
            expires = '; expires=' + date.toUTCString();
        }
        document.cookie = name + '=' + value + expires + '; path=/; SameSite=Lax';
    }

    function getCSRFToken() {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var c = cookies[i].trim();
            if (c.indexOf('csrftoken=') === 0) {
                return c.substring('csrftoken='.length);
            }
        }
        return '';
    }
});
