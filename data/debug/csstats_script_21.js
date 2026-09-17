
            (function ($) {
                $(document).ready(function () {
                    $('ul.dropdown-menu [data-toggle=dropdown]').on('click', function (event) {
                        event.preventDefault();
                        event.stopPropagation();
                        $(this).parent().siblings().removeClass('open');
                        $(this).parent().toggleClass('open');
                    });
                                    });
            })(jQuery);

            function dismissReplay() {
                document.getElementById('replay-overlay').style.display='none';
                var request = $.ajax({
                    url: "/replay/dismiss",
                    method: "POST",
                    dataType: "json"
                });
            }

            function check_for_sharecode(inputSource='search-input') {
                const search = document.getElementById(inputSource);

                if(search.value.match(/(CSGO-\w{5}-\w{5}-\w{5}-\w{5}-\w{5})/)
                    || search.value.match(/steam:\/\/rungame\/730\/76561202255233023\/\+csgo_download_match%20(CSGO-\w{5}-\w{5}-\w{5}-\w{5}-\w{5})/)
                ) {

                    add_match(search.value);
                    search.value = "";
                    if(inputSource==='cs2-matches-input') {
                        document.getElementById('cs2-matches-group').classList.remove('has-error')
                    }

                    return false;

                } else {

                    if(inputSource==='cs2-matches-input') {
                        document.getElementById('cs2-matches-group').classList.add('has-error');
                        return false;
                    }
                }

                return true;
            }

            var message = document.createElement('div');
            message.innerHTML = "";
            if(message.innerHTML) {
                document.body.appendChild(message);
                message.id = 'message';
            }

            var fixed_index = 0;
            var stored = Cookies.getJSON('matches');
            var matches = [];

            var match_list_ping = false;

            $(function() {
                if(!match_list_ping) {
                    match_list_ping = match_list_timeout();
                }
                if(stored) {
                    for(var i=0; i<stored.length; i++) {
                        stored[i].index = fixed_index;
                        ui_add_match(stored[i]);
                        matches.push(stored[i]);
                        fixed_index++;
                    }
                }
            });

            function add_by_sharecode(ele) {
                var code = false;
                if(document.getElementById('add-match-sharecode')) {
                    code = document.getElementById('add-match-sharecode').value;
                }
                // validate?
                if(code) {
                    add_match(code);
                }
                return false;
            }

            function ui_add_match(match_obj) {
                // in Queue
                //Error _ Unable to retrieve demo file. This match is over 7 days old, so it's likely the demo is no longer hosted on valve servers.

                var html =
                "<div class=\"add-match-list-item-inner\">" +
                    "<div class=\"status-icon\">" +
                        "<span class=\"glyphicon glyphicon-time\"></span>" +
                        "<span class=\"glyphicon glyphicon-ok\"></span>" +
                        "<span class=\"glyphicon glyphicon-warning-sign\"></span>" +
                    "</div>" +
                    "<div>" +
                        "<span class=\"add-match-name\">"+match_obj.sharecode+"</span>" +
                        "<div class=\"add-match-message\" style=\"padding-bottom:8px; display:block;\">" +
                            "<span class=\"add-match-message-state\"></span>" +
                            "<a class=\"add-match-view\"></a>" +
                        "</div>" +
                    "</div>" +
                    "<div class=\"match-list-item-actions\">" +
                        "<span class=\"match-list-item-action\" onclick=\"remove_match(this);\">" +
                            "<span class=\"glyphicon glyphicon-remove\"></span>" +
                        "</span>" +
                    "</div>" +
                "</div>";
                var ele = document.createElement('div');
                ele.innerHTML = html;
                ele.setAttribute('data-index', match_obj.index);
                ele.className = 'add-match-list-item';
                document.getElementById('match-queue-list-inner').appendChild(ele);
                ui_update_match(match_obj);
            }

            function ui_update_match(match_obj) {
                var ele = false;
                var match_eles = document.getElementById('match-queue-list-inner').getElementsByTagName('div');
                for(var i=0; i<match_eles.length; i++) {
                    if(match_eles[i].getAttribute('data-index') >= 0) {
                        if(match_eles[i].getAttribute('data-index') == match_obj.index) {
                            ele = match_eles[i];
                        }
                    }
                }

                if(ele) {
                    var msg = "Queuing";
                    if(match_obj.msg) {
                        msg = match_obj.msg;
                    }
                    ele.className = 'add-match-list-item '+match_obj.status;

                    var eles = ele.getElementsByTagName('span');
                    for(var i=0; i<eles.length; i++) {
                        if(eles[i].className == "add-match-name") {
                            eles[i].innerHTML = match_obj.sharecode;
                        } else if(eles[i].className == 'add-match-message-state') {
                            eles[i].innerHTML = msg;
                        }
                    }

                    var eles = ele.getElementsByTagName('a');
                    for(var i=0; i<eles.length; i++) {
                        if(eles[i].className == 'add-match-view') {
                            //console.log(match_obj);
                            if(match_obj.hasOwnProperty('url') && match_obj.url && match_obj.id) {
                                eles[i].href = match_obj.url;
                                eles[i].innerHTML = "View";
                            }
                        }
                    }
                }
            }

            function match_queued(data) {
                var item = false;
                for(var i=0; i<matches.length; i++) {
                    if(data.data.index == matches[i].index) {
                        item = i;
                    }
                }

                if(item !== false) {
                    matches[item].sharecode = data.data.sharecode;
                    matches[item].status = data.status;
                    matches[item].queue_id = data.data.queue_id;
                    matches[item].id = data.data.demo_id;
                    matches[item].error = parseInt(data.error);
                    matches[item].start = parseInt(data.data.start);
                    matches[item].msg = data.data.msg;
                    if(data.data.hasOwnProperty('url')) {
                        matches[item].url = data.data.url;
                    }
                    if(data.data.hasOwnProperty('in_queue')) {
                        matches[item].in_queue = data.data.in_queue;
                    } else {
                        matches[item].in_queue = 0;
                    }
                    ui_update_match(matches[item]);
                }
                Cookies.set('matches', matches);
                if(!match_list_ping) {
                    match_list_ping = match_list_timeout();
                }
            }

            var allow_match_list_refresh = false;
            var hidden, visibilityChange;
            if (typeof document.hidden !== "undefined") { // Opera 12.10 and Firefox 18 and later support
                hidden = "hidden";
                visibilityChange = "visibilitychange";
            } else if (typeof document.msHidden !== "undefined") {
                hidden = "msHidden";
                visibilityChange = "msvisibilitychange";
            } else if (typeof document.webkitHidden !== "undefined") {
                hidden = "webkitHidden";
                visibilityChange = "webkitvisibilitychange";
            }

            function match_list_check() {
                allow_match_list_refresh = false;
                var matches_processing = [];
                for (var i = 0; i < matches.length; i++) {
                    if (!matches[i].id && matches[i].queue_id && matches[i].in_queue) {
                        matches_processing.push(matches[i].queue_id);
                    }
                }
                if (matches_processing.length) {
                    if(typeof document[hidden] === "undefined" || !document[hidden]) {
                        var request = $.ajax({
                            url: "/match/processing/ajax",
                            method: "POST",
                            data: {matches: matches_processing},
                            dataType: "json"
                        })
                            .done(function (data) {
                                match_list_update(data);
                            })
                            .fail(function (jqXHR, textStatus) {
                                //	alert( "Request failed: " + textStatus );
                            });
                    } else {
                        allow_match_list_refresh = true;
                        window.clearInterval(match_list_ping);
                        match_list_ping = false;
                    }
                } else {
                    window.clearInterval(match_list_ping);
                    match_list_ping = false;
                }
            }

            document.addEventListener(visibilityChange, function() {
                if(!document[hidden] && allow_match_list_refresh === true && match_list_ping === false) {
                    match_list_check();
                    match_list_ping = match_list_timeout();
                }
            }, false);

            function match_list_timeout() {
                //return window.setInterval(match_list_check, 60000);
            }

            function match_list_update(data) {
                var updates = 0;
                for(var i=0; i<data.length; i++) {
                    for(var z=0; z<matches.length; z++) {
                        if(matches[z].queue_id == data[i].data.queue_id) {
                            matches[z].id = data[i].data.demo_id;
                            matches[z].queue_pos = data[i].data.queue_pos;
                            matches[z].error = parseInt(data[i].error);
                            matches[z].status = data[i].status;
                            matches[z].msg = data[i].data.msg;
                            if(data[i].data.hasOwnProperty('url')) {
                                matches[z].url = data[i].data.url;
                            }
                            if(data[i].data.hasOwnProperty('in_queue')) {
                                matches[z].in_queue = data[i].data.in_queue;
                            } else {
                                matches[z].in_queue = 0;
                            }
                            updates++;
                            ui_update_match(matches[z]);
                            break;
                        }
                    }
                }
                if(updates) {
                    Cookies.set('matches', matches);
                }
            }

            function isNumeric(n) {
                return !isNaN(parseFloat(n)) && isFinite(n);
            }

            function add_match(sharecode) {
                // Add by queue id
                $('body').addClass('open-match-queue');

                if(sharecode.substr(0, 1) == "#" && isNumeric(sharecode.substr(1, sharecode.length))) {
                    var queue_id = sharecode.substr(1, sharecode.length);
                    for (var i = 0; i < matches.length; i++) {
                        if (matches[i].queue_id == queue_id) {
                            return;
                        }
                    }
                    var match = {'sharecode': sharecode, 'queue_id': queue_id, 'id': false, 'index': fixed_index, 'error': 0, 'in_queue': 1};
                    ui_add_match(match);
                    matches.push(match);
                    Cookies.set('matches', matches);
                    if(!match_list_ping) {
                        match_list_ping = match_list_timeout();
                    }
                } else {
                    for (var i = 0; i < matches.length; i++) {
                        if (matches[i].sharecode == sharecode) {
                            return;
                        }
                    }

                    var match = {'sharecode': sharecode, 'queue_id': false, 'id': false, 'index': fixed_index, 'in_queue': 1};
                    ui_add_match(match);
                    matches.push(match);
                    Cookies.set('matches', matches);

                    var request = $.ajax({
                        url: "/match/upload/ajax",
                        method: "POST",
                        data: {sharecode: sharecode, index: fixed_index},
                        dataType: "json"
                    })

                        .done(function (msg) {
                            match_queued(msg);
                        })

                        .fail(function (jqXHR, textStatus) {
                            //	console.log(jqXHR);
                            //	console.log(textStatus);
                            //	alert( "Request failed: " + textStatus );
                        });
                }
                fixed_index++;
                return false;
            }

            function remove_match(ele) {
                var item = ele.parentNode.parentNode.parentNode;
                for(var i=0; i<matches.length; i++) {
                    if(item.getAttribute('data-index') == matches[i].index) {
                        matches.splice(i, 1);
                    }
                }
                $(item).slideToggle();
                Cookies.set('matches', matches);
            }

            $(function () {
                $('[data-toggle="tooltip"]').tooltip();
                $('[data-toggle="tooltip-html"]').tooltip({
                    html: true,
                });
            });

            /* Crosshair copy */
            function csxCopyCrosshair(el) {
                var code = el.getAttribute('data-xh-code') || '';
                if (!code) { return; }
                var done = function () {
                    el.classList.add('copied');
                    setTimeout(function () { el.classList.remove('copied'); }, 1400);
                };
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(code).then(done).catch(function () {});
                } else {
                    var t = document.createElement('textarea');
                    t.value = code;
                    document.body.appendChild(t);
                    t.select();
                    try { document.execCommand('copy'); done(); } catch (e) {}
                    document.body.removeChild(t);
                }
            }
        