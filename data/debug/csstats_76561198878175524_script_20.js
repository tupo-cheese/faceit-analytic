
        stats_loading = false;
        stats_pending = false;

        // Confirm before leaving while the request is in flight
        window.addEventListener("beforeunload", function (e) {
            if (!stats_pending) {
                return undefined;
            }

            e.preventDefault();
            e.returnValue = "";
            return "";
        });

        function getStats() {
            if (!stats_loading) {
                stats_loading = true;
                stats_pending = true;
                var statsPath = "/player/76561198878175524";
                                var request = $.ajax({
                    url: statsPath + "/stats" + window.location.search,
                    method: "GET"
                })
                .done(function (msg) {
                    clearStatsChallenge();
                    $('#player-loading-section').removeClass('loading');
                    $('#player-loading-section').html(msg);
                })

                .fail(function (jqXHR, textStatus) {
                    $('#player-loading-section').removeClass('loading');

                    // Must precede the 403 branch: a challenge is served AS a 403.
                    if (jqXHR.getResponseHeader('cf-mitigated') === 'challenge') {
                        handleStatsChallenge();
                        stats_loading = false;
                        return;
                    }

                    if (jqXHR.status === 403) {
                        $('#player-loading-section').hide();
                        $('#player-login-required').show();
                    } else if (jqXHR.status === 429) {
                        $('#player-loading-section').hide();
                        showRateLimited(jqXHR.getResponseHeader('Retry-After'));
                    }
                    stats_loading = false;
                })

                .always(function () {
                    stats_pending = false;
                });
            }
        }
        // Rate limited notice, counts down Retry-After when the server sends one
        function showRateLimited(retryAfter) {
            var seconds = parseInt(retryAfter, 10);
            var $wait = $('#player-rate-limited-wait');
            var $retry = $('#player-rate-limited-retry');

            $('#player-rate-limited').show();

            if (!seconds || seconds < 0) {
                $wait.text('');
                $retry.show();
                return;
            }

            $retry.hide();

            (function tick() {
                if (seconds <= 0) {
                    $wait.text('');
                    $retry.show();
                    return;
                }

                $wait.text('You can try again in ' + seconds + 's.');
                seconds--;
                window.setTimeout(tick, 1000);
            })();
        }

        // Remember a challenge redirect for this tab session so it cannot loop
        function statsChallengeRedirected() {
            try {
                return !!window.sessionStorage && sessionStorage.getItem("stats-challenge") === "1";
            } catch (e) {
                return false;
            }
        }

        function markStatsChallenge() {
            try {
                if (window.sessionStorage) {
                    sessionStorage.setItem("stats-challenge", "1");
                }
            } catch (e) {}
        }

        function clearStatsChallenge() {
            try {
                if (window.sessionStorage) {
                    sessionStorage.removeItem("stats-challenge");
                }
            } catch (e) {}
        }

        // The challenge only fires on the /stats endpoint, which is XHR-only, so the
        // interstitial cannot surface from a profile reload. Navigate the top-level
        // window to /stats itself; Cloudflare then serves the challenge, and the
        // cf_return marker makes the controller send us back to the profile once it
        // is solved. One attempt per session; a persistent challenge falls back to
        // the manual notice rather than looping.
        function handleStatsChallenge() {
            $('#player-loading-section').hide();

            if (statsChallengeRedirected()) {
                $('#player-challenge').show();
                return;
            }

            markStatsChallenge();

            var target = "/player/76561198878175524";
                        target += "/stats";

            var qs = window.location.search;
            target += qs ? (qs + "&cf_return=1") : "?cf_return=1";

            window.location.href = target;
        }

        // Defer stats until the tab is viewed
        function getStatsWhenVisible() {
            if (typeof document.hidden === "undefined" || !document.hidden) {
                getStats();
                return;
            }

            document.addEventListener("visibilitychange", function onVisible() {
                if (!document.hidden) {
                    document.removeEventListener("visibilitychange", onVisible);
                    getStats();
                }
            });
        }

        // Remember confirmation for this tab session
        function statsGatePassed() {
            try {
                return !!window.sessionStorage && sessionStorage.getItem("stats-confirmed") === "1";
            } catch (e) {
                return false;
            }
        }

        function rememberStatsGate() {
            try {
                if (window.sessionStorage) {
                    sessionStorage.setItem("stats-confirmed", "1");
                }
            } catch (e) {}
        }

        // Reveal the loader and start the request
        function openStats() {
            $('#player-stats-gate').remove();
            $('#player-loading-section').show();
            getStatsWhenVisible();
        }

        // Temporary: preview a state with #skeleton or #rate-limited (optionally =seconds)
        function statsPreviewState() {
            var match = /^#(skeleton|rate-limited)(?:=([^\/]*))?$/.exec(window.location.hash);

            if (!match) {
                return false;
            }

            $('#player-stats-gate').remove();

            if (match[1] === "skeleton") {
                $('#player-loading-section').addClass('loading').show();
                return true;
            }

            $('#player-loading-section').hide();
            showRateLimited(match[2]);
            return true;
        }

        $(function () {
            if (statsPreviewState()) {
                return;
            }

            if (!$('#player-stats-gate').length || statsGatePassed()) {
                window.setTimeout(openStats, 100);
                return;
            }

            // Every real browser exposes the Page Visibility API, so guests load
            // with no friction. Only environments missing it have to ask.
            if (typeof document.hidden !== "undefined") {
                window.setTimeout(openStats, 100);
                return;
            }

            $('#player-loading-section').hide();
            $('#player-stats-gate').show();

            $('#player-stats-gate-button').on('click', function (e) {
                var native = e.originalEvent || e;

                if (native.isTrusted === false) {
                    return;
                }

                rememberStatsGate();
                openStats();
            });
        });

        $(function () {
            $('#player-rate-limited-retry').on('click', function () {
                $('#player-rate-limited').hide();
                $('#player-loading-section').addClass('loading').show();
                getStats();
            });

            $('#player-challenge-retry').on('click', function () {
                clearStatsChallenge();
                window.location.reload();
            });
        });
    