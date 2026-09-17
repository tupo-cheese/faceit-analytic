
            function dismissEvent() {
                var request = $.ajax({
                    url: "/dismiss/event",
                    method: "POST",
                    dataType: "json"
                });

                if(typeof(ga) != "undefined") {
                    ga('send', 'event', 'faceitevent', 'dismiss', 'event_1681395000', {
                        'transport': 'beacon'
                    });
                }
                $('#event-notif').hide();
            }
            function joinEvent() {
                if(typeof(ga) != "undefined") {
                    ga('send', 'event', 'faceitevent', 'click', 'event_1681395000', {
                        'transport': 'beacon'
                    });
                }
                return true;
            }
            function hideSurvey() {
                var banner = document.getElementById('nps-banner');
                if (banner) {
                    banner.classList.remove('nps-visible');
                    setTimeout(function(){ banner.style.display = 'none'; }, 400);
                }
            }
            function dismissSurvey() {
                hideSurvey();
                $.ajax({
                    url: "/feedback/dismiss",
                    method: "GET",
                    dataType: "json"
                });
            }

            function dismissBot() {
                var request = $.ajax({
                    url: "/bot/dismiss",
                    method: "POST",
                    dataType: "json"
                });
                $('#player-bot-connect').hide();
            }

        