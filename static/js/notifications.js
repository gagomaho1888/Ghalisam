function getCSRFToken() {
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input) return input.value;
    var cookies = document.cookie.split(';');
    for (var i = 0; i < cookies.length; i++) {
        var c = cookies[i].trim();
        if (c.indexOf('csrftoken=') === 0) return c.substring(10);
    }
    return '';
}

var notifToast = document.getElementById('notificationToast');
var notifBadge = document.getElementById('notifBadge');

function fermerToast() { if (notifToast) notifToast.style.display = 'none'; }

// ---- Synthèse vocale ----
var voiceQueue = [];
var speaking = false;
var audioCtx = null;
var audioReady = false;
var pendingVoice = null;

function initAudio() {
    if (!audioCtx) {
        try {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        } catch(e) {}
    }
    if (audioCtx) {
        if (audioCtx.state === 'suspended') {
            audioCtx.resume().then(function() {
                audioReady = true;
                if (pendingVoice) {
                    direTexte(pendingVoice);
                    pendingVoice = null;
                }
            }).catch(function(){});
        } else if (audioCtx.state === 'running') {
            audioReady = true;
            if (pendingVoice) {
                direTexte(pendingVoice);
                pendingVoice = null;
            }
        }
    }
    if (window.speechSynthesis) {
        window.speechSynthesis.getVoices();
    }
}

document.addEventListener('click', initAudio);
document.addEventListener('touchstart', initAudio);

function jouerSonBip() {
    initAudio();
    if (!audioReady) return;
    try {
        var osc = audioCtx.createOscillator();
        var gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.frequency.value = 800;
        osc.type = 'sine';
        gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.15);
        osc.start(audioCtx.currentTime);
        osc.stop(audioCtx.currentTime + 0.15);
    } catch(e) {
        console.log('Bip:', e.message);
    }
}

function direTexte(texte) {
    if (!window.speechSynthesis) return;
    voiceQueue.push(texte);
    if (!speaking) jouerMessageSuivant();
}

function jouerMessageSuivant() {
    if (voiceQueue.length === 0) {
        speaking = false;
        return;
    }
    speaking = true;
    var texte = voiceQueue.shift();
    window.speechSynthesis.cancel();
    var utterance = new SpeechSynthesisUtterance(texte);
    utterance.lang = 'fr-FR';
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;

    var voix = window.speechSynthesis.getVoices();
    var voixFr = voix.find(function(v) {
        return v.lang.startsWith('fr');
    });
    if (voixFr) utterance.voice = voixFr;

    utterance.onend = function() { jouerMessageSuivant(); };
    utterance.onerror = function(e) { console.log('Erreur voix:', e.error); jouerMessageSuivant(); };
    window.speechSynthesis.speak(utterance);
}

if (window.speechSynthesis) {
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = function() {
        window.speechSynthesis.getVoices();
    };
}

function annoncerCommande(data) {
    jouerSonBip();
    var prenom = data.livreur_name || 'livreur';
    var messages = [
        'Vous avez une nouvelle commande, Monsieur ' + prenom + '.',
        'Bonjour Monsieur ' + prenom + ', une nouvelle livraison vous attend.',
        'Attention, une nouvelle commande vient de vous être attribuée.'
    ];
    var msg = messages[Math.floor(Math.random() * messages.length)];
    console.log('Annonce vocale :', msg);
    if (audioReady) {
        setTimeout(function() { direTexte(msg); }, 400);
    } else {
        pendingVoice = msg;
        console.log('Audio pas encore prêt — voix jouée au prochain clic.');
    }
}

// ---- Fin synthèse vocale ----

function afficherNotification(data) {
    console.log('Notification reçue :', data);
    if (notifBadge) {
        notifBadge.style.display = 'inline';
        notifBadge.textContent = parseInt(notifBadge.textContent || 0) + 1;
    }
    if (notifToast) {
        var t = notifToast.querySelector('.toast-text');
        if (t) {
            t.querySelector('strong').textContent = 'Nouvelle commande ' + data.ticket;
            t.querySelector('span').textContent = data.client + ' - ' + data.montant + ' FCFA';
        }
        notifToast.style.display = 'flex';
        notifToast.onclick = function() {
            initAudio();
            if (pendingVoice) {
                direTexte(pendingVoice);
                pendingVoice = null;
            }
        };
        setTimeout(fermerToast, 8000);
    }
    if (typeof ajouterLigneCommande === 'function') {
        ajouterLigneCommande(data);
    }
    annoncerCommande(data);
}

var wsRetryDelay = 1000;
var wsMaxDelay = 30000;

function connecterWS() {
    var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    var url = protocol + '//' + window.location.host + '/ws/notifications/';
    var socket = new WebSocket(url);
    socket.onopen = function() {
        console.log('WS connectée');
        wsRetryDelay = 1000;
    };
    socket.onmessage = function(e) {
        try {
            var data = JSON.parse(e.data);
            if (data.type === 'nouvelle_commande') afficherNotification(data);
        } catch(err) { console.error('Erreur WS:', err); }
    };
    socket.onclose = function() {
        setTimeout(function() {
            wsRetryDelay = Math.min(wsRetryDelay * 2, wsMaxDelay);
            connecterWS();
        }, wsRetryDelay);
    };
    socket.onerror = function(e) { console.error('WS erreur:', e); };
    return socket;
}

var ws = connecterWS();

function mettreAJourBadge() {
    if (!notifBadge) return;
    fetch('/api/notifications/non-lues/')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            notifBadge.style.display = data.non_lues > 0 ? 'inline' : 'none';
            if (data.non_lues > 0) notifBadge.textContent = data.non_lues;
        })
        .catch(function() {});
}

mettreAJourBadge();
setInterval(mettreAJourBadge, 30000);
