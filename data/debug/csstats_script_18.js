
        function dismissConnect() {
            $('#faceit-connect').hide();
            var request = $.ajax({
                url: "/user/faceit/hide",
                method: "POST",
                dataType: "json",
                data: {
                    _token: 'jAb1lAtCqGAt9IWOSWGJSCvEwICm3wU9Irz2Bnaw'
                }
            });
        }
    