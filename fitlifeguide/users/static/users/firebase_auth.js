import { initializeApp } from './vendor/firebase/firebase-app.js';
import {
    getAuth,
    isSignInWithEmailLink,
    signInWithEmailLink,
} from './vendor/firebase/firebase-auth.js';

function initFirebaseAuth() {
    const root = document.getElementById('auth-app');
    if (root) {
        const page = root.dataset.page;
        const callbackUrl = root.dataset.callbackUrl;
        const completeProfileUrl = root.dataset.completeUrl;
        const homeUrl = root.dataset.homeUrl;

        const errorBox = document.getElementById('auth-error');
        const statusBox = document.getElementById('auth-status');
        const backToLogin = document.getElementById('back-to-login');
        const profilePanel = document.getElementById('profile-panel');
        const profileEmail = document.getElementById('profile-email');
        const profileError = document.getElementById('profile-error');

        let auth = null;
        let currentUser = null;
        let handoffPoller = null;

        const config = (() => {
            const node = document.getElementById('firebase-config');
            if (!node) return {};
            try {
                return JSON.parse(node.textContent);
            } catch {
                return {};
            }
        })();

        function showError(message) {
            if (!errorBox) return;
            errorBox.textContent = message;
            errorBox.hidden = false;
        }

        function hideError() {
            if (!errorBox) return;
            errorBox.textContent = '';
            errorBox.hidden = true;
        }

        function setStatus(message) {
            if (statusBox) statusBox.textContent = message;
        }

        function csrfToken() {
            const input = document.querySelector('[name=csrfmiddlewaretoken]');
            return input ? input.value : '';
        }

        function friendlyFirebaseError(error) {
            const code = error && error.code ? error.code : '';
            if (code === 'auth/unauthorized-continue-uri') {
                return `This domain is not authorized in Firebase Auth. Add ${window.location.origin} under Authentication > Settings > Authorized domains.`;
            }
            if (code === 'auth/operation-not-allowed') {
                return 'Email link sign-in is not enabled. Turn on Email link in Firebase Authentication.';
            }
            if (code === 'auth/quota-exceeded') {
                return 'Too many links have been requested. Wait a few minutes and try again.';
            }
            if (code === 'auth/invalid-email') {
                return 'Enter a valid email address.';
            }
            if (code === 'auth/network-request-failed') {
                return 'Could not reach Firebase. Check your connection and try again.';
            }
            return (error && error.message) || 'Something went wrong. Please try again.';
        }

        function clearFieldErrors() {
            document.querySelectorAll('[data-error-for]').forEach((node) => {
                node.textContent = '';
            });
        }

        function renderFieldErrors(errors) {
            clearFieldErrors();
            Object.entries(errors || {}).forEach(([field, entries]) => {
                const target = document.querySelector(`[data-error-for="${field}"]`);
                if (!target) return;
                target.textContent = entries.map((entry) => entry.message).join(' ');
            });
        }

        function showProfileError(message) {
            if (!profileError) return;
            profileError.textContent = message;
            profileError.hidden = false;
        }

        function hideProfileError() {
            if (!profileError) return;
            profileError.textContent = '';
            profileError.hidden = true;
        }

        if (!config.apiKey || !config.authDomain || !config.appId) {
            showError('Firebase Auth is not configured. Add FIREBASE_API_KEY, FIREBASE_AUTH_DOMAIN, and FIREBASE_APP_ID to .env.');
            return;
        }

        if (!callbackUrl || !completeProfileUrl) {
            showError('Sign-in is not configured correctly. Reload the page and try again.');
            return;
        }

        try {
            auth = getAuth(initializeApp(config));
        } catch (error) {
            showError(friendlyFirebaseError(error));
            return;
        }

        if (page === 'login') {
            const form = document.getElementById('email-link-form');
            const button = document.getElementById('send-link-button');
            const sentBox = document.getElementById('link-sent');
            const sentEmail = document.getElementById('sent-email');
            const sendAgain = document.getElementById('send-again');

            if (form && button && sentBox) {
                form.addEventListener('submit', async (event) => {
                    event.preventDefault();
                    hideError();

                    const emailInput = form.querySelector('input[type="email"]');
                    const email = emailInput ? emailInput.value.trim() : '';
                    if (!email) {
                        showError('Enter your email address.');
                        return;
                    }

                    const originalLabel = button.textContent;
                    button.disabled = true;
                    button.textContent = 'Sending link...';

                    try {
                        const response = await fetch(root.dataset.sendUrl, {
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': csrfToken(),
                            },
                            body: JSON.stringify({ email }),
                        });
                        const data = await response.json().catch(() => ({}));
                        if (!response.ok) {
                            throw new Error(data.message || 'Could not send the link. Please try again.');
                        }
                        try {
                            localStorage.setItem('emailForSignIn', email);
                            if (data.rid) localStorage.setItem('emailForSignInRid', data.rid);
                        } catch {
                            // The link can still be completed by confirming the email.
                        }
                        if (sentEmail) sentEmail.textContent = email;
                        form.hidden = true;
                        sentBox.hidden = false;
                        setStatus('Check your email for the sign-in link.');
                        if (data.rid) {
                            startHandoffPolling(data.rid);
                        }
                    } catch (error) {
                        showError(friendlyFirebaseError(error));
                        button.disabled = false;
                        button.textContent = originalLabel;
                    }
                });
            }

            function startHandoffPolling(rid) {
                const statusUrl = root.dataset.linkStatusUrl;
                const handoffUrl = root.dataset.handoffUrl;
                if (!statusUrl || !handoffUrl) return;
                if (handoffPoller) clearInterval(handoffPoller);

                const startedAt = Date.now();
                handoffPoller = setInterval(async () => {
                    if (Date.now() - startedAt > 15 * 60 * 1000) {
                        clearInterval(handoffPoller);
                        return;
                    }
                    let data = {};
                    try {
                        const response = await fetch(
                            `${statusUrl}?rid=${encodeURIComponent(rid)}`,
                            { credentials: 'same-origin' },
                        );
                        data = await response.json().catch(() => ({}));
                    } catch {
                        return;
                    }
                    if (data.status === 'invalid') {
                        clearInterval(handoffPoller);
                        return;
                    }
                    if (data.status !== 'ready') return;

                    clearInterval(handoffPoller);
                    setStatus('Sign-in detected. Opening the app...');
                    try {
                        const response = await fetch(handoffUrl, {
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': csrfToken(),
                            },
                            body: JSON.stringify({ token: data.token }),
                        });
                        const result = await response.json().catch(() => ({}));
                        if (response.ok && result.status === 'ok') {
                            window.location.assign(result.redirect || homeUrl);
                            return;
                        }
                        if (result.status === 'needs_profile') {
                            setStatus('Almost done — finish creating your account where you opened the link, then reload this page.');
                            return;
                        }
                        showError(result.message || 'Could not finish signing in here. Please request a new link.');
                    } catch {
                        showError('Could not finish signing in here. Please request a new link.');
                    }
                }, 3000);
            }

            if (sendAgain) {
                sendAgain.addEventListener('click', () => {
                    sentBox.hidden = true;
                    form.hidden = false;
                    button.disabled = false;
                    button.textContent = button.dataset.buttonLabel || 'Email me a sign-in link';
                    hideError();
                    const emailInput = form.querySelector('input[type="email"]');
                    if (emailInput) emailInput.focus();
                });
            }
        }

        if (page === 'callback') {
            const confirmForm = document.getElementById('confirm-email-form');
            const profileForm = document.getElementById('complete-profile-form');
            const profileButton = document.getElementById('complete-profile-button');

            async function finishSignIn(email) {
                hideError();
                setStatus('Verifying your sign-in link...');
                if (backToLogin) backToLogin.hidden = true;

                try {
                    const result = await signInWithEmailLink(auth, email, window.location.href);
                    try {
                        localStorage.removeItem('emailForSignIn');
                        localStorage.removeItem('emailForSignInRid');
                    } catch {
                        // Ignore storage failures.
                    }

                    // Tokens minted at sign-in can carry stale email_verified claims;
                    // refresh the record and force-mint so the server sees current state.
                    await result.user.reload();
                    const idToken = await result.user.getIdToken(true);
                    const response = await fetch(callbackUrl, {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken(),
                        },
                        body: JSON.stringify({
                            idToken,
                            rid: new URLSearchParams(window.location.search).get('rid') || '',
                        }),
                    });
                    const data = await response.json().catch(() => ({}));

                    if (response.ok && data.status === 'ok') {
                        window.location.assign(data.redirect || homeUrl);
                        return;
                    }

                    if (response.ok && data.status === 'needs_profile') {
                        currentUser = result.user;
                        if (profileEmail) profileEmail.textContent = data.email || result.user.email || email;
                        if (profilePanel) profilePanel.hidden = false;
                        setStatus('Email verified. Finish your profile to continue.');
                        if (profileForm) {
                            const username = profileForm.querySelector('input[name="username"]');
                            if (username) username.focus();
                        }
                        return;
                    }

                    throw new Error(data.message || 'Could not complete sign-in.');
                } catch (error) {
                    showError(friendlyFirebaseError(error));
                    setStatus('');
                    if (backToLogin) backToLogin.hidden = false;
                }
            }

            if (!isSignInWithEmailLink(auth, window.location.href)) {
                setStatus('This page is only for sign-in links.');
                showError('Open the link from your email to continue.');
                if (backToLogin) backToLogin.hidden = false;
            } else {
                let savedEmail = '';
                try {
                    savedEmail = localStorage.getItem('emailForSignIn') || '';
                } catch {
                    savedEmail = '';
                }

                if (savedEmail) {
                    finishSignIn(savedEmail);
                } else {
                    setStatus('Confirm the email address that received the link.');
                    if (confirmForm) confirmForm.hidden = false;
                }
            }

            if (confirmForm) {
                confirmForm.addEventListener('submit', (event) => {
                    event.preventDefault();
                    const emailInput = document.getElementById('confirm-email');
                    const email = emailInput ? emailInput.value.trim() : '';
                    if (!email) {
                        showError('Enter your email address.');
                        return;
                    }
                    confirmForm.hidden = true;
                    finishSignIn(email);
                });
            }

            if (profileForm && profileButton) {
                profileForm.addEventListener('submit', async (event) => {
                    event.preventDefault();
                    hideError();
                    hideProfileError();
                    clearFieldErrors();

                    if (!currentUser) {
                        showProfileError('Verify your email link again before continuing.');
                        return;
                    }

                    const originalLabel = profileButton.textContent;
                    profileButton.disabled = true;
                    profileButton.textContent = 'Creating account...';

                    const payload = {};
                    new FormData(profileForm).forEach((value, key) => {
                        if (key !== 'csrfmiddlewaretoken') payload[key] = value;
                    });

                    try {
                        payload.idToken = await currentUser.getIdToken();
                        const response = await fetch(completeProfileUrl, {
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': csrfToken(),
                            },
                            body: JSON.stringify(payload),
                        });
                        const data = await response.json().catch(() => ({}));

                        if (response.ok && data.status === 'ok') {
                            window.location.assign(data.redirect || homeUrl);
                            return;
                        }

                        if (data.status === 'invalid') {
                            renderFieldErrors(data.errors);
                            showProfileError('Check the highlighted fields and try again.');
                        } else {
                            showProfileError(data.message || 'Could not create your account.');
                        }
                    } catch (error) {
                        showProfileError(friendlyFirebaseError(error));
                    } finally {
                        profileButton.disabled = false;
                        profileButton.textContent = originalLabel;
                    }
                });
            }
        }

        window.__firebaseAuthReady = true;
    }
}

initFirebaseAuth();